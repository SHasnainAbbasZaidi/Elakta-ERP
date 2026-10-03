from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib import messages
from operations.document_service import get_client, money
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
def inventory_list(request):
    show_zero = request.GET.get('show_zero', 'false') == 'true'
    items = InventoryItem.objects.all().prefetch_related('logs').order_by('-id')
    if not show_zero: items = items.filter(qty__gt=0)
    return render(request, 'operations/inventory_list.html', {'items': items, 'show_zero': show_zero})

@login_required
def inventory_history(request, id):
    item = get_object_or_404(InventoryItem, id=id)
    logs = item.logs.all().order_by('-date')
    s_date = request.GET.get('start_date'); e_date = request.GET.get('end_date')
    if s_date and e_date: logs = logs.filter(date__date__range=[s_date, e_date])
    return render(request, 'operations/inventory_history.html', {'item': item, 'logs': logs, 'start_date': s_date, 'end_date': e_date})

@login_required
def add_inventory(request):
    return _inventory_form(request)

@login_required
def edit_inventory(request, id):
    return _inventory_form(request, id)

def _inventory_form(request, id=None):
    item = get_object_or_404(InventoryItem, pk=id) if id else None
    old_qty = item.qty if item else 0
    form = InventoryItemForm(request.POST if request.method == 'POST' else None, instance=item)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            item = form.save()
            delta = item.qty - old_qty
            if delta or not id:
                InventoryLog.objects.create(item=item, action='Quantity adjustment' if id else 'Initial stock', qty_change=delta)
        return redirect('inventory_list')
    return render(request, 'operations/add_inventory.html', {'form':form, 'edit_mode':bool(id)})

@login_required
def print_inventory(request): 
    items = InventoryItem.objects.all().order_by('name')
    if request.GET.get('show_zero') != 'true': items = items.filter(qty__gt=0)
    return render(request, 'operations/printables/print_inventory.html', {'items': items})

@login_required
def dc_list(request): return render(request, 'operations/dc_list.html', {'dcs': DeliveryChallan.objects.all().order_by('-date')})

def _save_dc_items(request, dc):
    s, it, cn, cd, q = request.POST.getlist('source[]'), request.POST.getlist('inventory_item_id[]'), request.POST.getlist('item_name[]'), request.POST.getlist('description[]'), request.POST.getlist('qty[]')
    tot = 0
    for i in range(len(cn)):
        if cn[i].strip():
            try:
                qty = int(q[i]) if i < len(q) and q[i] else 1
            except ValueError:
                raise ValidationError('Delivery quantities must be whole numbers.')
            if qty <= 0:
                raise ValidationError('Delivery quantities must be positive.')
            tot += qty
            source_val = s[i] if i < len(s) and s[i] else 'Direct'
            inv_item = InventoryItem.objects.select_for_update().filter(id=it[i]).first() if i < len(it) and it[i] and it[i].isdigit() else None
            if source_val == 'Inventory' and (inv_item is None or inv_item.qty < qty):
                raise ValidationError(f'Insufficient inventory for {cn[i]}.')
            if source_val == 'Inventory' and inv_item:
                inv_item.qty -= qty; inv_item.save(); InventoryLog.objects.create(item=inv_item, action=f"Used in DC: {dc.dc_number}", qty_change=-qty)
                DeliveryChallanItem.objects.create(dc=dc, source='Inventory', inventory_item=inv_item, custom_item_name=cn[i], custom_item_description=cd[i] if i < len(cd) else "", qty=qty)
            else: DeliveryChallanItem.objects.create(dc=dc, source='Direct', custom_item_name=cn[i], custom_item_description=cd[i] if i < len(cd) else "", qty=qty)
    if tot <= 0: raise ValidationError('Add at least one delivery item.')
    dc.total_qty = tot; dc.save()

@login_required
def create_dc(request):
    return _dc_form(request)

@login_required
def edit_dc(request, id):
    return _dc_form(request, id)

@login_required
@require_POST
@transaction.atomic
def delete_dc(request, id):
    dc = get_object_or_404(DeliveryChallan, id=id)
    for item in dc.items.all():
        if item.source == 'Inventory' and item.inventory_item: item.inventory_item.qty += item.qty; item.inventory_item.save(); InventoryLog.objects.create(item=item.inventory_item, action=f"Reverted from DC Delete: {dc.dc_number}", qty_change=item.qty)
    dc.delete(); return redirect('dc_list')

@login_required
def print_dc(request, dc_id): return render(request, 'operations/printables/print_dc.html', {'doc': get_object_or_404(DeliveryChallan, id=dc_id), 'doc_type': 'Delivery Challan'})

def _dc_form(request, id=None):
    dc = get_object_or_404(DeliveryChallan, pk=id) if id else None
    form = DeliveryChallanForm(request.POST if request.method == 'POST' else None, instance=dc)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                saved = form.save(commit=False)
                saved.client = get_client(request.POST)
                saved.save()
                if id:
                    for line in saved.items.select_related('inventory_item'):
                        if line.source == 'Inventory' and line.inventory_item_id:
                            item = InventoryItem.objects.select_for_update().get(pk=line.inventory_item_id)
                            item.qty += line.qty
                            item.save()
                            InventoryLog.objects.create(item=item, action=f'Reverted from DC Edit: {saved.dc_number}', qty_change=line.qty)
                    saved.items.all().delete()
                _save_dc_items(request, saved)
            return redirect('dc_list')
        except ValidationError as exc:
            form.add_error(None, exc)
            if id: dc = DeliveryChallan.objects.get(pk=id)
    return render(request, 'operations/create_dc.html', {
        'form': form, 'edit_mode': bool(id), 'dc': dc,
        'edit_items': dc.items.all() if dc and dc.pk else [],
        'selected_client': dc.client if dc and dc.client_id else None,
        'categories': InventoryItem.objects.values_list('category', flat=True).distinct().exclude(category=''),
        'clients': Client.objects.all(), 'past_quotations': Quotation.objects.order_by('-id')[:50],
    })
