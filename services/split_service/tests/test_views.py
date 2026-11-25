import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

from split_app import create_app
from split_app.bill_service import _bill
from split_app.models import Allocation, SplitSession, db
from werkzeug.security import generate_password_hash

BILL = {
    "id": 12,
    "version": 3,
    "status": "open",
    "items": [{"id": 31, "quantity": 1, "price_cents": 1000}],
}


class ViewsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///"
                + str(Path(self.directory.name) / "test.db"),
            }
        )
        with self.app.app_context():
            db.create_all()
        self.mock = patch("split_app.bill_service._bill", return_value=BILL)
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.addCleanup(self.directory.cleanup)

    def guest(self):
        client = self.app.test_client()
        response = client.get("/api/bills/12")
        headers = {"X-CSRFToken": response.json["csrf_token"]}
        response = client.post(
            "/api/bills/12/participants", json={"display_name": "Ana"}, headers=headers
        )
        self.assertEqual(response.status_code, 200)
        return client, headers

    def test_browser_staff_progress_requires_separate_staff_credentials(self):
        client, _ = self.guest()
        url = "/api/staff/bills/12/progress"
        self.app.config.update(STAFF_USERNAME="", STAFF_PASSWORD_HASH="")
        self.assertEqual(client.get(url).status_code, 503)

        self.app.config.update(
            STAFF_USERNAME="staff",
            STAFF_PASSWORD_HASH=generate_password_hash("staff-test-password"),
            STAFF_API_TOKEN="internal-test-token",
        )
        for credentials in (
            {},
            {"headers": {"Authorization": "Bearer internal-test-token"}},
            {"auth": ("staff", "wrong-password")},
        ):
            response = client.get(url, **credentials)
            self.assertEqual(response.status_code, 401)
            self.assertIn("Basic", response.headers["WWW-Authenticate"])

        response = client.get(
            url,
            auth=("staff", "staff-test-password"),
            headers={"Origin": "https://guest.example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        internal = client.get(
            "/api/bills/12/progress",
            headers={
                "Authorization": "Bearer internal-test-token",
            },
        )
        self.assertEqual(response.json, internal.json)

    def test_csrf_and_methods(self):
        client = self.app.test_client()
        self.assertEqual(client.get("/health").json, {"status": "ok"})
        self.assertEqual(
            client.post("/api/bills/12/participants", json={"display_name": "Ana"}).status_code, 403
        )
        self.assertEqual(client.get("/api/bills/12/participants").status_code, 405)
        self.assertEqual(client.get("/api/bills/12/").status_code, 404)

    def test_concurrent_claim_one_winner(self):
        guests = [self.guest(), self.guest()]
        data = {"item_id": 31, "quantity": "1", "bill_version": 3, "split_version": 0}
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(
                pool.map(
                    lambda guest: (
                        guest[0]
                        .post("/api/bills/12/claims", json=data, headers=guest[1])
                        .status_code
                    ),
                    guests,
                )
            )
        self.assertEqual(sorted(responses), [201, 409])
        with self.app.app_context():
            self.assertEqual(Allocation.query.count(), 1)
            self.assertEqual(SplitSession.query.one().split_version, 1)

    def test_upstream_failure_rolls_back(self):
        client, headers = self.guest()
        with patch("split_app.bill_service._bill", side_effect=[BILL, None]):
            response = client.post(
                "/api/bills/12/claims",
                json={"item_id": 31, "quantity": "1", "bill_version": 3, "split_version": 0},
                headers=headers,
            )
        self.assertEqual(response.status_code, 503)
        with self.app.app_context():
            self.assertEqual(Allocation.query.count(), 0)
            self.assertEqual(SplitSession.query.one().split_version, 0)

    def test_tip_edit_and_poll(self):
        client, headers = self.guest()
        for value in [100, 200]:
            response = client.post(
                "/api/bills/12/tip", json={"kind": "fixed", "value": value}, headers=headers
            )
            self.assertEqual(response.json["value"], value)
        self.assertIn("claims", client.get("/api/bills/12/allocations").json)

    def test_bill_url_has_no_trailing_slash(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = '{"id":12}'
        with (
            self.app.app_context(),
            patch("split_app.bill_service.urlopen", return_value=response) as upstream,
        ):
            self.app.config["BILL_SERVICE_URL"] = "http://bill:8000/"
            self.assertEqual(_bill(12), {"id": 12})
            upstream.assert_called_once_with("http://bill:8000/bills/12", timeout=3)

    def test_change_claim_requires_owner_and_current_version(self):
        owner, headers = self.guest()
        other, other_headers = self.guest()
        base = "/api/bills/12"
        version = {"bill_version": "3", "split_version": 0}
        claim = owner.post(
            base + "/claims", headers=headers, json={**version, "item_id": 31, "quantity": "0.5"}
        )
        path = base + "/claims/" + claim.json["allocation_id"]
        self.assertEqual(
            owner.get(base + "/allocations").json["claims"][0]["allocation_id"],
            claim.json["allocation_id"],
        )
        self.assertEqual(
            other.delete(
                path, headers=other_headers, json={**version, "split_version": 1}
            ).status_code,
            404,
        )
        self.assertEqual(
            owner.put(path, headers=headers, json={**version, "quantity": "0.75"}).status_code, 409
        )
        self.assertEqual(
            owner.put(
                path, headers=headers, json={**version, "split_version": 1, "quantity": "1.1"}
            ).status_code,
            409,
        )
        result = owner.put(
            path, headers=headers, json={**version, "split_version": 1, "quantity": "0.75"}
        )
        self.assertEqual(result.json["split_version"], 2)
        self.assertEqual(owner.get(base + "/balance").json["total_cents"], 750)
        result = owner.delete(path, headers=headers, json={**version, "split_version": 2})
        self.assertTrue(result.json["deleted"])
        self.assertEqual(owner.get(base + "/balance").json["total_cents"], 0)

    def test_progress_and_settlement_use_current_amount(self):
        client, headers = self.guest()
        base = "/api/bills/12"
        self.app.config["STAFF_API_TOKEN"] = "staff-test"
        staff = {"Authorization": "Bearer staff-test"}
        self.assertEqual(client.get(base + "/progress").status_code, 401)
        self.assertEqual(
            client.get(base + "/progress", headers=staff).json["unallocated_subtotal_cents"], 1000
        )

        claim = client.post(
            base + "/claims",
            headers=headers,
            json={"bill_version": "3", "split_version": 0, "item_id": 31, "quantity": "1"},
        )
        self.assertEqual(claim.status_code, 201)
        balance = client.get(base + "/balance").json
        self.assertEqual(balance["total_cents"], 1000)
        self.assertEqual(
            client.get(base + "/progress", headers=staff).json[
                "allocated_unsettled_subtotal_cents"
            ],
            1000,
        )
        client.post(base + "/tip", headers=headers, json={"kind": "fixed", "value": 200})
        data = {"bill_version": "3", "split_version": 1, "amount_cents": 1000}
        self.assertEqual(
            client.post(base + "/settlement", headers=headers, json=data).status_code, 409
        )
        data["amount_cents"] = 1200
        self.assertEqual(
            client.post(base + "/settlement", headers=headers, json=data).status_code, 201
        )
        self.assertEqual(
            client.post(base + "/settlement", headers=headers, json=data).status_code, 200
        )
        self.assertEqual(
            client.get(base + "/participants/me").json["settlement"]["amount_cents"], 1200
        )
        self.assertTrue(client.get(base + "/progress", headers=staff).json["ready_to_close"])
        self.assertEqual(
            client.delete(
                base + "/claims/" + claim.json["allocation_id"],
                headers=headers,
                json={**data, "split_version": 2},
            ).status_code,
            409,
        )
        with patch("split_app.bill_service._bill", return_value={**BILL, "version": 4}):
            progress = client.get(base + "/progress", headers=staff).json
            self.assertTrue(progress["needs_review"])
            self.assertFalse(progress["ready_to_close"])
