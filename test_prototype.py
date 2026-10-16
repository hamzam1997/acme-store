"""Prototype test exercising back-in-stock notifications against the mock adapter."""

import unittest

from app import create_app
from integrations.mock_notifications_client import MockNotificationsClient
import routes.stock_alerts
import store


class TestBackInStockPrototype(unittest.TestCase):
    def setUp(self):
        store.reset()
        self.mock_notifications = MockNotificationsClient()
        self.app = create_app()
        self.app.config["NOTIFICATIONS_CLIENT"] = self.mock_notifications
        self.client = self.app.test_client()

    def tearDown(self):
        routes.stock_alerts.set_notifications_client(None)

    def test_prototype_back_in_stock_flow(self):
        """End-to-end prototype flow:
        1. Customer registers interest for an out-of-stock product ("notify me").
        2. A second customer registers for the same item.
        3. Inventory is replenished with positive quantity.
        4. Mock notification client receives alerts for all subscribed customers.
        5. Store tracks alert status transitions from pending to sent.
        6. Subsequent replenishments do not send duplicate emails.
        """
        # Step 1: Alice clicks "notify me" for out-of-stock product "solar-charger"
        resp_alice = self.client.post(
            "/stock-alerts/subscribe",
            json={"product_id": "solar-charger", "email": "alice@example.com"},
        )
        self.assertEqual(resp_alice.status_code, 201)
        alice_data = resp_alice.get_json()
        self.assertEqual(alice_data["status"], "pending")
        self.assertEqual(alice_data["product_id"], "solar-charger")

        # Step 2: Bob (registered user 2: marco@example.com) also requests notification
        resp_bob = self.client.post(
            "/stock-alerts/subscribe",
            json={"product_id": "solar-charger", "user_id": 2},
        )
        self.assertEqual(resp_bob.status_code, 201)
        bob_data = resp_bob.get_json()
        self.assertEqual(bob_data["email"], "marco@example.com")
        self.assertEqual(bob_data["status"], "pending")

        # Step 3: Check store reflects 2 pending notifications for "solar-charger"
        pending_alerts = store.get_pending_notifications_for_product("solar-charger")
        self.assertEqual(len(pending_alerts), 2)
        self.assertEqual(len(self.mock_notifications.sent_emails), 0)

        # Step 4: Inventory replenishment occurs (inventory becomes positive: 25 units)
        replenish_resp = self.client.post(
            "/stock-alerts/replenish",
            json={
                "product_id": "solar-charger",
                "product_name": "Solar Charger 20W",
                "inventory": 25,
            },
        )
        self.assertEqual(replenish_resp.status_code, 200)
        replenish_data = replenish_resp.get_json()
        self.assertEqual(replenish_data["notified_count"], 2)

        # Step 5: Verify Mock adapter recorded calls with realistic payloads
        self.assertEqual(len(self.mock_notifications.sent_emails), 2)
        recipients = [m["to"] for m in self.mock_notifications.sent_emails]
        self.assertIn("alice@example.com", recipients)
        self.assertIn("marco@example.com", recipients)

        for email_record in self.mock_notifications.sent_emails:
            self.assertEqual(email_record["product_id"], "solar-charger")
            self.assertEqual(email_record["product_name"], "Solar Charger 20W")
            self.assertEqual(email_record["template"], "back_in_stock_alert")
            self.assertEqual(email_record["status"], "delivered")
            self.assertTrue(email_record["id"].startswith("notif_mock_"))

        # Step 6: Verify store updated status to 'sent' and set notified_at
        alerts_now = store.get_stock_notifications(product_id="solar-charger")
        self.assertEqual(len(alerts_now), 2)
        for alert in alerts_now:
            self.assertEqual(alert.status, "sent")
            self.assertIsNotNone(alert.notified_at)

        # No pending alerts remain
        self.assertEqual(len(store.get_pending_notifications_for_product("solar-charger")), 0)

        # Step 7: Another replenishment arrives; verify no duplicate emails sent
        second_replenish = self.client.post(
            "/stock-alerts/replenish",
            json={"product_id": "solar-charger", "inventory": 10},
        )
        self.assertEqual(second_replenish.status_code, 200)
        self.assertEqual(second_replenish.get_json()["notified_count"], 0)
        # Total sent emails remains 2
        self.assertEqual(len(self.mock_notifications.sent_emails), 2)


if __name__ == "__main__":
    unittest.main()
