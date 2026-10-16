import unittest
from unittest.mock import MagicMock, patch

import store
from app import create_app
from integrations.notifications_client import (
    NotificationsClient,
    NotificationsClientError,
)


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

    @patch("routes.checkout.NotificationsClient")
    def test_checkout_invokes_notifications_client_with_correct_receipt_details(
        self, mock_client_cls
    ):
        mock_instance = MagicMock()
        mock_instance.send_sms_receipt.return_value = {
            "id": "notif_test123",
            "to": "+15551234567",
            "order_id": 6,
            "total_cents": 4500,
            "message": "Thanks for your order! Order #6 total: $45.00",
            "status": "sent",
        }
        mock_client_cls.return_value = mock_instance

        response = self.client.post(
            "/checkout", json={"user_id": 1, "total_cents": 4500}
        )
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        order_id = body["order"]["id"]

        mock_instance.send_sms_receipt.assert_called_once_with(
            to_phone="+15551234567",
            order_id=order_id,
            total_cents=4500,
        )
        self.assertIn("sms_receipt", body)
        self.assertEqual(body["sms_receipt"]["status"], "sent")

    @patch("routes.checkout.NotificationsClient")
    def test_checkout_handles_notification_failure_gracefully(
        self, mock_client_cls
    ):
        mock_instance = MagicMock()
        mock_instance.send_sms_receipt.side_effect = RuntimeError("SMS provider is down")
        mock_client_cls.return_value = mock_instance

        response = self.client.post(
            "/checkout", json={"user_id": 1, "total_cents": 3000}
        )
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["order"]["status"], "placed")
        self.assertEqual(body["payment"]["status"], "captured")
        self.assertEqual(body["sms_receipt"]["status"], "failed")

    @patch("routes.checkout.NotificationsClient")
    def test_checkout_skips_sms_when_user_has_no_phone(self, mock_client_cls):
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance

        # User 3 has phone_number=None
        response = self.client.post(
            "/checkout", json={"user_id": 3, "total_cents": 2500}
        )
        self.assertEqual(response.status_code, 201)
        mock_instance.send_sms_receipt.assert_not_called()

    @patch("routes.checkout.NotificationsClient")
    def test_checkout_uses_request_phone_number_override(self, mock_client_cls):
        mock_instance = MagicMock()
        mock_instance.send_sms_receipt.return_value = {"status": "sent"}
        mock_client_cls.return_value = mock_instance

        response = self.client.post(
            "/checkout",
            json={
                "user_id": 3,
                "total_cents": 2500,
                "phone_number": "+15559990000",
            },
        )
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        mock_instance.send_sms_receipt.assert_called_once_with(
            to_phone="+15559990000",
            order_id=body["order"]["id"],
            total_cents=2500,
        )


class TestStoreUserHelpers(AcmeStoreTestCase):
    def test_user_lookup_helpers(self):
        user1 = store.get_user(1)
        self.assertIsNotNone(user1)
        self.assertEqual(user1.name, "Dana Whitfield")
        self.assertEqual(user1.phone_number, "+15551234567")

        user_by_phone = store.user_by_phone("+15551234567")
        self.assertEqual(user_by_phone, user1)

        self.assertIsNone(store.user_by_phone("+19999999999"))
        self.assertIsNone(store.get_user(999))


class TestNotificationsClientAdapter(unittest.TestCase):
    def test_send_sms_receipt_success(self):
        client = NotificationsClient(api_key="key", base_url="https://notif.test")
        self.assertTrue(client.configured)
        receipt = client.send_sms_receipt("+15551234567", order_id=42, total_cents=1999)
        self.assertEqual(receipt["to"], "+15551234567")
        self.assertEqual(receipt["order_id"], 42)
        self.assertEqual(receipt["total_cents"], 1999)
        self.assertEqual(receipt["status"], "sent")
        self.assertIn("42", receipt["message"])
        self.assertIn("$19.99", receipt["message"])

    def test_send_sms_receipt_validation(self):
        client = NotificationsClient()
        with self.assertRaises(NotificationsClientError):
            client.send_sms_receipt("", 1, 100)
        with self.assertRaises(NotificationsClientError):
            client.send_sms_receipt("+15551234567", None, 100)
        with self.assertRaises(NotificationsClientError):
            client.send_sms_receipt("+15551234567", 1, 0)


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


if __name__ == "__main__":
    unittest.main()
