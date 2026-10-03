"""Read-only device connectors; never write users, clear logs, or control doors."""
import csv
import hashlib
import io
import re
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo
from django.db import transaction
from django.utils import timezone
from .models import AttendanceMapping, AttendancePunch


class AttendanceError(Exception):
    pass


def normalize(user_id, timestamp, event, timezone_name):
    user_id = str(user_id).strip()
    if not user_id or len(user_id) > 100:
        raise AttendanceError('A record has a missing or invalid device user ID.')
    try:
        if isinstance(timestamp, datetime):
            moment = timestamp
        elif str(timestamp).isdigit():
            moment = datetime.fromtimestamp(int(timestamp), dt_timezone.utc)
        else:
            moment = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
        if timezone.is_naive(moment):
            moment = timezone.make_aware(moment, ZoneInfo(timezone_name))
    except (ValueError, OverflowError, OSError):
        raise AttendanceError('Invalid attendance time. Use an ISO date and time.')
    event = str(event or 'Unknown').strip()
    event = {'entry':'In', 'exit':'Out', 'in':'In', 'out':'Out'}.get(event.lower(), event)
    if len(event) > 40:
        raise AttendanceError('An attendance event exceeds 40 characters.')
    return {'device_user_id': user_id, 'timestamp': moment, 'event': event}


def parse_csv(upload, device):
    if upload.size > 5 * 1024 * 1024:
        raise AttendanceError('CSV files must be 5 MB or smaller.')
    try:
        reader = csv.DictReader(io.StringIO(upload.read().decode('utf-8-sig')))
        if not {'user_id', 'timestamp'}.issubset(reader.fieldnames or []):
            raise AttendanceError('CSV requires user_id and timestamp columns; event is optional.')
        records = []
        for number, row in enumerate(reader, start=2):
            if number > 20001:
                raise AttendanceError('Import at most 20,000 records per file.')
            try:
                records.append(normalize(row['user_id'] or '', row['timestamp'] or '', row.get('event'), device.timezone_name))
            except AttendanceError as exc:
                raise AttendanceError(f'Row {number}: {exc}')
        return records
    except (UnicodeDecodeError, csv.Error):
        raise AttendanceError('Upload a UTF-8 CSV file.')


def parse_dahua(text, device):
    fields, rows = {}, {}
    for line in text.splitlines():
        key, separator, value = line.partition('=')
        if not separator:
            continue
        match = re.fullmatch(r'records\[(\d+)\]\.(\w+)', key.strip(), re.I)
        if match:
            rows.setdefault(int(match[1]), {})[match[2].lower()] = value.strip()
        else:
            fields[key.strip().lower()] = value.strip()
    try:
        found = int(fields['found'])
        total = int(fields.get('totalcount', found))
        if found != len(rows) or total < found or found < 0:
            raise ValueError
    except (KeyError, ValueError):
        raise AttendanceError('Device returned an unsupported or incomplete CGI response.')
    records = []
    for row in rows.values():
        if row.get('status') == '0':
            continue
        records.append(normalize(row.get('userid', ''), row.get('createtime', ''), row.get('type'), device.timezone_name))
    return records, found, total


def dahua_records(device, password, start, end, test=False):
    import requests
    from requests.auth import HTTPDigestAuth
    scheme = 'https' if device.use_https else 'http'
    host = f'[{device.host}]' if ':' in device.host else device.host
    endpoint = f'{scheme}://{host}:{device.port}/cgi-bin/recordFinder.cgi'
    intervals = [(int(start.timestamp()), int(end.timestamp()) - 1)]
    records = []
    with requests.Session() as session:
        session.trust_env = False
        session.auth = HTTPDigestAuth(device.username, password)
        requests_made = 0
        while intervals:
            lower, upper = intervals.pop()
            requests_made += 1
            if requests_made > 100:
                raise AttendanceError('Too many records. Sync a smaller date range.')
            try:
                response = session.get(endpoint, params={'action':'find', 'name':'AccessControlCardRec',
                    'StartTime':lower, 'EndTime':upper, 'count':1 if test else 1024},
                    timeout=(5, 20), allow_redirects=False)
                if response.status_code in (401, 403):
                    raise AttendanceError('Authentication failed. Check the device username and password.')
                if response.status_code != 200:
                    raise AttendanceError('Device rejected the CGI request. Confirm this model supports HTTP CGI.')
                if len(response.content) > 5 * 1024 * 1024:
                    raise AttendanceError('Device response is too large. Use a smaller date range.')
                page, found, total = parse_dahua(response.text, device)
            except requests.RequestException:
                raise AttendanceError('Could not reach the device. Check its IP, port, network, and HTTPS certificate.')
            if test:
                return []
            if total > found:
                if lower >= upper:
                    raise AttendanceError('Device truncated records within one second; no records were imported.')
                midpoint = (lower + upper) // 2
                intervals.extend([(lower, midpoint), (midpoint + 1, upper)])
            else:
                records.extend(page)
    return [row for row in records if start <= row['timestamp'] < end]


def zk_records(device, password, start, end, test=False):
    from zk import ZK
    if password and not password.isdigit():
        raise AttendanceError('ZK communication passwords must be numeric.')
    connection = None
    try:
        connection = ZK(device.host, port=device.port, timeout=15, password=int(password or 0),
            force_udp=device.force_udp, ommit_ping=True).connect()
        if test:
            connection.get_firmware_version()
            return []
        rows = [normalize(record.user_id, record.timestamp, str(record.punch), device.timezone_name)
            for record in connection.get_attendance()]
        return [row for row in rows if start <= row['timestamp'] < end]
    except AttendanceError:
        raise
    except Exception:
        raise AttendanceError('ZK connection failed. Check the address, communication password, port, and protocol compatibility.')
    finally:
        if connection:
            try: connection.disconnect()
            except Exception: pass


def fetch_records(device, password, start, end, test=False):
    if device.protocol == 'dahua':
        return dahua_records(device, password, start, end, test)
    if device.protocol == 'zk':
        return zk_records(device, password, start, end, test)
    raise AttendanceError('This device uses CSV import; it has no network connection.')


@transaction.atomic
def store_records(device, records):
    mappings = dict(AttendanceMapping.objects.filter(device=device).values_list('device_user_id', 'employee_id'))
    created = 0
    for row in records:
        key = '|'.join([row['device_user_id'], row['timestamp'].astimezone(dt_timezone.utc).isoformat(), row['event']])
        _, added = AttendancePunch.objects.get_or_create(device=device,
            fingerprint=hashlib.sha256(key.encode()).hexdigest(),
            defaults={**row, 'employee_id': mappings.get(row['device_user_id'])})
        created += added
    device.last_sync = timezone.now()
    device.save(update_fields=['last_sync'])
    return created
