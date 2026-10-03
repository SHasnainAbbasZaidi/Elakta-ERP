import csv
from decimal import Decimal
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from operations.models import Client, Vendor, Invoice, Quotation, FinanceBill, InventoryItem, Complaint, CRMLead
from operations.date_filters import date_range, filter_dates
from operations.ledger import ledger_data
from operations.profit import document_profit

def csv_response(title, headers, rows):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{title}.csv"'
    writer = csv.writer(response)
    def safe(value):
        if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
            return "'" + value
        return value
    writer.writerow(headers)
    for row in rows: writer.writerow([safe(v) for v in row])
    return response

@login_required
def ledger_index(request):
    groups = []
    for kind, model in [('client',Client),('vendor',Vendor)]:
        entities = model.objects.order_by('name')
        if request.GET.get('q'): entities = entities.filter(name__icontains=request.GET['q'])
        groups.append((kind, [dict(entity=e, balance=ledger_data(kind,e)['closing']) for e in entities]))
    return render(request, 'operations/ledgers.html', {'groups':groups, 'search_query':request.GET.get('q','')})

@login_required
def entity_ledger(request, kind, id):
    if kind not in ('client','vendor'): raise Http404
    entity = get_object_or_404(Client if kind == 'client' else Vendor, pk=id)
    mode, start, end = date_range(request)
    data = ledger_data(kind, entity, start, end)
    if request.GET.get('export') == 'csv':
        rows = [[start or '', '', 'Opening balance', '', '', '', '', '', '',data['opening']]]
        rows += [[r[k] for k in ('date','reference','description','status','method','remarks','amount','debit','credit','balance')] for r in data['rows']]
        return csv_response(f'{kind}-{id}-ledger', ['Date','Reference','Description','Status','Method','Remarks','Amount','Debit','Credit','Balance'], rows)
    return render(request, 'operations/ledger.html', dict(data, entity=entity, kind=kind,
        filter_type=mode,start_date=start,end_date=end))

REPORTS = [('sales','Sales & profit'),('quotations','Quotation pipeline'),('receivables','Receivables aging'),
    ('payables','Vendor balances'),('inventory','Inventory valuation'),('cash','Cash movements'),('operations','Complaints & operations'),('activity','User activity')]

