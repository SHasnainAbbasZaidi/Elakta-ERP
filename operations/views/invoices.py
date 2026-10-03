from operations.date_filters import date_range, filter_dates
from operations.profit import document_profit
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from operations.document_service import get_client, save_lines
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
def invoice_list(request): 
    filter_type, start_date, end_date = date_range(request)
    search = request.GET.get('q', '').strip()
    qs = filter_dates(Invoice.objects.select_related('client', 'company').prefetch_related('items'), 'date', start_date, end_date).order_by('-date', '-id')
    if search: qs = qs.filter(Q(invoice_number__icontains=search) | Q(client__name__icontains=search) | Q(company__name__icontains=search))
    total_inv = qs.aggregate(Sum('grand_total'))['grand_total__sum'] or 0
    today = date.today(); paid_tot = 0; due_tot = 0; overdue_tot = 0; invoice_data = []
    top_client = qs.values('client__name').annotate(tot=Sum('grand_total')).order_by('-tot').first()
    for inv in qs:
        paid = sum((b.amount for b in FinanceBill.objects.filter(linked_invoice=inv, category='Invoice Payment', payment_status='Paid')), Decimal('0'))
        bal = max(inv.grand_total - paid, Decimal('0'))
        paid_tot += min(paid, inv.grand_total)
        if bal <= 0: status = 'Paid'
        else: due_tot += bal; status = 'Overdue' if (today - inv.date).days > 30 else 'Due'; overdue_tot += bal if status == 'Overdue' else 0
        invoice_data.append({'invoice': inv, 'payment_status': status, 'balance': bal, 'profit_data': document_profit(inv)})
    return render(request, 'operations/invoice_list.html', {'filter_type':filter_type, 'start_date':start_date, 'end_date':end_date, 'search_query':search, 'invoices': invoice_data, 'total_inv': total_inv, 'paid_tot': paid_tot, 'due_tot': due_tot, 'overdue_tot': overdue_tot, 'top_client': top_client})


@login_required
def create_invoice(request):
    return _document_form(request, 'invoice')

@login_required
def edit_invoice(request, id):
    return _document_form(request, 'invoice', id)

@login_required
@require_POST
def delete_invoice(request, id): Invoice.objects.get(id=id).delete(); return redirect('invoice_list')

@login_required
def print_invoice(request, invoice_id):
    doc = get_object_or_404(Invoice, id=invoice_id); tax_breakdown = {}
    if doc.tax_type == 'Item':
        for item in doc.items.all():
            if item.item_tax and item.tax_amount > 0: tax_breakdown[item.item_tax.name] = tax_breakdown.get(item.item_tax.name, 0) + float(item.tax_amount)
    elif doc.tax_type == 'Global' and doc.global_tax: tax_breakdown[doc.global_tax.name] = float(doc.total_tax_amount)
    return render(request, 'operations/printables/print_invoice.html', {'doc': doc, 'doc_type': 'Invoice', 'doc_number': doc.invoice_number, 'tax_breakdown': tax_breakdown})

@login_required
def quotation_list(request): 
    filter_type, start_date, end_date = date_range(request)
    search = request.GET.get('q', '').strip()
    qs = filter_dates(Quotation.objects.select_related('client', 'company').prefetch_related('items'), 'date', start_date, end_date).order_by('-date', '-id')
    if search: qs = qs.filter(Q(quotation_number__icontains=search) | Q(client__name__icontains=search) | Q(client__company_name__icontains=search))
    today = timezone.localdate()
    rows = []
    cards = {name: {'count':0, 'amount':Decimal('0')} for name in ('Total', 'Approved', 'Pending', 'Expired')}
    for quote in qs:
        expiry = quote.date + timedelta(days=quote.validity_days)
        status = 'Approved' if quote.is_approved else ('Expired' if today > expiry else 'Pending')
        for name in ('Total', status):
            cards[name]['count'] += 1
            cards[name]['amount'] += quote.grand_total
        rows.append({'quotation':quote, 'status':status, 'expiry_date':expiry, 'profit_data':document_profit(quote)})
    return render(request, 'operations/quotation_list.html', {'quotations':rows, 'cards':cards,
        'total_quo':cards['Total']['amount'], 'approved_tot':cards['Approved']['amount'],
        'filter_type':filter_type, 'start_date':start_date, 'end_date':end_date, 'search_query':search})



