from django import forms
from django.contrib.auth.models import User
from .models import (CompanyProfile, Complaint, DailyTask, MaintenanceContract, ServiceVisit, 
                     Invoice, Quotation, InventoryItem, DeliveryChallan, FinanceBill, CRMLead, TaxRate, CustomRole, UserProfile)

class CompanyProfileForm(forms.ModelForm):
    class Meta: 
        model = CompanyProfile
        fields = '__all__'

class TaxRateForm(forms.ModelForm):
    class Meta: 
        model = TaxRate
        fields = '__all__'

class CRMLeadForm(forms.ModelForm):
    class Meta: 
        model = CRMLead
        fields = '__all__'

class ComplaintForm(forms.ModelForm):
    class Meta: 
        model = Complaint
        fields = ['company', 'issue_description', 'client', 'technicians', 'status', 'linked_invoice', 'linked_expense', 'closed_at']

class DailyTaskForm(forms.ModelForm):
    class Meta: 
        model = DailyTask
        fields = '__all__'

class MaintenanceContractForm(forms.ModelForm):
    class Meta: 
        model = MaintenanceContract
        fields = '__all__'

class ServiceVisitForm(forms.ModelForm):
    class Meta: 
        model = ServiceVisit
        fields = '__all__'

class InvoiceForm(forms.ModelForm):
    def clean_discount(self):
        value = self.cleaned_data['discount']
        if value < 0:
            raise forms.ValidationError('Discount cannot be negative.')
        return value

    class Meta: 
        model = Invoice
        fields = ['company', 'date', 'discount', 'tax_type', 'global_tax', 'terms_conditions']
        widgets = {'date': forms.DateInput(attrs={'type':'date'}, format='%Y-%m-%d')}

class QuotationForm(forms.ModelForm):
    def clean_validity_days(self):
        value = self.cleaned_data['validity_days']
        if value < 1:
            raise forms.ValidationError('Validity must be at least one day.')
        return value

    class Meta: 
        model = Quotation
        fields = ['company', 'date', 'validity_days', 'discount', 'tax_type', 'global_tax', 'terms_conditions']
        widgets = {'date': forms.DateInput(attrs={'type':'date'}, format='%Y-%m-%d')}

class InventoryItemForm(forms.ModelForm):
    def clean(self):
        data = super().clean()
        if (data.get('qty') or 0) < 0: self.add_error('qty', 'Quantity cannot be negative.')
        if (data.get('avg_unit_cost') or 0) < 0: self.add_error('avg_unit_cost', 'Cost cannot be negative.')
        if not data.get('category', '').strip(): self.add_error('category', 'Enter a category.')
        if data.get('purchase_source') == 'Vendor':
            if not data.get('vendor'): self.add_error('vendor', 'Select a vendor.')
            data['dp_shop_name'] = ''
        else:
            data['vendor'] = None
        return data

    class Meta: 
        model = InventoryItem
        fields = ['item_code', 'category', 'name', 'description', 'qty', 'unit', 'location', 'purchase_source', 'vendor', 'dp_shop_name', 'avg_unit_cost']

class DeliveryChallanForm(forms.ModelForm):
    class Meta: 
        model = DeliveryChallan
        fields = ['company', 'date', 'delivered_by', 'site_project']

class FinanceBillForm(forms.ModelForm):
    class Meta: 
        model = FinanceBill
        fields = '__all__'

class UserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            UserProfile.objects.update_or_create(user=user, defaults={'role': self.cleaned_data.get('role')})
        return user

    role = forms.ModelChoiceField(queryset=CustomRole.objects.all(), required=False)
    class Meta: 
        model = User
        fields = ['username', 'password', 'email', 'first_name', 'last_name']

class UserEditForm(forms.ModelForm):
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            UserProfile.objects.update_or_create(user=user, defaults={'role': self.cleaned_data.get('role')})
        return user

    role = forms.ModelChoiceField(queryset=CustomRole.objects.all(), required=False)
    class Meta: 
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
from .models import Employee

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['company', 'name', 'father_name', 'cnic', 'contact_number', 'doj', 'dob', 'address', 'department', 'designation', 'location', 'image']
        widgets = {
            'doj': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
            'dob': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
            'address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control form-control-sm'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'image':
                field.widget.attrs.update({'class': 'form-control form-control-sm'})
