import unittest
from unittest.mock import patch

import store
from app import create_app
from integrations.mock_notifications_client import MockNotificationsClient
from routes.refunds import set_notifications_client


class AcmeStoreTestCase(unittest.TestCase):
    def setUp(self):
        store.reset()
        set_notifications_client(None)
        self.client = create_app().test_client()

    def tearDown(self):
        set_notifications_client(None)


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


class TestDelayedRefundNotifications(AcmeStoreTestCase):
    def test_delayed_refunds_trigger_notifications(self):
        mock_client = MockNotificationsClient()
        set_notifications_client(mock_client)

        response = self.client.post("/refunds/notify-delayed")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["notified_count"], 2)
        self.assertEqual(body["failed_count"], 0)

        # Seed payments 2 and 3 are 9 and 4 days old (threshold 3 days)
        notified_payment_ids = [n["payment_id"] for n in body["notified"]]
        self.assertEqual(notified_payment_ids, [2, 3])

        # Verify payment records updated with last_delayed_notice_at
        self.assertIsNotNone(store.payments[2].last_delayed_notice_at)
        self.assertIsNotNone(store.payments[3].last_delayed_notice_at)

        # Verify calls recorded on mock adapter
        self.assertEqual(len(mock_client.calls), 2)
        call1 = mock_client.calls[0]
        self.assertEqual(call1["recipient_email"], "marco@example.com")
        self.assertIn("amount_cents", call1["template_vars"])

    def test_threshold_parameter_filters_refunds(self):
        mock_client = MockNotificationsClient()
        set_notifications_client(mock_client)

        # Payment 2 is 9 days old, Payment 3 is 4 days old
        # With threshold_days=5, only payment 2 should qualify
        response = self.client.post(
            "/refunds/notify-delayed", json={"threshold_days": 5}
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["notified_count"], 1)
        self.assertEqual(body["notified"][0]["payment_id"], 2)

    def test_recent_refunds_are_ignored(self):
        mock_client = MockNotificationsClient()
        set_notifications_client(mock_client)

        # Request a new refund now
        self.client.post("/refunds", json={"order_id": 1})
        p1 = store.payment_for_order(1)
        self.assertEqual(p1.status, "refund_requested")

        # Threshold of 3 days should not notify the new refund
        response = self.client.post(
            "/refunds/notify-delayed", json={"threshold_days": 3}
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        notified_ids = [n["payment_id"] for n in body["notified"]]
        self.assertNotIn(p1.id, notified_ids)

    def test_duplicate_sends_prevented(self):
        mock_client = MockNotificationsClient()
        set_notifications_client(mock_client)

        first_resp = self.client.post("/refunds/notify-delayed")
        self.assertEqual(first_resp.get_json()["notified_count"], 2)

        # Second call immediately after should notify 0
        second_resp = self.client.post("/refunds/notify-delayed")
        self.assertEqual(second_resp.get_json()["notified_count"], 0)
        self.assertEqual(len(mock_client.calls), 2)

    def test_notification_failure_handled_gracefully(self):
        mock_client = MockNotificationsClient()
        mock_client.should_fail = True
        mock_client.fail_error_message = "Notifications service unavailable"
        set_notifications_client(mock_client)

        response = self.client.post("/refunds/notify-delayed")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["notified_count"], 0)
        self.assertEqual(body["failed_count"], 2)
        self.assertIn("unavailable", body["failed"][0]["error"])

        # Timestamp should not be set on failure so it can be retried
        self.assertIsNone(store.payments[2].last_delayed_notice_at)
        self.assertIsNone(store.payments[3].last_delayed_notice_at)

    def test_invalid_threshold(self):
        response = self.client.post(
            "/refunds/notify-delayed", json={"threshold_days": -2}
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            "/refunds/notify-delayed", json={"threshold_days": "not-an-int"}
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_notifications_client(self):
        with patch("routes.refunds.NotificationsClient") as mock_cls:
            instance = mock_cls.return_value
            instance.send_delayed_refund_notice.return_value = {
                "notification_id": "notif_mock_123",
                "status": "sent",
            }
            response = self.client.post("/refunds/notify-delayed")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["notified_count"], 2)
            self.assertEqual(instance.send_delayed_refund_notice.call_count, 2)


if __name__ == "__main__":
    unittest.main()
