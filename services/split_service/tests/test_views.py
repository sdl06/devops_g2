import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor
from split_app import create_app
from split_app.models import db, Allocation, SplitSession
from split_app.views import _bill

BILL = {'id': 12, 'version': 3, 'status': 'open', 'items': [{'id': 31, 'quantity': 1, 'price_cents': 1000}]}

class ViewsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret', 'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(Path(self.directory.name) / 'test.db')})
        with self.app.app_context():
            db.create_all()
        self.mock = patch('split_app.views._bill', return_value=BILL)
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.addCleanup(self.directory.cleanup)

    def guest(self):
        client = self.app.test_client()
        response = client.get('/api/bills/12')
        headers = {'X-CSRFToken': response.json['csrf_token']}
        response = client.post('/api/bills/12/participants', json={'display_name': 'Ana'}, headers=headers)
        self.assertEqual(response.status_code, 200)
        return client, headers

    def test_csrf_and_methods(self):
        client = self.app.test_client()
        self.assertEqual(client.get('/health').json, {'status': 'ok'})
        self.assertEqual(client.post('/api/bills/12/participants', json={'display_name': 'Ana'}).status_code, 403)
        self.assertEqual(client.get('/api/bills/12/participants').status_code, 405)
        self.assertEqual(client.get('/api/bills/12/').status_code, 404)

    def test_concurrent_claim_one_winner(self):
        guests = [self.guest(), self.guest()]
        data = {'item_id': 31, 'quantity': '1', 'bill_version': 3, 'split_version': 0}
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda guest: guest[0].post('/api/bills/12/claims', json=data, headers=guest[1]).status_code, guests))
        self.assertEqual(sorted(responses), [201, 409])
        with self.app.app_context():
            self.assertEqual(Allocation.query.count(), 1)
            self.assertEqual(SplitSession.query.one().split_version, 1)

    def test_upstream_failure_rolls_back(self):
        client, headers = self.guest()
        with patch('split_app.views._bill', side_effect=[BILL, None]):
            response = client.post('/api/bills/12/claims', json={'item_id': 31, 'quantity': '1', 'bill_version': 3, 'split_version': 0}, headers=headers)
        self.assertEqual(response.status_code, 503)
        with self.app.app_context():
            self.assertEqual(Allocation.query.count(), 0)
            self.assertEqual(SplitSession.query.one().split_version, 0)

    def test_tip_edit_and_poll(self):
        client, headers = self.guest()
        for value in [100, 200]:
            response = client.post('/api/bills/12/tip', json={'kind': 'fixed', 'value': value}, headers=headers)
            self.assertEqual(response.json['value'], value)
        self.assertIn('claims', client.get('/api/bills/12/allocations').json)

    def test_bill_url_has_no_trailing_slash(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = '{"id":12}'
        with self.app.app_context(), patch('split_app.views.urlopen', return_value=response) as upstream:
            self.app.config['BILL_SERVICE_URL'] = 'http://bill:8000/'
            self.assertEqual(_bill(12), {'id': 12})
            upstream.assert_called_once_with('http://bill:8000/bills/12', timeout=3)
