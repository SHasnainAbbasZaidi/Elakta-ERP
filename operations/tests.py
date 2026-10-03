from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from .models import CompanyProfile, Client, Invoice, Quotation, FinanceBill, CustomRole, CRMLead

class WorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('tester', password='test-password-123')
        self.client.force_login(self.admin)
        self.company = CompanyProfile.objects.create(name='Test', company_code='TEST', address='Test', contact_number='123')
        self.customer = Client.objects.create(name='Customer', contact='123')

    def payload(self, **changes):
        data = {'company': self.company.pk, 'client_select': str(self.customer.pk),
            'date': timezone.localdate().isoformat(), 'discount': '10', 'tax_type': 'None',
            'terms_conditions': 'Test terms', 'validity_days': '15',
            'item_name[]': ['Service'], 'qty[]': ['2'], 'price[]': ['100.25'],
            'calculated_grand_total': '999999', 'calculated_sub_total': '999999'}
        data.update(changes)
        return data

    def test_second_invoice_and_quotation_get_unique_numbers(self):
        for model in (Invoice, Quotation):
            first = model.objects.create(company=self.company, client=self.customer)
            second = model.objects.create(company=self.company, client=self.customer)
            field = 'invoice_number' if model is Invoice else 'quotation_number'
            self.assertNotEqual(getattr(first, field), getattr(second, field))

    def test_invoice_ignores_browser_totals(self):
        self.assertEqual(self.client.post('/invoices/create/', self.payload()).status_code, 302)
        invoice = Invoice.objects.get()
        self.assertEqual(invoice.sub_total, Decimal('200.50'))
        self.assertEqual(invoice.grand_total, Decimal('190.50'))
        self.assertEqual(invoice.items.get().total, Decimal('200.50'))

    def test_invalid_items_roll_back_document_and_new_client(self):
        response = self.client.post('/invoices/create/', self.payload(**{'qty[]': ['-1'], 'client_select': 'Must not persist'}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(Client.objects.filter(name='Must not persist').exists())

    def test_invalid_edit_keeps_original_items(self):
        self.client.post('/invoices/create/', self.payload())
        invoice = Invoice.objects.get()
        self.client.post(f'/invoices/edit/{invoice.pk}/', self.payload(**{'qty[]': ['not a number']}))
        invoice.refresh_from_db()
        self.assertEqual(invoice.grand_total, Decimal('190.50'))
        self.assertEqual(invoice.items.get().qty, 2)

    def test_quotation_revision_preserves_original(self):
        self.client.post('/quotations/create/', self.payload())
        original = Quotation.objects.get()
        response = self.client.post(f'/quotations/edit/{original.pk}/', self.payload(is_revised='on'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Quotation.objects.count(), 2)
        self.assertEqual(original.items.count(), 1)
        revised = Quotation.objects.exclude(pk=original.pk).get()
        self.assertEqual(revised.items.count(), 1)
        self.assertTrue(revised.is_revised)

    def test_new_user_can_authenticate_and_has_role(self):
        role = CustomRole.objects.create(name='Sales')
        response = self.client.post('/users/add/', {'username':'newuser', 'password':'valid-password-123', 'role':role.pk})
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='newuser')
        self.assertTrue(user.check_password('valid-password-123'))
        self.assertEqual(user.profile.role, role)

    def test_invalid_user_and_company_forms_do_not_crash(self):
        for path in ['/users/add/', '/users/add-company/']:
            response = self.client.post(path, {'username': 'tester'})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)

    def test_crm_creation_saves_notes(self):
        response = self.client.post('/crm/', {'client_name':'Prospect', 'contact':'123', 'notes':'Follow up'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CRMLead.objects.get().project_details, 'Follow up')

    def test_dashboard_excludes_expenses_pending_and_double_counting(self):
        invoice = Invoice.objects.create(company=self.company, client=self.customer, grand_total=100, date=timezone.localdate()-timedelta(days=40))
        for category, status, amount in [('Invoice Payment','Paid',30),('Invoice Payment','Pending',20),('Expense','Paid',40)]:
            FinanceBill.objects.create(linked_invoice=invoice, category=category, payment_status=status, amount=amount)
        response = self.client.get('/?filter=all')
        self.assertEqual(response.context['paid_inv_amount'], 30)
        self.assertEqual(response.context['overdue_inv_amount'], 70)
        self.assertEqual(response.context['unpaid_inv_amount'], 0)
        self.assertEqual(self.client.get('/finance/').status_code, 200)

    def test_custom_date_validation(self):
        response = self.client.get('/?filter=custom&start_date=invalid&end_date=invalid')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose a valid date range')

    def test_finance_detail_exists(self):
        bill = FinanceBill.objects.create(category='Expense', amount=20)
        self.assertEqual(self.client.get(f'/finance/detail/{bill.pk}/').status_code, 200)

    def test_empty_dashboard_does_not_show_sample_chart_values(self):
        response = self.client.get('/')
        self.assertContains(response, 'No invoices in this period')
        self.assertNotContains(response, '680000')

    def test_role_checkboxes_round_trip_and_duplicate_validation(self):
        response = self.client.post('/roles/create/', {'name':'Operator', 'p_comp_view':'on', 'p_comp_add':'on', 'p_crm_view':'on'})
        self.assertEqual(response.status_code, 302)
        role = CustomRole.objects.get(name='Operator')
        self.assertTrue(role.permissions['complaints']['view'])
        self.assertTrue(role.permissions['complaints']['add'])
        self.assertFalse(role.permissions['complaints']['delete'])
        self.assertTrue(role.permissions['crm']['view'])
        self.assertEqual(self.client.post('/roles/create/', {'name':'Operator'}).status_code, 200)
        self.assertEqual(CustomRole.objects.filter(name='Operator').count(), 1)

    def test_user_activity_counts_are_not_multiplied_by_joins(self):
        for _ in range(2):
            Invoice.objects.create(company=self.company, client=self.customer, created_by=self.admin)
        for _ in range(3):
            Quotation.objects.create(company=self.company, client=self.customer, created_by=self.admin)
        user = self.client.get('/?filter=all').context['user_docs'].get(pk=self.admin.pk)
        self.assertEqual(user.inv_count, 2)
        self.assertEqual(user.quo_count, 3)

    def test_tax_totals_use_stored_rate(self):
        from .models import TaxRate
        tax = TaxRate.objects.create(name='Tax', rate='18')
        data = self.payload(tax_type='Global', global_tax=tax.pk, calculated_tax_amount='1')
        self.client.post('/invoices/create/', data)
        invoice = Invoice.objects.get()
        self.assertEqual(invoice.total_tax_amount, Decimal('34.29'))
        self.assertEqual(invoice.grand_total, Decimal('224.79'))

    def test_role_enforcement_and_admin_bypass(self):
        from .models import UserProfile
        role = CustomRole.objects.create(name='Read only', permissions={'invoices': {'view': True, 'add': False}})
        user = User.objects.create_user('reader', password='test-password')
        UserProfile.objects.create(user=user, role=role)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/invoices/').status_code, 200)
        self.assertEqual(self.client.post('/invoices/create/', self.payload()).status_code, 403)
        self.assertEqual(self.client.get('/finance/').status_code, 403)
        self.assertEqual(self.client.get('/users/').status_code, 403)
        self.assertEqual(self.client.get('/ajax/get-client-expenses/').status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/finance/').status_code, 200)

    def test_user_without_role_is_denied_business_access(self):
        user = User.objects.create_user('unassigned', password='test-password')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/').status_code, 403)
        self.assertEqual(self.client.post('/logout/').status_code, 302)

    def test_get_cannot_delete_or_approve_documents(self):
        invoice = Invoice.objects.create(company=self.company, client=self.customer)
        quote = Quotation.objects.create(company=self.company, client=self.customer)
        self.assertEqual(self.client.get(f'/invoices/delete/{invoice.pk}/').status_code, 405)
        self.assertEqual(self.client.get(f'/quotations/approve/{quote.pk}/').status_code, 405)
        self.assertTrue(Invoice.objects.filter(pk=invoice.pk).exists())
        self.assertEqual(self.client.post(f'/invoices/delete/{invoice.pk}/').status_code, 302)
        self.assertFalse(Invoice.objects.filter(pk=invoice.pk).exists())

    def test_insufficient_delivery_stock_rolls_back_all_rows(self):
        from .models import InventoryItem, DeliveryChallan, InventoryLog
        item = InventoryItem.objects.create(name='Stock', category='Parts', qty=3)
        data = {'company':self.company.pk, 'client_select':str(self.customer.pk), 'date':timezone.localdate().isoformat(),
            'source[]':['Inventory','Inventory'], 'inventory_item_id[]':[str(item.pk),str(item.pk)],
            'item_name[]':['Stock','Stock'], 'qty[]':['2','2']}
        response = self.client.post('/dc/create/', data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        item.refresh_from_db()
        self.assertEqual(item.qty, 3)
        self.assertFalse(DeliveryChallan.objects.exists())
        self.assertFalse(InventoryLog.objects.exists())

    def test_tasks_display_and_ownership(self):
        from .models import DailyTask, UserProfile
        task = DailyTask.objects.create(created_by=self.admin, task_type='Reminder', task_details='Visible task')
        self.assertContains(self.client.get('/tasks/'), 'Visible task')
        role = CustomRole.objects.create(name='Own tasks', permissions={'tasks': {'view': True, 'edit': True, 'view_all': False}})
        user = User.objects.create_user('taskuser', password='test-password')
        UserProfile.objects.create(user=user, role=role)
        self.client.force_login(user)
        self.assertNotContains(self.client.get('/tasks/'), 'Visible task')
        self.assertEqual(self.client.post('/tasks/', {'close_task':'1','task_id':task.pk}).status_code, 404)
        role.permissions['tasks']['view_all'] = True
        role.save()
        self.assertContains(self.client.get('/tasks/'), 'Visible task')
