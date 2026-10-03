from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from .models import AttendanceDevice, AttendancePunch, Employee
from .attendance_service import AttendanceError, normalize, parse_csv, parse_dahua, store_records, dahua_records, zk_records


class AttendanceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('attendance-admin', password='test-password')
        self.client.force_login(self.admin)
        self.device = AttendanceDevice.objects.create(name='Test device', protocol='dahua', host='192.0.2.10', username='admin')
        self.start = datetime(2026, 10, 2, tzinfo=dt_timezone.utc)
        self.end = self.start + timedelta(days=1)

    def test_attendance_pages_and_branding(self):
        for path in ('/attendance/', '/attendance/devices/add/', f'/attendance/devices/{self.device.pk}/'):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertContains(self.client.get('/'), 'Elakta')
        self.assertContains(self.client.get('/'), 'data-theme-toggle')
        self.assertContains(self.client.get('/login/'), 'theme.js')

    def test_non_admin_cannot_read_or_import_attendance(self):
        user = User.objects.create_user('staff')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/attendance/').status_code, 403)
        self.assertEqual(self.client.post(f'/attendance/devices/{self.device.pk}/', {'action':'sync'}).status_code, 403)

    def test_device_validation(self):
        response = self.client.post('/attendance/devices/add/', {'name':'Invalid', 'protocol':'dahua', 'host':'not-an-ip', 'port':'99999', 'timezone_name':'bad-zone'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(AttendanceDevice.objects.count(), 1)

    def test_csv_timezone_dedup_and_mapping(self):
        content = b'user_id,timestamp,event\n001,2026-10-02 09:00:00,In\n'
        rows = parse_csv(SimpleUploadedFile('punches.csv', content), self.device)
        self.assertEqual(rows[0]['timestamp'].astimezone(dt_timezone.utc).hour, 4)
        self.assertEqual(store_records(self.device, rows), 1)
        self.assertEqual(store_records(self.device, rows), 0)
        employee = Employee.objects.create(name='Test Employee', contact_number='123')
        response = self.client.post(f'/attendance/devices/{self.device.pk}/', {'action':'map', 'device_user_id':'001', 'employee':employee.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AttendancePunch.objects.get().employee, employee)

    def test_invalid_csv_does_not_partially_import(self):
        upload = SimpleUploadedFile('bad.csv', b'user_id,timestamp\n101,2026-10-02 09:00:00\n102,invalid\n')
        response = self.client.post(f'/attendance/devices/{self.device.pk}/', {'action':'import', 'file':upload})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Row 3')
        self.assertFalse(AttendancePunch.objects.exists())

    def test_dahua_parser_skips_failed_access(self):
        text = 'totalCount=2\nfound=2\nrecords[0].UserID=001\nrecords[0].CreateTime=1790928000\nrecords[0].Type=Entry\nrecords[0].Status=1\nrecords[1].Status=0'
        rows, found, total = parse_dahua(text, self.device)
        self.assertEqual((len(rows), found, total), (1, 2, 2))
        self.assertEqual(rows[0]['event'], 'In')
        with self.assertRaises(AttendanceError): parse_dahua('<html>login</html>', self.device)

    @patch('requests.Session')
    def test_dahua_connection_and_authentication_failure(self, session_class):
        session = session_class.return_value.__enter__.return_value
        session.get.return_value = SimpleNamespace(status_code=200, content=b'found=0', text='found=0\ntotalCount=0')
        self.assertEqual(dahua_records(self.device, 'secret', self.start, self.end, test=True), [])
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])
        session.get.return_value.status_code = 401
        with self.assertRaisesMessage(AttendanceError, 'Authentication failed'):
            dahua_records(self.device, 'secret', self.start, self.end)

    @patch('requests.Session')
    def test_dahua_splits_truncated_ranges(self, session_class):
        session = session_class.return_value.__enter__.return_value
        stamp = int(self.start.timestamp())
        def response(text): return SimpleNamespace(status_code=200, content=text.encode(), text=text)
        session.get.side_effect = [response('found=0\ntotalCount=2'),
            response(f'found=1\ntotalCount=1\nrecords[0].UserID=2\nrecords[0].CreateTime={stamp+50000}\nrecords[0].Type=Exit'),
            response(f'found=1\ntotalCount=1\nrecords[0].UserID=1\nrecords[0].CreateTime={stamp+100}\nrecords[0].Type=Entry')]
        self.assertEqual(len(dahua_records(self.device, 'secret', self.start, self.end)), 2)
        self.assertEqual(session.get.call_count, 3)

    @patch('zk.ZK')
    def test_zk_read_only_sync_and_disconnect(self, zk_class):
        self.device.protocol = 'zk'
        connection = zk_class.return_value.connect.return_value
        connection.get_attendance.return_value = [SimpleNamespace(user_id='101', timestamp=datetime(2026,10,2,10), punch=0)]
        rows = zk_records(self.device, '0', self.start, self.end)
        self.assertEqual(len(rows), 1)
        connection.disconnect.assert_called_once()
        connection.clear_attendance.assert_not_called()
        connection.disable_device.assert_not_called()

    @patch('zk.ZK')
    def test_zk_disconnects_on_failed_download(self, zk_class):
        connection = zk_class.return_value.connect.return_value
        connection.get_attendance.side_effect = RuntimeError('network failed')
        with self.assertRaises(AttendanceError): zk_records(self.device, '0', self.start, self.end)
        connection.disconnect.assert_called_once()

    @patch('operations.views.attendance.fetch_records')
    def test_sync_stores_punches_but_not_password(self, fetch):
        fetch.return_value = [normalize('101', self.start, 'Entry', 'Asia/Karachi')]
        response = self.client.post(f'/attendance/devices/{self.device.pk}/', {'action':'sync', 'start_date':'2026-10-02', 'end_date':'2026-10-02', 'password':'secret'}, follow=True)
        self.assertContains(response, '1 new punches')
        self.assertNotContains(response, 'secret')
        self.assertEqual(AttendancePunch.objects.count(), 1)
        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.last_sync)

    def test_invalid_date_range_never_connects(self):
        with patch('operations.views.attendance.fetch_records') as fetch:
            response = self.client.post(f'/attendance/devices/{self.device.pk}/', {'action':'sync', 'start_date':'2026-10-02', 'end_date':'2026-09-01'})
            self.assertContains(response, 'Choose a date range')
            fetch.assert_not_called()
