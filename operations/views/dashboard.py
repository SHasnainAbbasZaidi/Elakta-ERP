from operations.date_filters import date_range, filter_dates
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from decimal import Decimal
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
def dashboard(request):
    today = timezone.localdate()
    filter_type, start_date, end_date = date_range(request, default='today')

    inv_qs = Invoice.objects.all(); quo_qs = Quotation.objects.all(); fin_qs = FinanceBill.objects.all(); comp_qs = Complaint.objects.all()
    inv_qs = filter_dates(inv_qs, 'date', start_date, end_date)
    quo_qs = filter_dates(quo_qs, 'date', start_date, end_date)
    fin_qs = filter_dates(fin_qs, 'date', start_date, end_date)
    comp_qs = filter_dates(comp_qs, 'date_time__date', start_date, end_date)

    total_inv_amount = inv_qs.aggregate(Sum('grand_total'))['grand_total__sum'] or 0
    total_quo_amount = quo_qs.aggregate(Sum('grand_total'))['grand_total__sum'] or 0
    total_exp_amount = fin_qs.filter(category='Expense').aggregate(Sum('amount'))['amount__sum'] or 0

    inv_filter = Q(); quo_filter = Q()
    if start_date:
        inv_filter &= Q(invoice__date__gte=start_date); quo_filter &= Q(quotation__date__gte=start_date)
    if end_date:
        inv_filter &= Q(invoice__date__lte=end_date); quo_filter &= Q(quotation__date__lte=end_date)
    user_docs = User.objects.annotate(inv_count=Count('invoice', distinct=True, filter=inv_filter), quo_count=Count('quotation', distinct=True, filter=quo_filter)).filter(Q(inv_count__gt=0) | Q(quo_count__gt=0))

    approved_quo_count = quo_qs.filter(is_approved=True).count()
    paid_inv_count = 0; paid_inv_amount = 0; unpaid_inv_count = 0; unpaid_inv_amount = 0; overdue_inv_count = 0; overdue_inv_amount = 0

    for inv in inv_qs:
        paid = sum((b.amount for b in FinanceBill.objects.filter(linked_invoice=inv, category='Invoice Payment', payment_status='Paid')), Decimal('0'))
        paid = min(max(paid, Decimal('0')), inv.grand_total)
        bal = inv.grand_total - paid
        paid_inv_amount += paid
        if bal <= 0: paid_inv_count += 1
        else:
            unpaid_inv_count += 1
            if (today - inv.date).days > 30: overdue_inv_count += 1; overdue_inv_amount += bal
            else: unpaid_inv_amount += bal

    my_tasks = DailyTask.objects.filter(Q(created_by=request.user) | Q(assigned_to=request.user), is_open=True).order_by('date_time')
    last_maint = ServiceVisit.objects.order_by('-service_date').first()
    upcoming_maint = [{'contract': c, 'next_due': (ServiceVisit.objects.filter(contract=c).order_by('-service_date').first().service_date + timedelta(days=int(c.visit_frequency_days))), 'days_left': ((ServiceVisit.objects.filter(contract=c).order_by('-service_date').first().service_date + timedelta(days=int(c.visit_frequency_days))) - today).days} for c in MaintenanceContract.objects.filter(end_date__gte=today) if ServiceVisit.objects.filter(contract=c).exists() and 0 <= ((ServiceVisit.objects.filter(contract=c).order_by('-service_date').first().service_date + timedelta(days=int(c.visit_frequency_days))) - today).days <= 3]

    return render(request, 'operations/dashboard.html', {
        'filter_type': filter_type, 'start_date': start_date, 'end_date': end_date, 'total_inv_amount': total_inv_amount, 'total_quo_amount': total_quo_amount, 'total_exp_amount': total_exp_amount,
        'pending_quo_count': quo_qs.filter(is_approved=False).count(), 'user_docs': user_docs, 'approved_quo_count': approved_quo_count, 'paid_inv_count': paid_inv_count, 'paid_inv_amount': paid_inv_amount,
        'unpaid_inv_count': unpaid_inv_count, 'unpaid_inv_amount': unpaid_inv_amount, 'overdue_inv_count': overdue_inv_count, 'overdue_inv_amount': overdue_inv_amount,
        'my_tasks': my_tasks, 'last_maint': last_maint, 'upcoming_maint': upcoming_maint, 'total_open_comp': Complaint.objects.filter(status='Open').count(), 'todays_comp_count': Complaint.objects.filter(date_time__date=today).count()
    })

