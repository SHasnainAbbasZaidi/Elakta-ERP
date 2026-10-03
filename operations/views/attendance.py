from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from operations.models import AttendanceDevice, AttendanceMapping, AttendancePunch, Employee
from operations.attendance_service import AttendanceError, fetch_records, parse_csv, store_records


class DeviceForm(forms.ModelForm):
    class Meta:
        model = AttendanceDevice
        fields = ['name', 'protocol', 'host', 'port', 'username', 'use_https', 'force_udp', 'timezone_name']

    def clean(self):
        data = super().clean()
        if data.get('protocol') != 'csv' and not data.get('host'):
            self.add_error('host', 'Enter the device IP address.')
        if data.get('port') is not None and not 1 <= data['port'] <= 65535:
            self.add_error('port', 'Port must be between 1 and 65535.')
        if data.get('protocol') == 'dahua' and not data.get('username'):
            self.add_error('username', 'Enter the Dahua device username.')
        try: ZoneInfo(data.get('timezone_name', ''))
        except (ZoneInfoNotFoundError, ValueError): self.add_error('timezone_name', 'Enter a valid timezone, such as Asia/Karachi.')
        return data


class SyncForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type':'date'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type':'date'}))
    password = forms.CharField(required=False, widget=forms.PasswordInput, label='Device password (not saved)')

    def clean(self):
        data = super().clean()
        start, end = data.get('start_date'), data.get('end_date')
        if start and end and (end < start or (end - start).days > 30):
            raise forms.ValidationError('Choose a date range of up to 31 days, with the start before the end.')
        return data


class MappingForm(forms.Form):
    device_user_id = forms.CharField(max_length=100, label='User ID on attendance machine')
    employee = forms.ModelChoiceField(queryset=Employee.objects.all())


@login_required
def attendance_home(request):
    if not request.user.is_superuser: raise PermissionDenied
    devices = AttendanceDevice.objects.order_by('name')
    records = AttendancePunch.objects.select_related('employee', 'device')
    device_id = request.GET.get('device', '')
    if device_id.isdigit(): records = records.filter(device_id=device_id)
    if request.GET.get('unmapped') == '1': records = records.filter(employee__isnull=True)
    return render(request, 'operations/attendance.html', {'devices':devices,
        'page':Paginator(records, 50).get_page(request.GET.get('page')), 'device_id':device_id,
        'unmapped':request.GET.get('unmapped') == '1', 'unmapped_count':AttendancePunch.objects.filter(employee__isnull=True).count()})


@login_required
def attendance_device_form(request, id=None):
    if not request.user.is_superuser: raise PermissionDenied
    device = get_object_or_404(AttendanceDevice, pk=id) if id else None
    form = DeviceForm(request.POST if request.method == 'POST' else None, instance=device)
    if request.method == 'POST' and form.is_valid():
        device = form.save()
        return redirect('attendance_device', id=device.pk)
    return render(request, 'operations/generic_form.html', {'form':form, 'title':'Edit attendance device' if id else 'Connect attendance device'})


@sensitive_post_parameters('password')
@login_required
def attendance_device(request, id):
    if not request.user.is_superuser: raise PermissionDenied
    device = get_object_or_404(AttendanceDevice, pk=id)
    today = timezone.localdate()
    action = request.POST.get('action') if request.method == 'POST' else None
    form = SyncForm(request.POST if action in ('sync', 'test') else None,
        initial={'start_date':today-timedelta(days=7), 'end_date':today})
    mapping_form = MappingForm(request.POST if action == 'map' else None)
    try:
        if action in ('sync', 'test') and form.is_valid():
            data = form.cleaned_data
            zone = ZoneInfo(device.timezone_name)
            start = datetime.combine(data['start_date'], time.min, zone)
            end = datetime.combine(data['end_date'] + timedelta(days=1), time.min, zone)
            records = fetch_records(device, data['password'], start, end, test=action == 'test')
            if action == 'test': messages.success(request, 'Connection verified: the device responded to an authenticated read request.')
            else:
                count = store_records(device, records)
                messages.success(request, f'Sync complete: {count} new punches; {len(records)-count} duplicates skipped.')
            return redirect('attendance_device', id=id)
        if action == 'import':
            upload = request.FILES.get('file')
            if not upload: raise AttendanceError('Choose a CSV file to import.')
            records = parse_csv(upload, device)
            count = store_records(device, records)
            messages.success(request, f'Imported {count} new punches; {len(records)-count} duplicates skipped.')
            return redirect('attendance_device', id=id)
        if action == 'map' and mapping_form.is_valid():
            data = mapping_form.cleaned_data
            with transaction.atomic():
                AttendanceMapping.objects.update_or_create(device=device, device_user_id=data['device_user_id'], defaults={'employee':data['employee']})
                AttendancePunch.objects.filter(device=device, device_user_id=data['device_user_id']).update(employee=data['employee'])
            messages.success(request, 'Employee mapping saved and existing punches updated.')
            return redirect('attendance_device', id=id)
    except AttendanceError as exc:
        messages.error(request, str(exc))
    return render(request, 'operations/attendance_device.html', {'device':device, 'form':form, 'mapping_form':mapping_form,
        'mappings':device.mappings.select_related('employee'),
        'unmapped_ids':AttendancePunch.objects.filter(device=device, employee__isnull=True).values_list('device_user_id', flat=True).distinct().order_by('device_user_id')})
