"""Read-only page checks against the configured local database."""
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.template.loader import get_template
from pathlib import Path

for template in Path('operations/templates').rglob('*.html'):
    get_template(template.relative_to('operations/templates').as_posix())
print('All templates compiled.')

client = Client(HTTP_HOST='localhost')
assert client.get('/').status_code == 302
assert client.get('/login/').status_code == 200
client.force_login(get_user_model().objects.filter(is_superuser=True).first())
paths = [
    '/', '/crm/', '/complaints/', '/tasks/', '/maintenance/',
    '/invoices/', '/quotations/', '/dc/', '/inventory/', '/finance/',
    '/reports/', '/users/', '/roles/', '/employees/',
    '/invoices/create/', '/quotations/create/', '/dc/create/',
    '/inventory/add/', '/finance/add/', '/employees/add/',
    '/maintenance/add-contract/', '/maintenance/add-service/',
    '/users/add/', '/users/add-company/', '/roles/create/',
]
for path in paths:
    response = client.get(path)
    assert response.status_code == 200, (path, response.status_code)
    print(f'OK {path}')
print(f'Passed {len(paths)} authenticated page checks.')
