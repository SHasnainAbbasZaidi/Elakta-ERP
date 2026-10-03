from datetime import date, timedelta
from django.contrib import messages
from django.utils import timezone


def date_range(request, default='all'):
    mode = request.GET.get('filter', 'custom' if request.GET.get('start_date') or request.GET.get('end_date') else default)
    mode = {'all_time':'all', 'all-time':'all', 'all time':'all'}.get(mode.lower(), mode.lower())
    today = timezone.localdate()
    if mode == 'all': return 'all', None, None
    if mode in ('today', 'week', 'month'):
        return mode, today - timedelta(days={'today':0, 'week':6, 'month':29}[mode]), today
    try:
        start = date.fromisoformat(request.GET['start_date']) if request.GET.get('start_date') else None
        end = date.fromisoformat(request.GET['end_date']) if request.GET.get('end_date') else None
        if start and end and start > end: raise ValueError
        if mode != 'custom': raise ValueError
        return 'custom', start, end
    except ValueError:
        messages.error(request, 'Choose a valid date range with the start before the end.')
        return 'custom', today, today


def filter_dates(queryset, field, start, end):
    if start: queryset = queryset.filter(**{field+'__gte':start})
    if end: queryset = queryset.filter(**{field+'__lte':end})
    return queryset
