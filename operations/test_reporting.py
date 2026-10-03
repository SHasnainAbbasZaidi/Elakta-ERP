from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Client, Vendor, Invoice, Quotation, FinanceBill, CompanyProfile, InventoryItem, InvoiceItem, TaxRate
from .profit import document_profit
from .ledger import ledger_data

class ReportingTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('reporter', password='test-pass'))
        self.customer = Client.objects.create(name='Acme')
        self.vendor = Vendor.objects.create(name='Supplier')
        self.company = CompanyProfile.objects.create(name='Company', company_code='CO')
        self.today = timezone.localdate()

    def invoice(self, **kw):
        return Invoice.objects.create(client=self.customer, company=self.company, **kw)

    def test_all_time_bypasses_even_invalid_stale_dates(self):
        self.invoice(date=self.today-timedelta(days=80), grand_total=100)
        response=self.client.get('/', {'filter':'all','start_date':'invalid','end_date':self.today.isoformat()})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['total_inv_amount'],100)
        self.assertIsNone(response.context['start_date'])

    def test_quotation_cards_match_filtered_rows_and_approval_wins(self):
        Quotation.objects.create(company=self.company,client=self.customer,date=self.today,grand_total=10)
        Quotation.objects.create(company=self.company,client=self.customer,date=self.today-timedelta(days=90),grand_total=20)
        Quotation.objects.create(company=self.company,client=self.customer,date=self.today-timedelta(days=90),grand_total=30,is_approved=True)
        response=self.client.get('/quotations/')
        self.assertEqual(response.context['cards']['Total']['count'],3)
        self.assertEqual(response.context['cards']['Expired']['amount'],20)
        self.assertEqual(response.context['cards']['Approved']['amount'],30)
        self.assertContains(response,'Pending')
        response=self.client.get('/quotations/',{'filter':'today'})
        self.assertEqual(response.context['cards']['Total']['amount'],10)
        self.assertEqual(self.client.get('/quotations/',{'q':'missing'}).context['cards']['Total']['count'],0)

    def test_profit_excludes_tax_and_preserves_cost(self):
        inv=self.invoice(sub_total=200,discount=20,grand_total=210,total_tax_amount=30)
        item=InventoryItem.objects.create(name='Part',category='Parts',avg_unit_cost=60)
        InvoiceItem.objects.create(invoice=inv,item_name='Part',qty=2,unit_price=100,unit_cost=60,inventory_item=item,total=200)
        item.avg_unit_cost=90;item.save()
        result=document_profit(inv)
        self.assertEqual(result['profit'],60)
        self.assertEqual(round(result['margin'],2),Decimal('33.33'))
        inv.items.update(unit_cost=None)
        self.assertIsNone(document_profit(inv)['profit'])
        inv.items.update(unit_cost=110)
        self.assertEqual(document_profit(inv)['profit'],-40)

    def test_save_cost_for_both_document_types(self):
        for path, model in [('invoices',Invoice),('quotations',Quotation)]:
            payload={'company':self.company.pk,'client_select':str(self.customer.pk),'date':self.today.isoformat(),'discount':'20','tax_type':'None','validity_days':15,'terms_conditions':'Test terms','item_name[]':['Part'],'qty[]':['2'],'price[]':['100'],'unit_cost[]':['60']}
            self.assertEqual(self.client.post('/'+path+'/create/',payload).status_code,302)
            doc=model.objects.get()
            self.assertEqual(doc.items.get().unit_cost,60)
            self.assertEqual(document_profit(doc)['profit'],60)
            self.assertEqual(self.client.get('/'+path+'/edit/'+str(doc.pk)+'/').status_code,200)

    def test_inventory_local_and_vendor_edit(self):
        payload={'name':'Part','category':'Parts','qty':3,'purchase_source':'Direct','dp_shop_name':'Local shop','avg_unit_cost':20}
        self.assertEqual(self.client.post('/inventory/add/',payload).status_code,302)
        item=InventoryItem.objects.get()
        self.assertEqual(item.get_purchase_source_display(),'Local')
        payload.update(purchase_source='Vendor',vendor=self.vendor.pk,qty=5)
        self.assertEqual(self.client.post(f'/inventory/edit/{item.pk}/',payload).status_code,302)
        item.refresh_from_db();self.assertEqual(item.vendor,self.vendor);self.assertEqual(item.dp_shop_name,'')
        self.assertEqual(sum(item.logs.values_list('qty_change',flat=True)),5)
        payload.pop('vendor')
        self.assertEqual(self.client.post(f'/inventory/edit/{item.pk}/',payload).status_code,200)

    def test_client_ledger_opening_pending_and_linked_customer(self):
        inv=self.invoice(date=self.today-timedelta(days=10),grand_total=100)
        wrong=Client.objects.create(name='Wrong')
        FinanceBill.objects.create(category='Invoice Payment',date=self.today,amount=30,linked_invoice=inv,client=wrong,payment_status='Paid')
        FinanceBill.objects.create(category='Invoice Payment',date=self.today,amount=20,linked_invoice=inv,payment_status='Pending')
        data=ledger_data('client',self.customer,self.today,self.today)
        self.assertEqual(data['opening'],100);self.assertEqual(data['closing'],70);self.assertEqual(len(data['rows']),2)
        self.assertEqual(ledger_data('client',wrong)['closing'],0)
        response=self.client.get(f'/finance/ledgers/client/{self.customer.pk}/')
        self.assertEqual(response.status_code,200);self.assertContains(response,'70.00')

    def test_vendor_balance_uses_only_paid_payments_not_remaining_cache(self):
        FinanceBill.objects.create(category='Purchase',vendor=self.vendor,amount=100,remaining_amount=0)
        FinanceBill.objects.create(category='Vendor Payment',vendor=self.vendor,amount=25,payment_status='Paid')
        FinanceBill.objects.create(category='Vendor Payment',vendor=self.vendor,amount=50,payment_status='Pending')
        self.assertEqual(ledger_data('vendor',self.vendor)['closing'],75)
        self.assertEqual(self.client.get('/finance/ledgers/').status_code,200)

    def test_reports_render_and_export(self):
        self.invoice(grand_total=100)
        for report in ['sales','quotations','receivables','payables','inventory','cash','operations','activity']:
            with self.subTest(report=report):
                response=self.client.get('/reports/',{'report':report})
                self.assertEqual(response.status_code,200)
                response=self.client.get('/reports/',{'report':report,'export':'csv'})
                self.assertEqual(response.status_code,200)
                self.assertIn('text/csv',response['Content-Type'])

    def test_receivables_asof_excludes_future_payments(self):
        inv=self.invoice(date=self.today-timedelta(days=40),grand_total=100)
        FinanceBill.objects.create(category='Invoice Payment',linked_invoice=inv,date=self.today+timedelta(days=1),amount=100,payment_status='Paid')
        response=self.client.get('/reports/',{'report':'receivables','filter':'custom','start_date':self.today.isoformat(),'end_date':self.today.isoformat()})
        self.assertEqual(response.context['summary']['Outstanding'],100)
        self.assertEqual(response.context['rows'][0][8],100)

    def test_csv_formula_escaped(self):
        self.customer.name='=1+1';self.customer.save();self.invoice()
        self.assertIn("'=1+1",self.client.get('/reports/',{'report':'sales','export':'csv'}).content.decode())

    def test_one_sided_date_range(self):
        self.invoice(date=self.today-timedelta(days=40),grand_total=100)
        self.invoice(date=self.today,grand_total=20)
        response=self.client.get('/',{'filter':'custom','start_date':self.today.isoformat()})
        self.assertEqual(response.context['total_inv_amount'],20)

    def test_ledger_and_export_require_module_permission(self):
        self.client.force_login(User.objects.create_user('restricted'))
        for url in ['/finance/ledgers/', f'/finance/ledgers/client/{self.customer.pk}/?export=csv', '/reports/?export=csv']:
            self.assertEqual(self.client.get(url).status_code,403)

    def test_unknown_cost_stays_unknown_when_editing(self):
        item=InventoryItem.objects.create(name='Part',category='Parts',avg_unit_cost=60)
        payload={'company':self.company.pk,'client_select':str(self.customer.pk),'date':self.today.isoformat(),'discount':'0','tax_type':'None','terms_conditions':'Test','item_name[]':['Part'],'qty[]':['1'],'price[]':['100'],'unit_cost[]':[''],'inventory_item_id[]':[str(item.pk)]}
        self.assertEqual(self.client.post('/invoices/create/',payload).status_code,302)
        self.assertIsNone(Invoice.objects.get().items.get().unit_cost)

    def test_cost_rounding_uses_half_up(self):
        inv=self.invoice(sub_total=1)
        InvoiceItem.objects.create(invoice=inv,item_name='Fractional',qty=Decimal('0.50'),unit_cost=Decimal('0.01'),unit_price=2,total=1)
        self.assertEqual(document_profit(inv)['cost'],Decimal('0.01'))
