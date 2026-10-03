"""Entity subledgers derived from documents; positive balance means payable to us/by us."""
from decimal import Decimal
from django.db.models import Q
from django.urls import reverse
from .models import Invoice, FinanceBill

ZERO = Decimal('0')

def entity_entries(kind, entity):
    entries = []
    if kind == 'client':
        for inv in Invoice.objects.filter(client=entity):
            entries.append(dict(date=inv.date, order=(0, inv.pk), reference=inv.invoice_number,
                description='Invoice', amount=inv.grand_total, debit=inv.grand_total, credit=ZERO,
                status='Posted', method='', remarks='', url=reverse('print_invoice', args=[inv.pk])))
        bills = FinanceBill.objects.filter(Q(linked_invoice__client=entity) | Q(linked_invoice__isnull=True, client=entity))
    else:
        bills = FinanceBill.objects.filter(vendor=entity)
    for bill in bills.select_related('linked_invoice'):
        debit = credit = ZERO
        if kind == 'client' and bill.category == 'Invoice Payment' and bill.payment_status == 'Paid':
            credit = bill.amount
        elif kind == 'vendor' and bill.category == 'Purchase':
            credit = bill.amount
        elif kind == 'vendor' and bill.category == 'Vendor Payment' and bill.payment_status == 'Paid':
            debit = bill.amount
        entries.append(dict(date=bill.date, order=(1,bill.pk), reference=bill.reference_number or f'FIN-{bill.pk}',
            description=bill.category + (f' Â· {bill.linked_invoice.invoice_number}' if bill.linked_invoice else ''),
            amount=bill.amount, debit=debit, credit=credit, status=bill.payment_status or 'Unspecified',
            method=' · '.join(filter(None, [bill.payment_method, bill.bank_name, str(bill.cheque_date or '')])), remarks=' · '.join(filter(None, [bill.vendor_invoice_number, bill.person_name, bill.remarks])), url=reverse('finance_detail', args=[bill.pk])))
    return sorted(entries, key=lambda e: (e['date'], e['order']))

def ledger_data(kind, entity, start=None, end=None):
    opening = ZERO
    rows = []
    balance = ZERO
    for entry in entity_entries(kind, entity):
        if end and entry['date'] > end:
            continue
        delta = entry['debit'] - entry['credit']
        if kind == 'vendor': delta = -delta
        balance += delta
        if start and entry['date'] < start:
            opening += delta
        else:
            rows.append(dict(entry, balance=balance))
    return dict(rows=rows, opening=opening, closing=balance,
        debits=sum((r['debit'] for r in rows),ZERO), credits=sum((r['credit'] for r in rows),ZERO))
