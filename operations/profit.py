from decimal import Decimal, ROUND_HALF_UP


def document_profit(document):
    lines = list(document.items.all())
    missing = sum(line.unit_cost is None for line in lines)
    revenue = document.sub_total - document.discount
    cost = sum((line.qty * line.unit_cost for line in lines if line.unit_cost is not None), Decimal('0')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    profit = None if missing or not lines else revenue - cost
    return {'net_sales': revenue, 'cost': cost, 'profit': profit,
        'margin': profit / revenue * 100 if profit is not None and revenue else None,
        'missing_costs': missing, 'complete': profit is not None}
