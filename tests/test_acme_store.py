import unittest
from unittest.mock import patch

import store
from app import create_app


class AcmeStoreTestCase(unittest.TestCase):
    def setUp(self):
        store.reset()
        self.client = create_app().test_client()


class TestHealth(AcmeStoreTestCase):
    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["service"], "acme-store")


class TestOrders(AcmeStoreTestCase):
    def test_list_orders(self):
        response = self.client.get("/orders")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()), 5)

    def test_get_order_includes_payment(self):
        response = self.client.get("/orders/1")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["id"], 1)
        self.assertIsNotNone(body["payment"])
        self.assertEqual(body["payment"]["order_id"], 1)

    def test_unknown_order(self):
        self.assertEqual(self.client.get("/orders/999").status_code, 404)


class TestCheckout(AcmeStoreTestCase):
    def test_creates_order_and_payment(self):
        response = self.client.post(
            "/checkout", json={"user_id": 1, "total_cents": 5000}
        )
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["order"]["total_cents"], 5000)
        self.assertEqual(body["payment"]["status"], "captured")
        self.assertTrue(body["payment"]["provider_ref"].startswith("pay_"))

    def test_rejects_unknown_user(self):
        response = self.client.post(
            "/checkout", json={"user_id": 99, "total_cents": 5000}
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_bad_amount(self):
        response = self.client.post("/checkout", json={"user_id": 1, "total_cents": 0})
        self.assertEqual(response.status_code, 400)


class TestRefunds(AcmeStoreTestCase):
    def test_lists_refunds_in_flight(self):
        response = self.client.get("/refunds")
        self.assertEqual(response.status_code, 200)
        statuses = {item["status"] for item in response.get_json()}
        self.assertEqual(statuses, {"refund_requested", "refunded"})

    def test_request_refund_marks_payment(self):
        response = self.client.post("/refunds", json={"order_id": 1})
        self.assertEqual(response.status_code, 202)
        body = response.get_json()
        self.assertEqual(body["status"], "refund_requested")
        self.assertIsNotNone(body["refund_requested_at"])

    def test_cannot_refund_twice(self):
        self.client.post("/refunds", json={"order_id": 1})
        response = self.client.post("/refunds", json={"order_id": 1})
        self.assertEqual(response.status_code, 409)

    def test_unknown_order(self):
        response = self.client.post("/refunds", json={"order_id": 999})
        self.assertEqual(response.status_code, 404)


class TestDelayedRefunds(AcmeStoreTestCase):
    @patch("integrations.notifications.NotificationsClient.send_email")
    def test_notify_delayed_refunds(self, mock_send_email):
        # In store.py, there are two payments with refund_requested_at > 3 days ago:
        # order 2: 9 days ago
        # order 3: 4 days ago
        # order 4: refunded 12 days ago (status is refunded, not refund_requested)
        response = self.client.post("/refunds/notify-delayed")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["notified_count"], 2)
        
        self.assertEqual(mock_send_email.call_count, 2)
        
        # Check that the correct emails were sent
        emails_sent = [call.kwargs["to_email"] for call in mock_send_email.call_args_list]
        self.assertIn("marco@example.com", emails_sent)
        self.assertIn("priya@example.com", emails_sent)


if __name__ == "__main__":
    unittest.main()
