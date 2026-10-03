from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

DEFAULT_TERMS = """Payment is due within 30 days of the invoice date.\n\nWARRANTY:\nWe offer one year manufacturerâ€™s warranty on all equipment at the normal condition and 90 days of labor services, parts, and technical support..."""
DEFAULT_QUOTATION_TERMS = """Prices are Exclusive of all Gov Taxes.\nPrice Validity: 15 days\nDelivery Time of Import Items is at least 90 Days..."""

class CustomRole(models.Model):
    name = models.CharField(max_length=100, unique=True)
    permissions = models.JSONField(default=dict)
    def __str__(self): return self.name

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.ForeignKey(CustomRole, on_delete=models.SET_NULL, null=True, blank=True)
    def __str__(self): return f"{self.user.username} Profile"

class CompanyProfile(models.Model):
    name = models.CharField(max_length=200)
    company_code = models.CharField(max_length=10, unique=True, help_text="e.g. ET for Elakta Technologies")
    address = models.TextField()
    contact_number = models.CharField(max_length=50)
    ntn = models.CharField(max_length=50, blank=True)
    logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    def __str__(self): return f"{self.name} ({self.company_code})"

class Client(models.Model):
    name = models.CharField(max_length=150)
    company_name = models.CharField(max_length=150, blank=True)
    contact = models.CharField(max_length=50)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    def __str__(self): return f"{self.name} - {self.company_name}"

class Vendor(models.Model):
    name = models.CharField(max_length=150)
    contact = models.CharField(max_length=100, blank=True)
    def __str__(self): return self.name