@login_required
def create_quotation(request):
    return _document_form(request, 'quotation')

@login_required
def edit_quotation(request, id):
    return _document_form(request, 'quotation', id)

@login_required
@require_POST
def delete_quotation(request, id): Quotation.objects.get(id=id).delete(); return redirect('quotation_list')

@login_required
@require_POST
def approve_quotation(request, id): quo = get_object_or_404(Quotation, id=id); quo.is_approved = True; quo.save(); return redirect('quotation_list')

@login_required
def print_quotation(request, quote_id): 
    doc = get_object_or_404(Quotation, id=quote_id); tax_breakdown = {}
    if doc.tax_type == 'Item':
        for item in doc.items.all():
            if item.item_tax and item.tax_amount > 0: tax_breakdown[item.item_tax.name] = tax_breakdown.get(item.item_tax.name, 0) + float(item.tax_amount)
    elif doc.tax_type == 'Global' and doc.global_tax: tax_breakdown[doc.global_tax.name] = float(doc.total_tax_amount)
    return render(request, 'operations/printables/print_invoice.html', {'doc': doc, 'doc_type': 'Quotation', 'doc_number': doc.quotation_number, 'tax_breakdown': tax_breakdown})


def _document_form(request, kind, id=None):
    is_quote = kind == 'quotation'
    model, form_class, item_model = (Quotation, QuotationForm, QuotationItem) if is_quote else (Invoice, InvoiceForm, InvoiceItem)
    document = get_object_or_404(model, pk=id) if id else None
    form = form_class(request.POST if request.method == 'POST' else None, instance=document)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                saved = form.save(commit=False)
                saved.client = get_client(request.POST)
                if not id:
                    saved.created_by = request.user
                if is_quote and id and request.POST.get('is_revised') == 'on':
                    original_number = saved.quotation_number
                    suffix = 1
                    number = f'{original_number}-R{suffix}'
                    while Quotation.objects.filter(quotation_number=number).exists():
                        suffix += 1
                        number = f'{original_number}-R{suffix}'
                    saved.pk = None
                    saved.quotation_number = number
                    saved.is_revised = True
                    saved.is_approved = False
                saved.save()
                save_lines(request.POST, saved, item_model, kind)
            return redirect(kind + '_list')
        except ValidationError as exc:
            form.add_error(None, exc)
            if id:
                document = model.objects.get(pk=id)
    lines = []
    if request.method == 'POST':
        keys = {'item_name':'item_name', 'description':'description', 'qty':'qty', 'unit':'unit', 'unit_price':'price', 'unit_cost':'unit_cost', 'inventory_item_id':'inventory_item_id', 'item_tax_id':'item_tax'}
        for index, name in enumerate(request.POST.getlist('item_name[]')):
            lines.append({key: (request.POST.getlist(post+'[]')[index] if index < len(request.POST.getlist(post+'[]')) else '') for key, post in keys.items()})
    elif document:
        lines = list(document.items.values('item_name','description','qty','unit','unit_price','unit_cost','inventory_item_id','item_tax_id'))
    return render(request, 'operations/document_form.html', {
        'lines':lines, 'kind':kind,
        'inventory_options':list(InventoryItem.objects.values('id','name','category','avg_unit_cost','description','unit__name')),
        'tax_options':list(TaxRate.objects.values('id','name','rate')),
        'posted_client':request.POST.get('client_select', '') if request.method == 'POST' else str(document.client_id) if document else '',
        'form': form, 'doc_type': kind.title(), 'edit_mode': bool(id), kind: document,
        'edit_items': document.items.all() if document and document.pk else [],
        'selected_client': document.client if document and document.client_id else None,
        'categories': InventoryItem.objects.values_list('category', flat=True).distinct().exclude(category=''),
        'clients': Client.objects.all(), 'units': ItemUnit.objects.all(),
        'taxes': TaxRate.objects.all(), 'companies': CompanyProfile.objects.all(),
        'past_invoices': Invoice.objects.order_by('-id')[:50],
        'past_quotations': Quotation.objects.order_by('-id')[:50],
    })