@login_required
def user_list(request): 
    if not request.user.is_superuser: return redirect('dashboard')
    return render(request, 'operations/user_list.html', {'users': User.objects.all().select_related('profile__role')})

@login_required
def add_user(request):
    if not request.user.is_superuser: return redirect('dashboard')
    form = UserForm(request.POST or None)
    if request.method == 'POST' and form.is_valid(): form.save(); return redirect('user_list')
    return render(request, 'operations/generic_form.html', {'form': form, 'title': 'Register New User'})

@login_required
def edit_user(request, id):
    if not request.user.is_superuser: return redirect('dashboard')
    edit_user_obj = get_object_or_404(User, id=id); form = UserEditForm(request.POST or None, instance=edit_user_obj, initial={'role': edit_user_obj.profile.role if hasattr(edit_user_obj, 'profile') else None})
    if request.method == 'POST' and form.is_valid(): form.save(); return redirect('user_list')
    return render(request, 'operations/generic_form.html', {'form': form, 'title': f'Edit User: {edit_user_obj.username}'})

@login_required
@require_POST
def delete_user(request, id):
    if not request.user.is_superuser: return redirect('dashboard')
    user_to_delete = get_object_or_404(User, id=id)
    if user_to_delete != request.user: user_to_delete.delete()
    return redirect('user_list')

@login_required
def add_company(request):
    if not request.user.is_superuser: return redirect('dashboard')
    form = CompanyProfileForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid(): form.save(); return redirect('user_list')
    return render(request, 'operations/generic_form.html', {'form': form, 'title': 'Add Company Profile'})

@login_required
def role_list(request):
    if not request.user.is_superuser: return redirect('dashboard')
    return render(request, 'operations/role_list.html', {'roles': CustomRole.objects.all()})

def _role_permissions(data):
    prefixes = {'dash':'dashboard', 'comp':'complaints', 'task':'tasks', 'inv':'invoices',
        'quo':'quotations', 'dc':'dc', 'invt':'inventory', 'maint':'maintenance', 'fin':'finance', 'rep':'reports', 'crm':'crm'}
    actions = {'view':'view', 'add':'add', 'edit':'edit', 'del':'delete', 'all':'view_all', 'comp':'complaints', 'tasks':'tasks'}
    return {module: {action: data.get(f'p_{prefix}_{suffix}') == 'on' for suffix, action in actions.items()}
        for prefix, module in prefixes.items()}

@login_required
def create_role(request):
    if not request.user.is_superuser: return redirect('dashboard')
    return _role_form(request)

@login_required
def edit_role(request, id):
    if not request.user.is_superuser: return redirect('dashboard')
    return _role_form(request, get_object_or_404(CustomRole, id=id))

def _role_form(request, role=None):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name or len(name) > 100:
            messages.error(request, 'Enter a role name of up to 100 characters.')
        elif CustomRole.objects.filter(name=name).exclude(pk=role.pk if role else None).exists():
            messages.error(request, 'A role with this name already exists.')
        else:
            role = role or CustomRole()
            role.name = name
            role.permissions = _role_permissions(request.POST)
            role.save()
            return redirect('role_list')
    return render(request, 'operations/role_form.html', {'title': 'Edit Role' if role else 'Create Role', 'role': role})
