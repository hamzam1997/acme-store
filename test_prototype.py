"""Prototype test exercising back-in-stock notifications against mock adapters."""

import unittest

import store
from app import create_app
from integrations.mock_notifications_client import MockNotificationsClient
from integrations.notifications_client import NotificationsClient


class TestPrototypeBackInStockNotifications(unittest.TestCase):
    def setUp(self):
        store.reset()
        self.mock_notifier = MockNotificationsClient()
        self.app = create_app(notifications_client=self.mock_notifier)
        self.client = self.app.test_client()

    def test_full_back_in_stock_notification_flow(self):
        # 1. Verify product 2 is initially sold out
        prod_resp = self.client.get("/products/2")
        self.assertEqual(prod_resp.status_code, 200)
        self.assertEqual(prod_resp.get_json()["stock"], 0)

        # 2. Customer Dana Whitfield (user_id=1) subscribes to back-in-stock alerts
        sub_resp = self.client.post(
            "/stock-alerts",
            json={"product_id": 2, "user_id": 1},
        )
        self.assertEqual(sub_resp.status_code, 201)
        sub_data = sub_resp.get_json()
        self.assertEqual(sub_data["email"], "dana@example.com")
        self.assertEqual(sub_data["status"], "pending")
        alert_id = sub_data["id"]

        # Also guest customer subscribes with email directly
        guest_resp = self.client.post(
            "/stock-alerts",
            json={"product_id": 2, "email": "wile.e.coyote@example.com"},
        )
        self.assertEqual(guest_resp.status_code, 201)

        # Verify no emails sent yet
        self.assertEqual(len(self.mock_notifier.sent_emails), 0)

        # 3. Product 2 gets restocked with 20 items (0 -> 20 transition)
        restock_resp = self.client.post(
            "/products/2/restock",
            json={"quantity": 20},
        )
        self.assertEqual(restock_resp.status_code, 200)
        restock_data = restock_resp.get_json()
        self.assertEqual(restock_data["previous_stock"], 0)
        self.assertEqual(restock_data["product"]["stock"], 20)
        self.assertTrue(restock_data["transitioned"])
        self.assertEqual(restock_data["notifications_sent"], 2)

        # 4. Verify mock notifications client received both dispatch calls
        self.assertEqual(len(self.mock_notifier.sent_emails), 2)
        sent_recipients = [e["recipient"] for e in self.mock_notifier.sent_emails]
        self.assertIn("dana@example.com", sent_recipients)
        self.assertIn("wile.e.coyote@example.com", sent_recipients)

        first_call = self.mock_notifier.sent_emails[0]
        self.assertTrue(first_call["notification_id"].startswith("notif_mock_"))
        self.assertEqual(first_call["status"], "sent")
        self.assertEqual(first_call["template_id"], "tpl_back_in_stock_v1")
        self.assertEqual(first_call["template_params"]["product_id"], 2)
        self.assertEqual(first_call["template_params"]["stock_quantity"], 20)

        # 5. Verify subscription status updated to 'sent'
        alert_check = self.client.get(f"/stock-alerts/{alert_id}")
        self.assertEqual(alert_check.status_code, 200)
        self.assertEqual(alert_check.get_json()["status"], "sent")
        self.assertIsNotNone(alert_check.get_json()["sent_at"])

        # 6. Verify subsequent restocking when already in stock does not trigger alerts
        restock_again = self.client.post(
            "/products/2/restock",
            json={"quantity": 10},
        )
        self.assertEqual(restock_again.status_code, 200)
        self.assertEqual(restock_again.get_json()["previous_stock"], 20)
        self.assertEqual(restock_again.get_json()["notifications_sent"], 0)
        self.assertEqual(len(self.mock_notifier.sent_emails), 2)  # No new notifications

    def test_notifications_client_interface(self):
        # Verify the production adapter interface conforms to expected shape
        real_client = NotificationsClient(
            api_key="test-key",
            base_url="https://notifications.example.com",
            template_id="tpl_back_in_stock_custom",
        )
        self.assertTrue(real_client.configured)
        res = real_client.send_back_in_stock_email(
            to_email="test@example.com",
            product_id=2,
            product_name="Acme Giant Rubber Band",
            stock_quantity=5,
        )
        self.assertEqual(res["status"], "sent")
        self.assertEqual(res["template_id"], "tpl_back_in_stock_custom")
        self.assertEqual(res["recipient"], "test@example.com")
        self.assertTrue(res["notification_id"].startswith("notif_"))


if __name__ == "__main__":
    unittest.main()
