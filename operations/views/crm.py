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
def crm_list(request):
    if request.method == 'POST':
        if 'update_status' in request.POST:
            lead = get_object_or_404(CRMLead, id=request.POST.get('lead_id'))
            lead.status = request.POST.get('new_status')
            lead.save()
            return redirect('crm_list')
        else:
            nfu = request.POST.get('next_follow_up')
            CRMLead.objects.create(
                client_name=request.POST.get('client_name'),
                company_name=request.POST.get('company_name', ''),
                contact=request.POST.get('contact'),
                status=request.POST.get('status', 'New'),
                priority=request.POST.get('priority', 'Medium'),
                lead_source=request.POST.get('lead_source', ''),
                expected_value=request.POST.get('expected_value') or 0,
                next_follow_up=nfu if nfu else None,
                project_details=request.POST.get('notes', ''),
                assigned_to_id=request.POST.get('assigned_to') or None,
                created_by=request.user
            )
            return redirect('crm_list')
            
    leads = CRMLead.objects.all().order_by('-created_at')
    statuses = ['New', 'Follow-Up', 'Converted', 'Lost']
    return render(request, 'operations/crm_list.html', {'leads': leads, 'users': User.objects.all(), 'statuses': statuses})

@login_required
def crm_lead_detail(request, id):
    lead = get_object_or_404(CRMLead, id=id)
    if request.method == 'POST':
        if 'add_activity' in request.POST:
            CRMActivityLog.objects.create(lead=lead, activity_type=request.POST.get('activity_type'), date_time=request.POST.get('date_time') or timezone.now(), remarks=request.POST.get('remarks'), added_by=request.user)
        elif 'update_lead' in request.POST:
            lead.status = request.POST.get('status')
            if lead.status == 'Lost': lead.lost_remarks = request.POST.get('lost_remarks', '')
            lead.priority = request.POST.get('priority')
            lead.client_name = request.POST.get('client_name'); lead.company_name = request.POST.get('company_name', ''); lead.contact = request.POST.get('contact')
            lead.email = request.POST.get('email', ''); lead.address = request.POST.get('address', ''); lead.city = request.POST.get('city', '')
            lead.product_category = request.POST.get('product_category', ''); lead.quantity = request.POST.get('quantity', 1); lead.budget = request.POST.get('budget') or 0; lead.project_details = request.POST.get('project_details', '')
            lead.assigned_to_id = request.POST.get('assigned_to') or None
            nfu = request.POST.get('next_follow_up'); lead.next_follow_up = nfu if nfu else None
            lead.follow_up_remarks = request.POST.get('follow_up_remarks', ''); lead.reminder = request.POST.get('reminder') == 'on'
            lead.decision_maker = request.POST.get('decision_maker', ''); lead.timeline = request.POST.get('timeline', ''); lead.probability = request.POST.get('probability', 10)
            lead.expected_value = request.POST.get('expected_value') or 0
            cd = request.POST.get('closing_date'); lead.closing_date = cd if cd else None
            lead.sales_stage = request.POST.get('sales_stage', '')
            lead.linked_quotation_id = request.POST.get('linked_quotation') or None
            lead.save()
            
            # Auto Convert Lead to Client if Converted
            if lead.status == 'Converted' and not Client.objects.filter(name=lead.client_name, contact=lead.contact).exists():
                Client.objects.create(name=lead.client_name, company_name=lead.company_name, contact=lead.contact, email=lead.email, address=f"{lead.address}, {lead.city}")
                
        return redirect('crm_lead_detail', id=lead.id)
    return render(request, 'operations/crm_lead_detail.html', {'lead': lead, 'quotations': Quotation.objects.all().order_by('-date'), 'users': User.objects.all()})
