from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
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
def finance_list(request):
    cat_filter = request.GET.get('category', ''); start_date = request.GET.get('start_date', ''); end_date = request.GET.get('end_date', '')
    bills = FinanceBill.objects.all().order_by('-date').select_related('client', 'linked_invoice', 'company')
    if cat_filter: bills = bills.filter(category=cat_filter)
    if start_date: bills = bills.filter(date__gte=start_date)
    if end_date: bills = bills.filter(date__lte=end_date)

    today = date.today()
    all_invoices = Invoice.objects.all()
    all_quos = Quotation.objects.all()
    
    tot_quo = all_quos.aggregate(Sum('grand_total'))['grand_total__sum'] or 0
    tot_inv = all_invoices.aggregate(Sum('grand_total'))['grand_total__sum'] or 0
    
    paid_inv_tot = 0; due_inv_tot = 0; overdue_inv_tot = 0
    for inv in all_invoices:
        paid = sum((b.amount for b in FinanceBill.objects.filter(linked_invoice=inv, category='Invoice Payment', payment_status='Paid')), Decimal('0'))
        bal = max(inv.grand_total - paid, Decimal('0'))
        paid_inv_tot += min(paid, inv.grand_total)
        if bal > 0:
            due_inv_tot += bal
            if (today - inv.date).days > 30: overdue_inv_tot += bal

    tot_exp = FinanceBill.objects.filter(category='Expense').aggregate(Sum('amount'))['amount__sum'] or 0
    tot_cashbill = FinanceBill.objects.filter(category='Cash Bill').aggregate(Sum('amount'))['amount__sum'] or 0
    tot_purchases = FinanceBill.objects.filter(category='Purchase').aggregate(Sum('amount'))['amount__sum'] or 0
    tot_vendor_paid = FinanceBill.objects.filter(category='Vendor Payment').aggregate(Sum('amount'))['amount__sum'] or 0
    
    vendor_pending = tot_purchases - tot_vendor_paid
    company_diff = paid_inv_tot - tot_vendor_paid

    return render(request, 'operations/finance_list.html', {
        'bills': bills, 'cat_filter': cat_filter, 'start_date': start_date, 'end_date': end_date,
        'tot_quo': tot_quo, 'tot_inv': tot_inv, 'paid_inv_tot': paid_inv_tot, 'due_inv_tot': due_inv_tot, 'overdue_inv_tot': overdue_inv_tot,
        'tot_exp': tot_exp, 'tot_cashbill': tot_cashbill, 'tot_purchases': tot_purchases, 'tot_vendor_paid': tot_vendor_paid,
        'vendor_pending': vendor_pending, 'company_diff': company_diff
    })

@login_required
def add_finance(request):
    if request.method == 'POST':
        cat = request.POST.get('category'); amount = float(request.POST.get('amount') or 0)
        cv = request.POST.get('client_select'); vv = request.POST.get('vendor_select')
        client = Client.objects.filter(id=cv).first() if cv and cv.isdigit() else (Client.objects.create(name=cv) if cv else None)
        vendor = Vendor.objects.filter(id=vv).first() if vv and vv.isdigit() else None
        
        bill = FinanceBill.objects.create(company_id=request.POST.get('company') or None, category=cat, custom_category=request.POST.get('custom_category', ''), date=request.POST.get('date') or timezone.now(), amount=amount, client=client, linked_invoice_id=request.POST.get('linked_invoice') or None, vendor=vendor, payment_status=request.POST.get('payment_status', 'Paid'), payment_method=request.POST.get('payment_method', ''), bank_name=request.POST.get('bank_name', ''), reference_number=request.POST.get('reference_number', ''), cheque_date=request.POST.get('cheque_date') or None, person_name=request.POST.get('person_name', ''), vendor_invoice_number=request.POST.get('vendor_invoice_number', ''), remarks=request.POST.get('remarks', ''), receipt_image=request.FILES.get('receipt_image'))
        
        if cat == 'Vendor Payment' and vendor:
            remaining = amount
            for pur in FinanceBill.objects.filter(category='Purchase', vendor=vendor, remaining_amount__gt=0).order_by('date'):
                if remaining <= 0: break
                if remaining >= pur.remaining_amount: remaining -= float(pur.remaining_amount); pur.remaining_amount = 0; pur.payment_status = 'Paid'; pur.save()
                else: pur.remaining_amount = float(pur.remaining_amount) - remaining; pur.payment_status = 'Partial'; pur.save(); remaining = 0
                    
        if cat == 'Purchase': bill.remaining_amount = amount; bill.payment_status = 'Pending'; bill.save()

        if cat in ['Cash Bill', 'Other']:
            names = request.POST.getlist('item_name[]'); qtys = request.POST.getlist('qty[]'); prices = request.POST.getlist('price[]'); totals = request.POST.getlist('total[]')
            for i in range(len(names)):
                if names[i].strip(): FinanceBillItem.objects.create(bill=bill, item_name=names[i], qty=qtys[i] if i<len(qtys) else 1, unit_price=prices[i] if i<len(prices) else 0, total=totals[i] if i<len(totals) else 0)
        
        if cat in ['Invoice Payment', 'Vendor Payment', 'Cash Bill']: return redirect('print_receipt', receipt_id=bill.id)
        return redirect('finance_list')
    return render(request, 'operations/create_finance.html', {'clients': Client.objects.all(), 'vendors': Vendor.objects.all(), 'companies': CompanyProfile.objects.all()})

@login_required
def print_receipt(request, receipt_id):
    bill = get_object_or_404(FinanceBill, id=receipt_id); history = []; total_invoice = 0; balance = 0
    if bill.category == 'Invoice Payment' and bill.linked_invoice:
        history = FinanceBill.objects.filter(linked_invoice=bill.linked_invoice, category='Invoice Payment', payment_status='Paid').order_by('date')
        total_invoice = float(bill.linked_invoice.grand_total)
        balance = total_invoice - sum([float(h.amount) for h in history])
    return render(request, 'operations/printables/print_receipt.html', {'bill': bill, 'history': history, 'total_invoice': total_invoice, 'balance': balance})

@login_required
def finance_detail(request, id): return render(request, 'operations/finance_detail.html', {'bill': get_object_or_404(FinanceBill, id=id)})

@login_required
def edit_finance(request, id):
    if not request.user.is_superuser: return redirect('finance_list')
    bill = get_object_or_404(FinanceBill, id=id)
    if request.method == 'POST':
        cv = request.POST.get('client_select'); bill.client = Client.objects.filter(id=cv).first() if cv and cv.isdigit() else (Client.objects.create(name=cv) if cv else None)
        bill.category = request.POST.get('category'); bill.custom_category = request.POST.get('custom_category', ''); bill.date = request.POST.get('date'); bill.amount = request.POST.get('amount', 0); bill.payment_status = request.POST.get('payment_status', 'Paid'); bill.payment_method = request.POST.get('payment_method', ''); bill.linked_invoice_id = request.POST.get('linked_invoice') or None; bill.save(); return redirect('finance_list')
    return render(request, 'operations/create_finance.html', {'bill': bill, 'edit_mode': True, 'clients': Client.objects.all(), 'vendors': Vendor.objects.all(), 'companies': CompanyProfile.objects.all()})

@login_required
@require_POST
def delete_finance(request, id):
    if not request.user.is_superuser: return redirect('finance_list')
    FinanceBill.objects.get(id=id).delete(); return redirect('finance_list')
