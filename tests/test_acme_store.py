import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import store
from app import create_app
from models import Order, Payment, User


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
    @patch("integrations.notifications_service.send_email")
    def test_notify_delayed_refunds(self, mock_send_email):
        # 1. Seed a delayed refund
        store.users.clear()
        store.orders.clear()
        store.payments.clear()

        user = User(id=1, name="Test User", email="test@example.com")
        store.users[user.id] = user

        order = Order(id=1, user_id=1, total_cents=1000)
        store.orders[order.id] = order

        payment = Payment(
            id=1,
            order_id=1,
            amount_cents=1000,
            status="refund_requested",
            refund_requested_at=datetime.now(timezone.utc) - timedelta(days=5),
        )
        store.payments[payment.id] = payment

        # 2. Trigger notification check
        response = self.client.post("/internal/notify-delayed-refunds")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["notified_count"], 1)

        # 3. Assert notification sent and payment updated
        mock_send_email.assert_called_once_with(
            user_email=user.email,
            subject=f"Update on your refund for order #{order.id}",
            body=f"Hi {user.name}, we are still processing your refund for order #{order.id}. We will notify you again once the refund is complete.",
        )
        self.assertIsNotNone(store.payment_for_order(1).delayed_notification_sent_at)

        # 4. Assert idempotency (no second notification)
        mock_send_email.reset_mock()
        response = self.client.post("/internal/notify-delayed-refunds")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["notified_count"], 0)
        mock_send_email.assert_not_called()


if __name__ == "__main__":
    unittest.main()