class Technician(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    def __str__(self): return self.name

class ItemLocation(models.Model): name = models.CharField(max_length=100)
class ItemUnit(models.Model): name = models.CharField(max_length=50)
class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.name

class TaxRate(models.Model):
    name = models.CharField(max_length=50, help_text="e.g., GST, SST")
    rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage e.g., 18.00")
    def __str__(self): return f"{self.name} ({self.rate}%)"

# --- ADVANCED CRM MODULE ---
class CRMLead(models.Model):
    STATUS_CHOICES = (('New', 'New'), ('Follow-Up', 'Follow-Up'), ('Converted', 'Converted'), ('Lost', 'Lost'))
    PRIORITY_CHOICES = (('High', 'ðŸ”¥ High'), ('Medium', 'Medium'), ('Low', 'Low'))

    lead_id = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    lead_source = models.CharField(max_length=100, blank=True)
    campaign = models.CharField(max_length=150, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='New')
    company_name = models.CharField(max_length=150, blank=True)
    client_name = models.CharField(max_length=150, verbose_name="Contact Person")
    contact = models.CharField(max_length=50, verbose_name="Mobile")
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    product_category = models.CharField(max_length=150, blank=True)
    quantity = models.IntegerField(default=1)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    project_details = models.TextField(blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='crm_created')
    next_follow_up = models.DateField(null=True, blank=True)
    reminder = models.BooleanField(default=False)
    follow_up_remarks = models.TextField(blank=True)
    decision_maker = models.CharField(max_length=150, blank=True)
    timeline = models.CharField(max_length=100, blank=True)
    probability = models.IntegerField(default=10, help_text="Percentage 0-100")
    opportunity_id = models.CharField(max_length=50, blank=True, null=True)
    expected_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_date = models.DateField(null=True, blank=True)
    sales_stage = models.CharField(max_length=100, blank=True)
    linked_quotation = models.ForeignKey('Quotation', on_delete=models.SET_NULL, null=True, blank=True)
    lost_remarks = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.lead_id:
            date_str = timezone.now().strftime('%y%m')
            last = CRMLead.objects.order_by('id').last()
            seq = (last.id + 1) if last else 1
            self.lead_id = f"LD-{date_str}-{seq:04d}"
        if not self.opportunity_id:
            date_str = timezone.now().strftime('%y%m')
            last = CRMLead.objects.order_by('id').last()
            seq = (last.id + 1) if last else 1
            self.opportunity_id = f"OPP-{date_str}-{seq:04d}"
        super().save(*args, **kwargs)

    def __str__(self): return f"{self.client_name} ({self.status})"

class CRMActivityLog(models.Model):
    ACTIVITY_TYPES = (('Call', 'Call'), ('Meeting', 'Meeting'), ('WhatsApp', 'WhatsApp'), ('Email', 'Email'), ('Site Visit', 'Site Visit'))
    lead = models.ForeignKey(CRMLead, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    date_time = models.DateTimeField(default=timezone.now)
    remarks = models.TextField()
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

# --- CORE MODULES ---
class InventoryItem(models.Model):
    item_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    category = models.CharField(max_length=150, blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    qty = models.IntegerField(default=0)
    unit = models.ForeignKey(ItemUnit, on_delete=models.SET_NULL, null=True, blank=True)
    location = models.ForeignKey(ItemLocation, on_delete=models.SET_NULL, null=True, blank=True)
    purchase_source = models.CharField(max_length=20, choices=(('Vendor', 'Vendor'), ('Direct', 'Local')), default='Vendor')
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    dp_shop_name = models.CharField(max_length=150, blank=True, help_text="If Direct Purchase")
    avg_unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        if not self.item_code and self.category:
            prefix = self.category.strip().split()[0][:3].upper()
            existing_items = InventoryItem.objects.filter(item_code__startswith=prefix)
            max_seq = 0
            for item in existing_items:
                if item.item_code:
                    num_str = item.item_code.replace(prefix, '')
                    if num_str.isdigit(): max_seq = max(max_seq, int(num_str))
            seq = max_seq + 1
            new_code = f"{prefix}{seq:02d}"
            while InventoryItem.objects.filter(item_code=new_code).exists():
                seq += 1; new_code = f"{prefix}{seq:02d}"
            self.item_code = new_code
        super().save(*args, **kwargs)

class InventoryLog(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='logs')
    date = models.DateTimeField(default=timezone.now)
    action = models.CharField(max_length=255)
    qty_change = models.IntegerField()

class Invoice(models.Model):
    TAX_TYPE_CHOICES = (('Item', 'Item Wise'), ('Global', 'Complete Invoice'), ('None', 'No Tax'))
    company = models.ForeignKey(CompanyProfile, on_delete=models.SET_NULL, null=True)
    invoice_number = models.CharField(max_length=50, unique=True, blank=True)
    date = models.DateField(default=timezone.now)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    sub_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_type = models.CharField(max_length=20, choices=TAX_TYPE_CHOICES, default='None')
    global_tax = models.ForeignKey(TaxRate, on_delete=models.SET_NULL, null=True, blank=True)
    total_tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    terms_conditions = models.TextField(default=DEFAULT_TERMS)

    def save(self, *args, **kwargs):
        if not self.invoice_number and self.company:
            date_str = timezone.now().strftime('%d%m%y')
            code = self.company.company_code
            last_i = Invoice.objects.filter(company=self.company).order_by('id').last()
            seq = (int(last_i.invoice_number[-5:]) + 1) if last_i and last_i.invoice_number else 1
            self.invoice_number = f"{date_str}{code}{seq:05d}"
        super().save(*args, **kwargs)

class InvoiceItem(models.Model):
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True, blank=True)
    item_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    qty = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50, blank=True, null=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    item_tax = models.ForeignKey(TaxRate, on_delete=models.SET_NULL, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)

class Quotation(models.Model):
    TAX_TYPE_CHOICES = (('Item', 'Item Wise'), ('Global', 'Complete Invoice'), ('None', 'No Tax'))
    company = models.ForeignKey(CompanyProfile, on_delete=models.SET_NULL, null=True)
    quotation_number = models.CharField(max_length=50, unique=True, blank=True)
    date = models.DateField(default=timezone.now)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    sub_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_type = models.CharField(max_length=20, choices=TAX_TYPE_CHOICES, default='None')
    global_tax = models.ForeignKey(TaxRate, on_delete=models.SET_NULL, null=True, blank=True)
    total_tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    terms_conditions = models.TextField(default=DEFAULT_QUOTATION_TERMS)
    validity_days = models.IntegerField(default=15)
    is_approved = models.BooleanField(default=False)
    is_revised = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.quotation_number and self.company:
            date_str = timezone.now().strftime('%d%m%y')
            code = self.company.company_code
            last_q = Quotation.objects.filter(company=self.company).exclude(quotation_number__contains='-R').order_by('id').last()
            seq = (int(last_q.quotation_number[-5:]) + 1) if last_q and last_q.quotation_number else 1
            self.quotation_number = f"{date_str}{code}Q{seq:05d}"
        super().save(*args, **kwargs)

class QuotationItem(models.Model):
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='items')
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True, blank=True)
    item_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    qty = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50, blank=True, null=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    item_tax = models.ForeignKey(TaxRate, on_delete=models.SET_NULL, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)

