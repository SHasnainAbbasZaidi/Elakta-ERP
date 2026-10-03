from django.views.decorators.http import require_POST
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from operations.models import Employee, JobCardTemplate
from operations.forms import EmployeeForm

@login_required
def employee_list(request):
    if not request.user.is_superuser: return redirect('dashboard')
    employees = Employee.objects.all().order_by('-id')
    return render(request, 'operations/employee_list.html', {'employees': employees})

@login_required
def employee_detail(request, id):
    if not request.user.is_superuser: return redirect('dashboard')
    emp = get_object_or_404(Employee, id=id)
    return render(request, 'operations/employee_detail.html', {'employee': emp})

@login_required
def add_employee(request):
    if not request.user.is_superuser: return redirect('dashboard')
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES)
        if form.is_valid():
            emp = form.save()
            return redirect('employee_detail', id=emp.id)
    else: form = EmployeeForm()
    return render(request, 'operations/generic_form.html', {'form': form, 'title': 'Register New Employee', 'enctype': 'multipart/form-data'})

@login_required
def edit_employee(request, id):
    if not request.user.is_superuser: return redirect('dashboard')
    emp = get_object_or_404(Employee, id=id)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, instance=emp)
        if form.is_valid():
            form.save()
            return redirect('employee_detail', id=emp.id)
    else: form = EmployeeForm(instance=emp)
    return render(request, 'operations/generic_form.html', {'form': form, 'title': f'Edit Employee: {emp.name}', 'enctype': 'multipart/form-data'})

@login_required
@require_POST
def delete_employee(request, id):
    if not request.user.is_superuser: return redirect('dashboard')
    get_object_or_404(Employee, id=id).delete()
    return redirect('employee_list')

@login_required
def print_job_card(request, id):
    emp = get_object_or_404(Employee, id=id)
    template = JobCardTemplate.objects.filter(is_active=True).first()
    validity_date = timezone.now().date() + timedelta(days=365)
    layout_json = json.dumps(template.layout_config) if template and template.layout_config else "{}"
    return render(request, 'operations/print_job_card.html', {
        'employee': emp, 'template': template, 'validity_date': validity_date, 'layout_json': layout_json
    })

@login_required
def save_job_card_layout(request, template_id):
    if request.method == 'POST' and request.user.is_superuser:
        template = get_object_or_404(JobCardTemplate, id=template_id)
        data = json.loads(request.body)
        template.layout_config = data
        template.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)
