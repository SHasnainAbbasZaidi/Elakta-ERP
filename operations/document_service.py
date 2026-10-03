"""Validate document lines and calculate money on the server."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from .models import Client, InventoryItem, TaxRate

CENT = Decimal('0.01')

def money(value):
    try:
        amount = Decimal(str(value or '0'))
        if not amount.is_finite() or amount < 0 or amount > Decimal('9999999999.99'):
            raise ValueError
        return amount.quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ValidationError('Enter a valid, non-negative amount.')

def get_client(data):
    value = data.get('client_select', '').strip()
    if not value:
        raise ValidationError('Select or enter a customer.')
    if value.isdigit():
        client = Client.objects.filter(pk=value).first()
        if client is None:
            raise ValidationError('The selected customer no longer exists.')
        return client
    if len(value) > 150:
        raise ValidationError('Customer names must be 150 characters or fewer.')
    return Client.objects.create(name=value, contact=data.get('new_client_contact', ''),
        address=data.get('new_client_address', ''), company_name=data.get('new_client_company', ''))

def save_lines(data, document, model, parent_field):
    def cell(key, index, default=''):
        values = data.getlist(key + '[]')
        return values[index] if index < len(values) else default
    rows = []
    subtotal = tax_total = Decimal('0')
    for index, name in enumerate(data.getlist('item_name[]')):
        if not name.strip():
            continue
        qty = money(cell('qty', index, '1'))
        price = money(cell('price', index, '0'))
        if qty <= 0 or qty > Decimal('99999999.99') or price > Decimal('99999999.99'):
            raise ValidationError('Enter a positive quantity and a valid unit price.')
        if len(name.strip()) > 255:
            raise ValidationError('Item names must be 255 characters or fewer.')
        inventory_id = cell('inventory_item_id', index)
        inventory = InventoryItem.objects.filter(pk=inventory_id).first() if inventory_id.isdigit() else None
        entered_cost = cell('unit_cost', index)
        unit_cost = money(entered_cost) if entered_cost.strip() else (inventory.avg_unit_cost if inventory and 'unit_cost[]' not in data else None)
        if unit_cost is not None and unit_cost > Decimal('99999999.99'):
            raise ValidationError('Unit cost is too large.')
        tax_id = cell('item_tax', index)
        tax = TaxRate.objects.filter(pk=tax_id).first() if tax_id.isdigit() else None
        base = money(qty * price)
        tax_amount = money(base * tax.rate / 100) if tax and document.tax_type == 'Item' else Decimal('0')
        subtotal += base
        tax_total += tax_amount
        rows.append(model(**{parent_field: document}, item_name=name.strip(),
            description=cell('description', index), qty=qty, unit=cell('unit', index),
            unit_price=price, unit_cost=unit_cost, inventory_item=inventory, item_tax=tax,
            tax_amount=tax_amount, total=money(base + tax_amount)))
    if not rows:
        raise ValidationError('Add at least one item.')
    discount = money(document.discount)
    if discount > subtotal:
        raise ValidationError('Discount cannot exceed the subtotal.')
    if document.tax_type == 'Global':
        if not document.global_tax:
            raise ValidationError('Select a global tax rate.')
        tax_total = money((subtotal - discount) * document.global_tax.rate / 100)
    document.sub_total = money(subtotal)
    document.total_tax_amount = money(tax_total)
    document.grand_total = money(subtotal - discount + tax_total)
    document.save()
    document.items.all().delete()
    model.objects.bulk_create(rows)
