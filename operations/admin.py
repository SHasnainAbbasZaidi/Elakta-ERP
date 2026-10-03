from django.contrib import admin
from .models import (JobCardTemplate, CompanyProfile, Client, Vendor, Technician, ItemLocation, ItemUnit, TaxRate, CRMLead,
                     InventoryItem, InventoryLog, Invoice, InvoiceItem, Quotation, QuotationItem,
                     Complaint, ComplaintRemark, DailyTask, MaintenanceContract, MaintenanceContractJob,
                     ServiceVisit, DeliveryChallan, DeliveryChallanItem, FinanceBill, FinanceBillItem,
                     CustomRole, UserProfile)

admin.site.register(CompanyProfile)
admin.site.register(Client)
admin.site.register(Vendor)
admin.site.register(Technician)
admin.site.register(ItemLocation)
admin.site.register(ItemUnit)
admin.site.register(TaxRate)
admin.site.register(CRMLead)
admin.site.register(InventoryItem)
admin.site.register(InventoryLog)
admin.site.register(Invoice)
admin.site.register(InvoiceItem)
admin.site.register(Quotation)
admin.site.register(QuotationItem)
admin.site.register(Complaint)
admin.site.register(ComplaintRemark)
admin.site.register(DailyTask)
admin.site.register(MaintenanceContract)
admin.site.register(MaintenanceContractJob)
admin.site.register(ServiceVisit)
admin.site.register(DeliveryChallan)
admin.site.register(DeliveryChallanItem)
admin.site.register(FinanceBill)
admin.site.register(FinanceBillItem)
admin.site.register(CustomRole)
admin.site.register(UserProfile)
admin.site.register(JobCardTemplate)

admin.site.site_header = "Elakta ERP Administration"
admin.site.site_title = "Elakta ERP"
admin.site.index_title = "Business administration"