@login_required
def reports_dashboard(request):
    mode,start,end = date_range(request)
    kind = request.GET.get('report', {'Finance':'cash','Invoices':'sales','Complaints':'operations','User Activity':'activity'}.get(request.GET.get('report_type'),'sales'))
    client_id = request.GET.get('client_id','')
    user_id = request.GET.get('user_id','')
    client_id = client_id if client_id.isdigit() else ''
    user_id = user_id if user_id.isdigit() else ''
    if kind not in dict(REPORTS): kind = 'sales'
    rows = []; summary = {}; note = ''; zero = Decimal('0')
    asof = end or timezone.localdate()
    if kind in ('sales','quotations'):
        model = Invoice if kind == 'sales' else Quotation
        docs = filter_dates(model.objects.select_related('client').prefetch_related('items'), 'date', start,end).order_by('date','pk')
        if client_id: docs = docs.filter(client_id=client_id)
        if user_id: docs = docs.filter(created_by_id=user_id)
        headers = ['Date','Number','Client','Net sales','Tax','Total','Cost','Profit','Margin %','Status']
        net=tax=total=profit=zero; incomplete=0
        for doc in docs:
            p=document_profit(doc); net+=p['net_sales']; tax+=doc.total_tax_amount; total+=doc.grand_total
            if p['complete']: profit+=p['profit']
            else: incomplete+=1
            status = 'Posted' if kind == 'sales' else ('Approved' if doc.is_approved else ('Expired' if doc.date+timedelta(days=doc.validity_days)<timezone.localdate() else 'Pending'))
            rows.append([doc.date,getattr(doc,'invoice_number' if kind=='sales' else 'quotation_number'),doc.client.name,p['net_sales'],doc.total_tax_amount,doc.grand_total,p['cost'] if p['complete'] else 'Incomplete',p['profit'] if p['complete'] else 'Incomplete',round(p['margin'],2) if p['margin'] is not None else '',status])
        summary={'Documents':len(rows),'Net sales':net,'Tax':tax,'Total':total,'Known profit':profit,'Documents missing costs':incomplete}
        note='Profit excludes tax and deducts discounts and saved unit costs. Known profit includes only documents with complete costs.'
    elif kind == 'receivables':
        headers=['Client','Invoice','Date','Age (days)','Invoice amount','Paid as of date','Outstanding','0–30','31–60','61–90','90+']
        total=zero
        invoices = Invoice.objects.filter(date__lte=asof).select_related('client')
        if client_id: invoices = invoices.filter(client_id=client_id)
        if user_id: invoices = invoices.filter(created_by_id=user_id)
        for inv in invoices:
            paid=sum(FinanceBill.objects.filter(linked_invoice=inv,category='Invoice Payment',payment_status='Paid',date__lte=asof).values_list('amount',flat=True),zero)
            balance=max(inv.grand_total-paid,zero)
            if not balance: continue
            age=(asof-inv.date).days; buckets=[zero]*4; buckets[0 if age<=30 else 1 if age<=60 else 2 if age<=90 else 3]=balance
            total+=balance; rows.append([inv.client.name,inv.invoice_number,inv.date,age,inv.grand_total,paid,balance,*buckets])
        summary={'Outstanding invoices':len(rows),'Outstanding':total}
        note=f'As of {asof}; includes all earlier invoices regardless of start date. Aging uses invoice date. Unallocated client credits are visible in ledgers.'
    elif kind == 'payables':
        headers=['Vendor','Purchases','Settled payments','Balance owed']
        total=zero
        for vendor in Vendor.objects.order_by('name'):
            data=ledger_data('vendor',vendor,end=asof); total+=data['closing']
            rows.append([vendor.name,data['credits'],data['debits'],data['closing']])
        summary={'Vendors':len(rows),'Net payable':total}
        note=f'As of {asof}; includes all earlier purchases and settled payments. Purchase-level aging is unavailable because payments are not linked to individual purchases.'
    elif kind == 'inventory':
        headers=['Code','Item','Source','Vendor / shop','Quantity','Unit cost','Stock value','Stock status']; total=zero
        for item in InventoryItem.objects.select_related('vendor').order_by('name'):
            value=item.qty*item.avg_unit_cost; total+=value
            rows.append([item.item_code,item.name,item.get_purchase_source_display(),item.vendor.name if item.vendor else item.dp_shop_name,item.qty,item.avg_unit_cost,value,'Low stock' if item.qty<=5 else 'Available'])
        summary={'Items':len(rows),'Current stock value':total}; note='Current inventory snapshot; date filters do not reconstruct historical stock values. Low stock means 5 units or fewer.'
    elif kind == 'cash':
        headers=['Date','Reference','Category','Client / vendor','Status','Amount','Cash in','Cash out']; incoming=outgoing=zero
        bills = filter_dates(FinanceBill.objects.select_related('client','vendor','linked_invoice__client'),'date',start,end).order_by('date','pk')
        if client_id: bills = bills.filter(Q(linked_invoice__client_id=client_id) | Q(linked_invoice__isnull=True,client_id=client_id))
        for bill in bills:
            settled=bill.payment_status=='Paid'
            credit=bill.amount if settled and bill.category in ('Invoice Payment','Cash Bill') else zero
            debit=bill.amount if settled and bill.category in ('Vendor Payment','Expense') else zero
            incoming+=credit; outgoing+=debit
            entity=bill.linked_invoice.client if bill.linked_invoice else bill.client or bill.vendor
            rows.append([bill.date,bill.reference_number or f'FIN-{bill.pk}',bill.category,entity.name if entity else '',bill.payment_status,bill.amount,credit,debit])
        summary={'Cash in':incoming,'Cash out':outgoing,'Net movement':incoming-outgoing}
        note='Only Paid receipts/payments affect cash. Purchases and Other entries are shown for reference without assuming a cash direction.'
    elif kind == 'activity':
        headers=['User','Invoices','Quotations','Complaints','CRM leads']
        users=User.objects.order_by('username')
        if user_id: users=users.filter(pk=user_id)
        for user in users:
            counts=[]
            for model, field in [(Invoice,'date'),(Quotation,'date'),(Complaint,'date_time__date'),(CRMLead,'created_at__date')]:
                qs=filter_dates(model.objects.filter(created_by=user),field,start,end)
                counts.append(qs.count())
            rows.append([user.username,*counts])
        summary={'Users':len(rows)}
        note='Activity counts use creation/document dates. Client filter does not apply to user activity.'
    else:
        headers=['Date','Client','Status','Description']
        complaints = filter_dates(Complaint.objects.select_related('client'),'date_time__date',start,end).order_by('-date_time')
        if client_id: complaints=complaints.filter(client_id=client_id)
        if user_id: complaints=complaints.filter(created_by_id=user_id)
        for c in complaints:
            rows.append([c.date_time.date(),c.client.name,c.status,str(c)])
        summary={'Complaints':len(rows),'Open':sum(r[2]=='Open' for r in rows),'Closed':sum(r[2]=='Closed' for r in rows)}
    if request.GET.get('export')=='csv': return csv_response(kind,headers,rows)
    return render(request,'operations/reporting.html',dict(clients=Client.objects.order_by('name'),users=User.objects.order_by('username'),client_id=client_id,user_id=user_id,report=kind,reports=REPORTS,headers=headers,rows=rows,summary=summary,note=note,filter_type=mode,start_date=start,end_date=end))
