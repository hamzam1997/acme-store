"""Prototype tests exercising SMS receipt logic against runnable mock adapters."""

import unittest

import store
from app import create_app
from integrations.mock_notifications_client import MockNotificationsClient
from integrations.mock_twilio_client import MockTwilioClient
from integrations.notifications_client import NotificationsClientError


class TestSmsReceiptPrototype(unittest.TestCase):
    def setUp(self):
        store.reset()

    def test_successful_checkout_sends_sms_receipt_via_mock_injection(self):
        mock_client = MockNotificationsClient()
        app = create_app(notifications_client=mock_client)
        client = app.test_client()

        # User 1 has phone_number="+15551234567"
        response = client.post(
            "/checkout",
            json={"user_id": 1, "total_cents": 4200},
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()

        # Verify order and payment created
        order_id = data["order"]["id"]
        self.assertEqual(data["order"]["total_cents"], 4200)
        self.assertEqual(data["payment"]["status"], "captured")

        # Verify mock recorded exactly one call
        self.assertEqual(len(mock_client.calls), 1)
        call = mock_client.calls[0]
        self.assertEqual(call["method"], "send_sms_receipt")
        self.assertEqual(call["to_phone"], "+15551234567")
        self.assertEqual(call["order_id"], order_id)
        self.assertEqual(call["total_cents"], 4200)

        # Verify receipt payload returned to customer
        self.assertIn("sms_receipt", data)
        receipt = data["sms_receipt"]
        self.assertTrue(receipt["id"].startswith("mock_notif_"))
        self.assertEqual(receipt["status"], "delivered")
        self.assertEqual(receipt["to"], "+15551234567")
        self.assertIn(str(order_id), receipt["message"])
        self.assertIn("$42.00", receipt["message"])

    def test_checkout_handles_mock_notification_failure_gracefully(self):
        mock_client = MockNotificationsClient(should_fail=True)
        app = create_app(notifications_client=mock_client)
        client = app.test_client()

        response = client.post(
            "/checkout",
            json={"user_id": 1, "total_cents": 7500},
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()

        # Order and payment must still succeed
        self.assertEqual(data["order"]["status"], "placed")
        self.assertEqual(data["payment"]["status"], "captured")
        self.assertEqual(data["sms_receipt"]["status"], "failed")

        # Mock still recorded the failed attempt
        self.assertEqual(len(mock_client.calls), 1)
        self.assertEqual(mock_client.calls[0]["total_cents"], 7500)

    def test_checkout_skips_sms_when_user_has_no_phone(self):
        mock_client = MockNotificationsClient()
        app = create_app(notifications_client=mock_client)
        client = app.test_client()

        # User 3 has phone_number=None
        response = client.post(
            "/checkout",
            json={"user_id": 3, "total_cents": 1500},
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["order"]["total_cents"], 1500)

        # No SMS should have been triggered
        self.assertEqual(len(mock_client.calls), 0)
        self.assertNotIn("sms_receipt", data)

    def test_checkout_with_injected_mock_twilio_client(self):
        mock_twilio = MockTwilioClient()
        app = create_app(notifications_client=mock_twilio)
        client = app.test_client()

        response = client.post(
            "/checkout",
            json={
                "user_id": 2,
                "total_cents": 9900,
                "phone_number": "+15559876543",
            },
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()

        self.assertEqual(len(mock_twilio.calls), 1)
        self.assertEqual(mock_twilio.calls[0]["to_phone"], "+15559876543")
        self.assertEqual(mock_twilio.calls[0]["total_cents"], 9900)
        self.assertEqual(data["sms_receipt"]["status"], "delivered")

    def test_mock_twilio_client_messages_api(self):
        mock_twilio = MockTwilioClient()
        resp = mock_twilio.messages.create(
            to="+15551112222",
            body="Order #10 total: $50.00",
        )
        self.assertTrue(resp["sid"].startswith("SM"))
        self.assertEqual(resp["status"], "delivered")
        self.assertEqual(resp["to"], "+15551112222")
        self.assertEqual(len(mock_twilio.calls), 1)

    def test_mock_notifications_client_direct_validation(self):
        mock_client = MockNotificationsClient()
        with self.assertRaises(NotificationsClientError):
            mock_client.send_sms_receipt(to_phone="", order_id=1, total_cents=100)
        with self.assertRaises(NotificationsClientError):
            mock_client.send_sms_receipt(to_phone="+15551234567", order_id=None, total_cents=100)
        with self.assertRaises(NotificationsClientError):
            mock_client.send_sms_receipt(to_phone="+15551234567", order_id=1, total_cents=-10)


if __name__ == "__main__":
    unittest.main()