class DeliveryChallan(models.Model):
    company = models.ForeignKey(CompanyProfile, on_delete=models.SET_NULL, null=True)
    dc_number = models.CharField(max_length=50, unique=True, blank=True)
    date = models.DateField(default=timezone.now)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    delivered_by = models.CharField(max_length=150, blank=True, null=True)
    site_project = models.CharField(max_length=200, blank=True)
    total_qty = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.dc_number:
            date_str = timezone.now().strftime('%d%m%y')
            last_dc = DeliveryChallan.objects.filter(dc_number__startswith=f"{date_str}-DC").order_by('id').last()
            self.dc_number = f"{date_str}-DC{(int(last_dc.dc_number.split('-DC')[-1]) + 1) if last_dc else 1:06d}"
        super().save(*args, **kwargs)

class DeliveryChallanItem(models.Model):
    dc = models.ForeignKey(DeliveryChallan, on_delete=models.CASCADE, related_name='items')
    source = models.CharField(max_length=20, choices=(('Inventory', 'Inventory'), ('Direct', 'Direct Purchase')))
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True, blank=True)
    custom_item_name = models.CharField(max_length=200, blank=True)
    custom_item_description = models.TextField(blank=True)
    qty = models.IntegerField(default=1)

class FinanceBill(models.Model):
    CATEGORY_CHOICES = (('Invoice Payment', 'Invoice Payment'), ('Cash Bill', 'Cash Bill'), ('Expense', 'Expense'), ('Purchase', 'Purchase'), ('Vendor Payment', 'Vendor Payment'), ('Other', 'Other'))
    company = models.ForeignKey(CompanyProfile, on_delete=models.SET_NULL, null=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    custom_category = models.CharField(max_length=150, blank=True)
    date = models.DateField(default=timezone.now)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    custom_vendor = models.CharField(max_length=150, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    receipt_image = models.ImageField(upload_to='receipts/', blank=True, null=True)
    linked_invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    bank_name = models.CharField(max_length=150, blank=True)
    reference_number = models.CharField(max_length=150, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    person_name = models.CharField(max_length=150, blank=True)
    vendor_invoice_number = models.CharField(max_length=100, blank=True)
    remarks = models.TextField(blank=True)
    payment_method = models.CharField(max_length=50, choices=(('Cash', 'Cash'), ('FT', 'Fund Transfer (FT)'), ('Cheque', 'Cheque')), blank=True)
    payment_status = models.CharField(max_length=20, choices=(('Paid', 'Paid'), ('Pending', 'Pending'), ('Partial', 'Partial')), blank=True)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, blank=True)

class FinanceBillItem(models.Model):
    bill = models.ForeignKey(FinanceBill, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=255)
    qty = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

class Complaint(models.Model):
    STATUS_CHOICES = (('Open', 'Open'), ('Pending', 'Pending'), ('Closed', 'Closed'))
    company = models.ForeignKey(CompanyProfile, on_delete=models.SET_NULL, null=True, blank=True)
    complaint_number = models.CharField(max_length=50, unique=True, blank=True)
    issue_description = models.CharField(max_length=255)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    date_time = models.DateTimeField(default=timezone.now)
    technicians = models.ManyToManyField(Technician, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    linked_invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    linked_expense = models.ForeignKey(FinanceBill, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.complaint_number and self.company:
            date_str = timezone.now().strftime('%d%m%y')
            prefix = f"{date_str}-{self.company.company_code}"
            last_c = Complaint.objects.filter(complaint_number__startswith=prefix).order_by('id').last()
            seq = (int(last_c.complaint_number.split(prefix)[-1]) + 1) if last_c else 1
            self.complaint_number = f"{prefix}{seq:04d}"
        super().save(*args, **kwargs)

class ComplaintRemark(models.Model):
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='tracking_remarks')
    date_time = models.DateTimeField(default=timezone.now)
    remark = models.TextField()
    status_changed_to = models.CharField(max_length=20, blank=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

class DailyTask(models.Model):
    TASK_TYPES = (('Invoice', 'Invoice'), ('Quotation', 'Quotation'), ('Reminder', 'Reminder'), ('Other', 'Other'))
    task_type = models.CharField(max_length=50, choices=TASK_TYPES, default='Reminder')
    custom_task_type = models.CharField(max_length=100, blank=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tasks', null=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    date_time = models.DateTimeField(default=timezone.now)
    task_details = models.TextField(blank=True)
    is_open = models.BooleanField(default=True)
    close_remarks = models.TextField(blank=True)

class MaintenanceContract(models.Model):
    FREQUENCY_CHOICES = (('15', 'Every 15 Days'), ('30', 'Every 30 Days'), ('90', 'Every 3 Months'), ('180', 'Every 6 Months'), ('365', 'Yearly'))
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    company = models.ForeignKey(CompanyProfile, on_delete=models.SET_NULL, null=True, blank=True)
    locations = models.CharField(max_length=255, blank=True, help_text="e.g. Head Office, Branch 1")
    start_date = models.DateField()
    end_date = models.DateField()
    visit_frequency_days = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    charges = models.DecimalField(max_digits=10, decimal_places=2)
    terms_conditions = models.TextField(default="1. Services will be provided as per schedule...")

class MaintenanceContractJob(models.Model):
    contract = models.ForeignKey(MaintenanceContract, on_delete=models.CASCADE, related_name='jobs')
    description = models.CharField(max_length=255)

class ServiceVisit(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    contract = models.ForeignKey(MaintenanceContract, on_delete=models.SET_NULL, null=True, blank=True)
    service_date = models.DateField(default=timezone.now)
    technician = models.ForeignKey(Technician, on_delete=models.SET_NULL, null=True, blank=True)
    remarks = models.TextField(blank=True)
    work_performed_doc = models.ImageField(upload_to='maintenance_docs/', blank=True, null=True)
    linked_invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    linked_expense = models.ForeignKey(FinanceBill, on_delete=models.SET_NULL, null=True, blank=True)

# --- HR & EMPLOYEE MODULE ---
class JobCardTemplate(models.Model):
    name = models.CharField(max_length=100, default="Default Job Card")
    background_image = models.ImageField(upload_to='job_cards/', help_text="Front Background (54mm x 86mm)")
    back_background_image = models.ImageField(upload_to='job_cards/', null=True, blank=True, help_text="Backside Background (54mm x 86mm)")
    layout_config = models.JSONField(default=dict, blank=True, help_text="Stores dynamic X/Y coords and font sizes")
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name

class Employee(models.Model):
    company = models.ForeignKey(CompanyProfile, on_delete=models.SET_NULL, null=True, blank=True)
    employee_id = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField(max_length=150, verbose_name="Employee Name")
    father_name = models.CharField(max_length=150, blank=True)
    cnic = models.CharField(max_length=20, blank=True, verbose_name="CNIC")
    contact_number = models.CharField(max_length=50)
    doj = models.DateField(null=True, blank=True, verbose_name="Date of Joining")
    dob = models.DateField(null=True, blank=True, verbose_name="Date of Birth")
    address = models.TextField(blank=True)
    department = models.CharField(max_length=100, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=150, blank=True, verbose_name="Current Location")
    image = models.ImageField(upload_to='employee_images/', blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.employee_id:
            last = Employee.objects.order_by('id').last()
            seq = (last.id + 1) if last else 1
            self.employee_id = f"ET-E{seq:04d}"
        super().save(*args, **kwargs)

    def __str__(self): return f"{self.name} ({self.employee_id})"


class AttendanceDevice(models.Model):
    name = models.CharField(max_length=100)
    protocol = models.CharField(max_length=20, choices=[('dahua', 'Dahua HTTP CGI'), ('zk', 'ZKTeco / ZK protocol'), ('csv', 'CSV export / other device')])
    host = models.GenericIPAddressField(null=True, blank=True)
    port = models.PositiveIntegerField(default=80)
    username = models.CharField(max_length=100, blank=True)
    use_https = models.BooleanField(default=False)
    force_udp = models.BooleanField(default=False)
    timezone_name = models.CharField(max_length=60, default='Asia/Karachi')
    last_sync = models.DateTimeField(null=True, blank=True)

    def __str__(self): return self.name


class AttendanceMapping(models.Model):
    device = models.ForeignKey(AttendanceDevice, on_delete=models.CASCADE, related_name='mappings')
    device_user_id = models.CharField(max_length=100)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['device', 'device_user_id'], name='unique_attendance_mapping')]


class AttendancePunch(models.Model):
    device = models.ForeignKey(AttendanceDevice, on_delete=models.PROTECT)
    device_user_id = models.CharField(max_length=100)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(db_index=True)
    event = models.CharField(max_length=40, default='Unknown')
    fingerprint = models.CharField(max_length=64)

    class Meta:
        ordering = ['-timestamp', '-id']
        constraints = [models.UniqueConstraint(fields=['device', 'fingerprint'], name='unique_attendance_punch')]
