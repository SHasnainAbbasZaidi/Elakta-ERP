from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum, Q, Count, F
from datetime import date, timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required

from operations.models import (CompanyProfile, Complaint, ComplaintRemark, Client, Technician, DailyTask, MaintenanceContract, ServiceVisit, MaintenanceContractJob,
                     Invoice, InvoiceItem, Quotation, QuotationItem, InventoryItem, CRMLead, CRMActivityLog, TaxRate,
                     InventoryLog, DeliveryChallan, DeliveryChallanItem, FinanceBill, FinanceBillItem,
                     CustomRole, UserProfile, ItemUnit, Vendor)
from operations.forms import (CompanyProfileForm, ComplaintForm, DailyTaskForm, MaintenanceContractForm, ServiceVisitForm, 
                    InvoiceForm, QuotationForm, InventoryItemForm, DeliveryChallanForm, FinanceBillForm, 
                    UserForm, UserEditForm, CRMLeadForm, TaxRateForm)

@login_required
def complaints_manager(request):
    if request.method == 'POST':
        if 'save_complaint' in request.POST:
            cv = request.POST.get('client_select')
            c = Complaint.objects.create(
                company_id=request.POST.get('company'), 
                client=(Client.objects.get(id=cv) if cv and cv.isdigit() else Client.objects.create(name=cv, address=request.POST.get('new_client_address', ''), contact=request.POST.get('new_client_contact', ''), company_name=request.POST.get('new_client_company', ''))), 
                issue_description=request.POST.get('issue_description'), 
                status=request.POST.get('status', 'Open'), 
                created_by=request.user
            )
            if c.status == 'Closed': c.closed_at = request.POST.get('closed_at') or timezone.now(); c.save()
            c.technicians.set([Technician.objects.get(id=tid) if tid.isdigit() else Technician.objects.get_or_create(name=tid)[0] for tid in request.POST.getlist('technicians[]')])
            ComplaintRemark.objects.create(complaint=c, remark="Complaint Opened", status_changed_to=c.status, added_by=request.user)
        elif 'update_status' in request.POST:
            c = get_object_or_404(Complaint, id=request.POST.get('complaint_id'))
            c.status = request.POST.get('new_status')
            if request.POST.get('linked_invoice'): c.linked_invoice_id = request.POST.get('linked_invoice')
            if request.POST.get('linked_expense'): c.linked_expense_id = request.POST.get('linked_expense')
            c.closed_at = request.POST.get('closed_at') or timezone.now() if c.status == 'Closed' else None
            c.save(); ComplaintRemark.objects.create(complaint=c, remark=request.POST.get('remark_text'), status_changed_to=c.status, added_by=request.user)
        return redirect('complaints')
    
    q = request.GET.get('q', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    status_filter = request.GET.get('status', '')

    qs = Complaint.objects.all().order_by('-date_time').prefetch_related('technicians')
    if start_date: qs = qs.filter(date_time__date__gte=start_date)
    if end_date: qs = qs.filter(date_time__date__lte=end_date)
    
    open_count = qs.filter(status='Open').count()
    pending_count = qs.filter(status='Pending').count()
    closed_count = qs.filter(status='Closed').count()
    unbilled_count = qs.filter(status='Closed', linked_invoice__isnull=True).count()

    if status_filter == 'Open': qs = qs.filter(status='Open')
    elif status_filter == 'Pending': qs = qs.filter(status='Pending')
    elif status_filter == 'Closed': qs = qs.filter(status='Closed')
    elif status_filter == 'Unbilled': qs = qs.filter(status='Closed', linked_invoice__isnull=True)

    if q: qs = qs.filter(Q(complaint_number__icontains=q) | Q(client__name__icontains=q) | Q(issue_description__icontains=q) | Q(technicians__name__icontains=q)).distinct()
    
    return render(request, 'operations/complaint_form.html', {
        'complaints': qs, 'search_query': q, 'start_date': start_date, 'end_date': end_date, 'status_filter': status_filter,
        'open_count': open_count, 'pending_count': pending_count, 'closed_count': closed_count, 'unbilled_count': unbilled_count,
        'clients': Client.objects.all(), 'technicians': Technician.objects.all(), 'companies': CompanyProfile.objects.all(), 
        'invoices': Invoice.objects.all(), 'expenses': FinanceBill.objects.filter(category='Expense')
    })

@login_required
def complaint_detail(request, id): return render(request, 'operations/complaint_detail.html', {'complaint': get_object_or_404(Complaint, id=id)})
@login_required
@require_POST
def delete_complaint(request, id): Complaint.objects.get(id=id).delete(); return redirect('complaints')
@login_required
def print_complaint(request, complaint_id): return render(request, 'operations/printables/print_complaint.html', {'complaint': get_object_or_404(Complaint, id=complaint_id)})

@login_required
def daily_tasks(request):
    if request.method == 'POST':
        if 'save_task' in request.POST:
            cv = request.POST.get('client_select')
            DailyTask.objects.create(created_by=request.user, task_type=request.POST.get('task_type'), custom_task_type=request.POST.get('custom_task_type', ''), client=(Client.objects.get(id=cv) if cv and cv.isdigit() else (Client.objects.create(name=cv) if cv else None)), assigned_to_id=request.POST.get('assigned_to') or None, date_time=request.POST.get('date_time') or timezone.now(), task_details=request.POST.get('task_details', ''))
        elif 'close_task' in request.POST:
            task = get_object_or_404(_visible_tasks(request.user), id=request.POST.get('task_id')); task.is_open = False; task.close_remarks = request.POST.get('close_remarks'); task.save()
        return redirect('daily_tasks')
    return render(request, 'operations/daily_tasks.html', {'open_tasks': _visible_tasks(request.user).filter(is_open=True).order_by('date_time'), 'assigned_to_me': DailyTask.objects.filter(assigned_to=request.user, is_open=True).order_by('date_time'), 'created_by_me': _visible_tasks(request.user).filter(is_open=True).order_by('date_time'), 'closed_tasks': _visible_tasks(request.user).filter(is_open=False).order_by('-date_time')[:15], 'clients': Client.objects.all(), 'users': User.objects.all()})

@login_required
def edit_task(request, id):
    task = get_object_or_404(_visible_tasks(request.user), id=id)
    if request.method == 'POST':
        cv = request.POST.get('client_select')
        task.client = Client.objects.get(id=cv) if cv and cv.isdigit() else (Client.objects.create(name=cv) if cv else None)
        task.task_type = request.POST.get('task_type'); task.custom_task_type = request.POST.get('custom_task_type', ''); task.assigned_to_id = request.POST.get('assigned_to') or None; task.date_time = request.POST.get('date_time') or task.date_time; task.task_details = request.POST.get('task_details', ''); task.is_open = 'is_open' in request.POST; task.close_remarks = request.POST.get('close_remarks', ''); task.save(); return redirect('daily_tasks')
    return render(request, 'operations/edit_task.html', {'task': task, 'clients': Client.objects.all(), 'users': User.objects.all()})

@login_required
@require_POST
def delete_task(request, id): get_object_or_404(_visible_tasks(request.user), id=id).delete(); return redirect('daily_tasks')

@login_required
def maintenance_dashboard(request):
    contracts = MaintenanceContract.objects.all().order_by('end_date')
    today = date.today(); upcoming = []
    for c in contracts:
        visits = ServiceVisit.objects.filter(contract=c)
        c.total_expenses = sum([v.linked_expense.amount for v in visits if v.linked_expense])
        c.total_invoiced = sum([v.linked_invoice.grand_total for v in visits if v.linked_invoice])
        c.profit_loss = c.charges - c.total_expenses
        last_visit = visits.order_by('-service_date').first()
        if last_visit:
            next_due = last_visit.service_date + timedelta(days=int(c.visit_frequency_days))
            if (next_due - today).days <= 7: upcoming.append({'contract': c, 'next_due': next_due, 'days_left': (next_due - today).days})
    return render(request, 'operations/maintenance.html', {'contracts': contracts, 'upcoming': upcoming, 'recent_visits': ServiceVisit.objects.all().order_by('-service_date')[:15], 'clients': Client.objects.all(), 'companies': CompanyProfile.objects.all()})

@login_required
def add_contract(request):
    if request.method == 'POST':
        cv = request.POST.get('client_select')
        contract = MaintenanceContract.objects.create(client=(Client.objects.get(id=cv) if cv and cv.isdigit() else Client.objects.create(name=cv)), company_id=request.POST.get('company') or None, locations=request.POST.get('locations', ''), start_date=request.POST.get('start_date'), end_date=request.POST.get('end_date'), visit_frequency_days=request.POST.get('visit_frequency_days'), charges=request.POST.get('charges'), terms_conditions=request.POST.get('terms_conditions'))
        for j in request.POST.getlist('jobs[]'):
            if j.strip(): MaintenanceContractJob.objects.create(contract=contract, description=j)
        return redirect('contract_detail', id=contract.id)
    return render(request, 'operations/create_contract.html', {'clients': Client.objects.all(), 'companies': CompanyProfile.objects.all()})

@login_required
def edit_contract(request, id):
    c = get_object_or_404(MaintenanceContract, id=id)
    if request.method == 'POST':
        cv = request.POST.get('client_select')
        c.client = Client.objects.get(id=cv) if cv and cv.isdigit() else Client.objects.create(name=cv); c.company_id = request.POST.get('company') or None; c.locations = request.POST.get('locations', ''); c.start_date = request.POST.get('start_date'); c.end_date = request.POST.get('end_date'); c.visit_frequency_days = request.POST.get('visit_frequency_days'); c.charges = request.POST.get('charges'); c.terms_conditions = request.POST.get('terms_conditions'); c.save()
        c.jobs.all().delete()
        for j in request.POST.getlist('jobs[]'):
            if j.strip(): MaintenanceContractJob.objects.create(contract=c, description=j)
        return redirect('contract_detail', id=c.id)
    return render(request, 'operations/create_contract.html', {'contract': c, 'edit_mode': True, 'clients': Client.objects.all(), 'companies': CompanyProfile.objects.all()})

@login_required
@require_POST
def delete_contract(request, id): get_object_or_404(MaintenanceContract, id=id).delete(); return redirect('maintenance')

@login_required
def contract_detail(request, id):
    c = get_object_or_404(MaintenanceContract, id=id); visits = ServiceVisit.objects.filter(contract=c).order_by('-service_date')
    c.total_expenses = sum([v.linked_expense.amount for v in visits if v.linked_expense])
    c.total_invoiced = sum([v.linked_invoice.grand_total for v in visits if v.linked_invoice])
    c.profit_loss = c.charges - c.total_expenses
    return render(request, 'operations/contract_detail.html', {'contract': c, 'visits': visits})

@login_required
def print_contract(request, contract_id): return render(request, 'operations/printables/print_contract.html', {'contract': get_object_or_404(MaintenanceContract, id=contract_id)})

@login_required
def add_service(request):
    if request.method == 'POST':
        ServiceVisit.objects.create(client_id=request.POST.get('client_select'), contract_id=request.POST.get('contract') or None, service_date=request.POST.get('service_date'), technician_id=request.POST.get('technician') or None, remarks=request.POST.get('remarks'), linked_invoice_id=request.POST.get('linked_invoice') or None, linked_expense_id=request.POST.get('linked_expense') or None, work_performed_doc=request.FILES.get('work_performed_doc'))
        return redirect('maintenance')
    return render(request, 'operations/create_service.html', {'clients': Client.objects.all(), 'technicians': Technician.objects.all(), 'contracts': MaintenanceContract.objects.all()})

@login_required
def service_visit_detail(request, visit_id): return render(request, 'operations/service_detail.html', {'visit': get_object_or_404(ServiceVisit, id=visit_id)})
@login_required
def print_service(request, visit_id): return render(request, 'operations/printables/print_service.html', {'visit': get_object_or_404(ServiceVisit, id=visit_id), 'company': CompanyProfile.objects.first()})

def _visible_tasks(user):
    profile = getattr(user, 'profile', None)
    permissions = profile.role.permissions if profile and profile.role else {}
    task_permissions = permissions.get('tasks', {})
    if user.is_superuser or isinstance(task_permissions, dict) and task_permissions.get('view_all'):
        return DailyTask.objects.all()
    return DailyTask.objects.filter(Q(created_by=user) | Q(assigned_to=user))
