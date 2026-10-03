from django.shortcuts import render


class RolePermissionMiddleware:
    """Check module permissions before a view reads or changes business data."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = request.user
        if not user.is_authenticated or user.is_superuser:
            return None
        name = request.resolver_match.url_name or ''
        if name in {'login', 'logout'} or request.path.startswith('/admin/'):
            return None
        profile = getattr(user, 'profile', None)
        permissions = profile.role.permissions if profile and profile.role else {}

        def permits(module, action='view'):
            entry = permissions.get(module, {})
            if isinstance(entry, bool):
                entry = {'view': entry}
            return isinstance(entry, dict) and entry.get('view') and (action == 'view' or entry.get(action))

        def deny():
            return render(request, 'operations/access_denied.html', status=403)

        if request.path.startswith(('/users/', '/roles/', '/employees/')):
            return deny()
        module = {'':'dashboard', 'crm':'crm', 'complaints':'complaints', 'tasks':'tasks',
            'maintenance':'maintenance', 'invoices':'invoices', 'quotations':'quotations',
            'dc':'dc', 'inventory':'inventory', 'finance':'finance', 'reports':'reports'}.get(request.path.strip('/').split('/')[0])
        if request.path.startswith('/ajax/'):
            lookup_modules = {
                'ajax_get_client_invoices': ('invoices', 'finance'),
                'ajax_get_all_client_invoices': ('invoices', 'complaints', 'maintenance'),
                'ajax_get_invoice_items': ('invoices',),
                'ajax_get_quotation_items': ('quotations', 'invoices', 'dc'),
                'ajax_get_client_expenses': ('finance', 'complaints', 'maintenance'),
                'ajax_get_client_contracts': ('maintenance',),
                'ajax_get_inventory_by_category': ('inventory', 'invoices', 'quotations', 'dc'),
                'ajax_get_tax_rates': ('invoices', 'quotations'),
                'ajax_add_client': ('crm', 'invoices', 'quotations', 'complaints', 'maintenance', 'finance', 'dc'),
            }
            action = 'add' if name == 'ajax_add_client' else 'view'
            return None if any(permits(key, action) for key in lookup_modules.get(name, ())) else deny()
        action = 'view'
        if name.startswith('delete_'):
            action = 'delete'
        elif name.startswith(('edit_', 'approve_', 'save_')):
            action = 'edit'
        elif name.startswith(('add_', 'create_')):
            action = 'add'
        elif request.method == 'POST':
            action = 'edit' if any(key in request.POST for key in ('update_status', 'update_lead', 'close_task', 'add_activity')) else 'add'
        if not permits(module, action):
            return deny()
