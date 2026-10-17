"""Prototype test suite exercising automated delayed refund notifications against mock adapter."""

from datetime import datetime, timedelta, timezone
import unittest

import store
from app import create_app
from integrations.mock_notifications_client import MockNotificationsClient
from integrations.notifications_client import NotificationsClientError
from models import Order, Payment, User
from routes.refunds import (
    check_and_notify_delayed_refunds,
    set_notifications_client,
)


class TestDelayedRefundPrototype(unittest.TestCase):
    def setUp(self):
        store.reset()
        set_notifications_client(None)
        self.mock_client = MockNotificationsClient()
        self.app = create_app()
        self.client = self.app.test_client()

    def tearDown(self):
        set_notifications_client(None)

    def test_mock_notifications_client_direct(self):
        """Verify the mock adapter records calls, returns realistic payloads, and handles error states."""
        client = MockNotificationsClient()
        self.assertTrue(client.configured)
        self.assertEqual(len(client.calls), 0)

        # Successful email send
        res = client.send_email(
            recipient_email="customer@example.com",
            template_id="delayed_notice",
            template_vars={"order_id": 10},
        )
        self.assertTrue(res["notification_id"].startswith("notif_mock_"))
        self.assertEqual(res["status"], "sent")
        self.assertEqual(res["recipient_email"], "customer@example.com")
        self.assertEqual(len(client.calls), 1)

        # Validation error on empty recipient
        with self.assertRaises(NotificationsClientError):
            client.send_email(recipient_email="", template_id="delayed_notice")

        # Configurable failure state
        client.should_fail = True
        with self.assertRaises(NotificationsClientError):
            client.send_email(
                recipient_email="customer@example.com",
                template_id="delayed_notice",
            )

        # Reset works
        client.reset()
        self.assertEqual(len(client.calls), 0)
        self.assertFalse(client.should_fail)

    def test_service_handler_with_injected_mock(self):
        """Verify check_and_notify_delayed_refunds directly with injected mock client."""
        now = datetime.now(timezone.utc)

        # Seed specific synthetic payments
        store.users[100] = User(id=100, name="Alice Test", email="alice@test.com")
        store.users[101] = User(id=101, name="Bob Test", email="bob@test.com")
        store.users[102] = User(id=102, name="Carol Test", email="carol@test.com")

        # Order & payment 100: requested 10 days ago (delayed)
        order_100 = Order(id=100, user_id=100, total_cents=5000, status="delivered")
        store.orders[100] = order_100
        payment_100 = Payment(
            id=100,
            order_id=100,
            amount_cents=5000,
            status="refund_requested",
            refund_requested_at=now - timedelta(days=10),
        )
        store.payments[100] = payment_100

        # Order & payment 101: requested 1 day ago (recent, NOT delayed at threshold=3)
        order_101 = Order(id=101, user_id=101, total_cents=3000, status="delivered")
        store.orders[101] = order_101
        payment_101 = Payment(
            id=101,
            order_id=101,
            amount_cents=3000,
            status="refund_requested",
            refund_requested_at=now - timedelta(days=1),
        )
        store.payments[101] = payment_101

        # Order & payment 102: already refunded 5 days ago (status != refund_requested)
        order_102 = Order(id=102, user_id=102, total_cents=4000, status="delivered")
        store.orders[102] = order_102
        payment_102 = Payment(
            id=102,
            order_id=102,
            amount_cents=4000,
            status="refunded",
            refund_requested_at=now - timedelta(days=8),
            refunded_at=now - timedelta(days=5),
        )
        store.payments[102] = payment_102

        # Run delayed check with threshold of 3 days
        result = check_and_notify_delayed_refunds(threshold_days=3, client=self.mock_client)

        # Seed data has payments 2 and 3 delayed, plus our payment 100 (total 3 delayed and notified)
        notified_pids = {n["payment_id"] for n in result["notified"]}
        self.assertIn(100, notified_pids)
        self.assertIn(2, notified_pids)
        self.assertIn(3, notified_pids)
        self.assertNotIn(101, notified_pids)  # recent
        self.assertNotIn(102, notified_pids)  # already refunded

        # Check payment 100 timestamp was updated
        self.assertIsNotNone(payment_100.last_delayed_notice_at)
        # Check payment 101 timestamp remains None
        self.assertIsNone(payment_101.last_delayed_notice_at)

        # Verify mock recorded calls with expected contents
        alice_calls = [
            c for c in self.mock_client.calls
            if c.get("recipient_email") == "alice@test.com"
        ]
        self.assertEqual(len(alice_calls), 1)
        self.assertEqual(alice_calls[0]["template_vars"]["customer_name"], "Alice Test")
        self.assertEqual(alice_calls[0]["template_vars"]["amount_cents"], 5000)
        self.assertEqual(alice_calls[0]["template_vars"]["order_id"], 100)

        # Duplicate dispatch test: running again should notify 0
        call_count_before = len(self.mock_client.calls)
        repeat_result = check_and_notify_delayed_refunds(threshold_days=3, client=self.mock_client)
        self.assertEqual(repeat_result["notified_count"], 0)
        self.assertEqual(len(self.mock_client.calls), call_count_before)

    def test_http_endpoint_with_injected_mock(self):
        """Verify the POST /refunds/notify-delayed endpoint using mock adapter injection."""
        set_notifications_client(self.mock_client)

        # Default run (threshold = 3)
        resp = self.client.post("/refunds/notify-delayed")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["threshold_days"], 3)
        self.assertEqual(data["notified_count"], 2)
        self.assertEqual(data["failed_count"], 0)

        # Calling GET /refunds confirms last_delayed_notice_at is exposed
        list_resp = self.client.get("/refunds")
        self.assertEqual(list_resp.status_code, 200)
        refunds = {r["id"]: r for r in list_resp.get_json()}
        self.assertIsNotNone(refunds[2]["last_delayed_notice_at"])
        self.assertIsNotNone(refunds[3]["last_delayed_notice_at"])
        # Payment 4 is refunded, never had delayed notice
        self.assertIsNone(refunds[4]["last_delayed_notice_at"])

    def test_failure_handling_and_retry(self):
        """Verify errors during notification sending are captured gracefully and allow retry."""
        self.mock_client.should_fail = True
        set_notifications_client(self.mock_client)

        resp = self.client.post("/refunds/notify-delayed")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["notified_count"], 0)
        self.assertEqual(data["failed_count"], 2)

        # Because notifications failed, last_delayed_notice_at remains None
        self.assertIsNone(store.payments[2].last_delayed_notice_at)
        self.assertIsNone(store.payments[3].last_delayed_notice_at)

        # Recover client and retry
        self.mock_client.should_fail = False
        retry_resp = self.client.post("/refunds/notify-delayed")
        self.assertEqual(retry_resp.status_code, 200)
        retry_data = retry_resp.get_json()
        self.assertEqual(retry_data["notified_count"], 2)
        self.assertEqual(retry_data["failed_count"], 0)
        self.assertIsNotNone(store.payments[2].last_delayed_notice_at)
        self.assertIsNotNone(store.payments[3].last_delayed_notice_at)


if __name__ == "__main__":
    unittest.main()
