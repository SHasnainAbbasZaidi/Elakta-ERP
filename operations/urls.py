from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
path('attendance/', views.attendance_home, name='attendance'),
path('attendance/devices/add/', views.attendance_device_form, name='attendance_device_add'),
path('attendance/devices/<int:id>/', views.attendance_device, name='attendance_device'),
path('attendance/devices/<int:id>/edit/', views.attendance_device_form, name='attendance_device_edit'),
path('login/', auth_views.LoginView.as_view(template_name='operations/login.html'), name='login'),
path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
path('', views.dashboard, name='dashboard'),

# AJAX Utilities
path('ajax/add-client/', views.ajax_add_client, name='ajax_add_client'),
path('ajax/get-inventory-by-category/', views.ajax_get_inventory_by_category, name='ajax_get_inventory_by_category'),
path('ajax/get-client-invoices/', views.ajax_get_client_invoices, name='ajax_get_client_invoices'),
path('ajax/get-all-client-invoices/', views.ajax_get_all_client_invoices, name='ajax_get_all_client_invoices'),
path('ajax/get-client-expenses/', views.ajax_get_client_expenses, name='ajax_get_client_expenses'),
path('ajax/get-client-contracts/', views.ajax_get_client_contracts, name='ajax_get_client_contracts'),
path('ajax/get-tax-rates/', views.ajax_get_tax_rates, name='ajax_get_tax_rates'),
path('ajax/get-invoice-items/<int:id>/', views.ajax_get_invoice_items, name='ajax_get_invoice_items'),
path('ajax/get-quotation-items/<int:id>/', views.ajax_get_quotation_items, name='ajax_get_quotation_items'),

# Advanced CRM
path('crm/', views.crm_list, name='crm_list'),
path('crm/lead/<int:id>/', views.crm_lead_detail, name='crm_lead_detail'),

# Complaints
path('complaints/', views.complaints_manager, name='complaints'),
path('complaints/detail/<int:id>/', views.complaint_detail, name='complaint_detail'),
path('complaints/delete/<int:id>/', views.delete_complaint, name='delete_complaint'),
path('complaints/print/<int:complaint_id>/', views.print_complaint, name='print_complaint'),

# Tasks
path('tasks/', views.daily_tasks, name='daily_tasks'),
path('tasks/edit/<int:id>/', views.edit_task, name='edit_task'),
path('tasks/delete/<int:id>/', views.delete_task, name='delete_task'),

# Maintenance
path('maintenance/', views.maintenance_dashboard, name='maintenance'),
path('maintenance/add-contract/', views.add_contract, name='add_contract'),
path('maintenance/contract/<int:id>/', views.contract_detail, name='contract_detail'),
path('maintenance/contract/edit/<int:id>/', views.edit_contract, name='edit_contract'),
path('maintenance/contract/delete/<int:id>/', views.delete_contract, name='delete_contract'),
path('maintenance/print-contract/<int:contract_id>/', views.print_contract, name='print_contract'),
path('maintenance/add-service/', views.add_service, name='add_service'),
path('maintenance/service-detail/<int:visit_id>/', views.service_visit_detail, name='service_visit_detail'),
path('maintenance/print-service/<int:visit_id>/', views.print_service, name='print_service'),

# Invoices & Quotations
path('invoices/', views.invoice_list, name='invoice_list'),
path('invoices/create/', views.create_invoice, name='create_invoice'),
path('invoices/edit/<int:id>/', views.edit_invoice, name='edit_invoice'),
path('invoices/delete/<int:id>/', views.delete_invoice, name='delete_invoice'),
path('invoices/print/<int:invoice_id>/', views.print_invoice, name='print_invoice'),

path('quotations/', views.quotation_list, name='quotation_list'),
path('quotations/create/', views.create_quotation, name='create_quotation'),
path('quotations/edit/<int:id>/', views.edit_quotation, name='edit_quotation'),
path('quotations/delete/<int:id>/', views.delete_quotation, name='delete_quotation'),
path('quotations/approve/<int:id>/', views.approve_quotation, name='approve_quotation'),
path('quotations/print/<int:quote_id>/', views.print_quotation, name='print_quotation'),

# Inventory & DC
path('inventory/', views.inventory_list, name='inventory_list'),
path('inventory/history/<int:id>/', views.inventory_history, name='inventory_history'),
path('inventory/edit/<int:id>/', views.edit_inventory, name='edit_inventory'),
path('inventory/add/', views.add_inventory, name='add_inventory'),
path('inventory/print/', views.print_inventory, name='print_inventory'),

path('dc/', views.dc_list, name='dc_list'),
path('dc/create/', views.create_dc, name='create_dc'),
path('dc/edit/<int:id>/', views.edit_dc, name='edit_dc'),
path('dc/delete/<int:id>/', views.delete_dc, name='delete_dc'),
path('dc/print/<int:dc_id>/', views.print_dc, name='print_dc'),

# Finance
path('finance/ledgers/', views.ledger_index, name='ledger_index'),
path('finance/ledgers/<str:kind>/<int:id>/', views.entity_ledger, name='entity_ledger'),
path('finance/', views.finance_list, name='finance_list'),
path('finance/add/', views.add_finance, name='add_finance'),
path('finance/detail/<int:id>/', views.finance_detail, name='finance_detail'),
path('finance/edit/<int:id>/', views.edit_finance, name='edit_finance'),
path('finance/delete/<int:id>/', views.delete_finance, name='delete_finance'),
path('finance/receipt/print/<int:receipt_id>/', views.print_receipt, name='print_receipt'),

# Reports & Users
path('reports/', views.reports_dashboard, name='reports'),
path('users/', views.user_list, name='user_list'),
path('users/add/', views.add_user, name='add_user'),
path('users/edit/<int:id>/', views.edit_user, name='edit_user'),
path('users/delete/<int:id>/', views.delete_user, name='delete_user'),
path('users/add-company/', views.add_company, name='add_company'),
path('roles/', views.role_list, name='role_list'),
path('roles/create/', views.create_role, name='create_role'),
path('roles/edit/<int:id>/', views.edit_role, name='edit_role'),
# Employees
path('employees/', views.employee_list, name='employee_list'),
path('employees/add/', views.add_employee, name='add_employee'),
path('employees/detail/<int:id>/', views.employee_detail, name='employee_detail'),
path('employees/edit/<int:id>/', views.edit_employee, name='edit_employee'),
path('employees/delete/<int:id>/', views.delete_employee, name='delete_employee'),
path('employees/job-card/<int:id>/', views.print_job_card, name='print_job_card'),
path('employees/job-card/save-layout/<int:template_id>/', views.save_job_card_layout, name='save_job_card_layout'),
]
