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
def ajax_add_client(request):
    if request.method == 'POST':
        c = Client.objects.create(name=request.POST.get('name'), contact=request.POST.get('contact'))
        return JsonResponse({'status': 'success', 'client_id': c.id, 'client_name': str(c)})
    return JsonResponse({'status': 'error'})

@login_required
def ajax_get_inventory_by_category(request): 
    return JsonResponse({'items': [{'id': i.id, 'name': i.name, 'description': i.description, 'price': float(i.avg_unit_cost), 'unit': i.unit.name if i.unit else ''} for i in InventoryItem.objects.filter(category__iexact=request.GET.get('category', ''))]})

@login_required
def ajax_get_client_invoices(request):
    data = []
    for inv in Invoice.objects.filter(client_id=request.GET.get('client_id')).order_by('-date'):
        bal = float(inv.grand_total) - sum([float(b.amount) for b in FinanceBill.objects.filter(linked_invoice=inv, category='Invoice Payment', payment_status='Paid')])
        if bal > 0: data.append({'id': inv.id, 'number': inv.invoice_number, 'date': inv.date.strftime('%b %d, %Y'), 'total': float(inv.grand_total), 'balance': bal})
    return JsonResponse({'invoices': data})

@login_required
def ajax_get_all_client_invoices(request): 
    return JsonResponse({'invoices': [{'id': inv.id, 'name': f"{inv.invoice_number} (PKR {inv.grand_total})"} for inv in Invoice.objects.filter(client_id=request.GET.get('client_id')).order_by('-date')]})

@login_required
def ajax_get_client_expenses(request): 
    return JsonResponse({'expenses': [{'id': e.id, 'name': f"{e.date.strftime('%b %d, %Y')} - {e.custom_category} (PKR {e.amount})"} for e in FinanceBill.objects.filter(client_id=request.GET.get('client_id'), category='Expense').order_by('-date')]})

@login_required
def ajax_get_client_contracts(request): 
    return JsonResponse({'contracts': [{'id': c.id, 'name': f"Contract #{c.id} ({c.start_date.strftime('%b %d, %Y')} to {c.end_date.strftime('%b %d, %Y')})"} for c in MaintenanceContract.objects.filter(client_id=request.GET.get('client_id')).order_by('-end_date')]})

@login_required
def ajax_get_tax_rates(request): 
    return JsonResponse({'taxes': [{'id': t.id, 'name': t.name, 'rate': float(t.rate)} for t in TaxRate.objects.all()]})

@login_required
def ajax_get_invoice_items(request, id): 
    return JsonResponse({'items': list(get_object_or_404(Invoice, id=id).items.values('item_name', 'description', 'qty', 'unit', 'unit_price', 'unit_cost', 'total', 'inventory_item_id', 'item_tax_id', 'tax_amount'))})

@login_required
def ajax_get_quotation_items(request, id): 
    return JsonResponse({'items': list(get_object_or_404(Quotation, id=id).items.values('item_name', 'description', 'qty', 'unit', 'unit_price', 'unit_cost', 'total', 'inventory_item_id', 'item_tax_id', 'tax_amount'))})
