import unittest
from unittest.mock import MagicMock, patch

from app import create_app
from integrations.mock_notifications_client import MockNotificationsClient
from integrations.notifications_client import NotificationsClient, NotificationsClientError
import routes.stock_alerts
import store


class StockAlertsTestCase(unittest.TestCase):
    def setUp(self):
        store.reset()
        self.mock_client = MockNotificationsClient()
        self.app = create_app()
        self.app.config["NOTIFICATIONS_CLIENT"] = self.mock_client
        self.client = self.app.test_client()

    def tearDown(self):
        routes.stock_alerts.set_notifications_client(None)


class TestStockAlertRegistration(StockAlertsTestCase):
    def test_subscribe_with_email_success(self):
        response = self.client.post(
            "/stock-alerts",
            json={"product_id": "widget-100", "email": "customer@example.com"},
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["product_id"], "widget-100")
        self.assertEqual(data["email"], "customer@example.com")
        self.assertEqual(data["status"], "pending")
        self.assertIsNone(data["notified_at"])
        self.assertIn("id", data)

    def test_subscribe_alias_endpoint(self):
        response = self.client.post(
            "/stock-alerts/subscribe",
            json={"product_id": "gadget-200", "email": "shopper@example.com"},
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["product_id"], "gadget-200")
        self.assertEqual(data["status"], "pending")

    def test_subscribe_with_user_id(self):
        # User 1 is Dana Whitfield, email: dana@example.com
        response = self.client.post(
            "/stock-alerts",
            json={"product_id": "widget-100", "user_id": 1},
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["email"], "dana@example.com")
        self.assertEqual(data["product_id"], "widget-100")

    def test_subscribe_unknown_user_id(self):
        response = self.client.post(
            "/stock-alerts",
            json={"product_id": "widget-100", "user_id": 9999},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("unknown user", response.get_json()["error"])

    def test_subscribe_missing_product_id(self):
        response = self.client.post(
            "/stock-alerts",
            json={"email": "customer@example.com"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("product_id is required", response.get_json()["error"])

    def test_subscribe_empty_product_id(self):
        response = self.client.post(
            "/stock-alerts",
            json={"product_id": "   ", "email": "customer@example.com"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("product_id is required", response.get_json()["error"])

    def test_subscribe_missing_email(self):
        response = self.client.post(
            "/stock-alerts",
            json={"product_id": "widget-100"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("valid email is required", response.get_json()["error"])

    def test_subscribe_invalid_email_format(self):
        response = self.client.post(
            "/stock-alerts",
            json={"product_id": "widget-100", "email": "not-an-email"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("valid email is required", response.get_json()["error"])

    def test_deduplicates_pending_subscriptions(self):
        resp1 = self.client.post(
            "/stock-alerts",
            json={"product_id": "widget-100", "email": "customer@example.com"},
        )
        resp2 = self.client.post(
            "/stock-alerts",
            json={"product_id": "widget-100", "email": "customer@example.com"},
        )
        self.assertEqual(resp1.status_code, 201)
        self.assertEqual(resp2.status_code, 201)
        self.assertEqual(resp1.get_json()["id"], resp2.get_json()["id"])
        self.assertEqual(len(store.stock_notifications), 1)

    def test_list_and_get_stock_alerts(self):
        self.client.post(
            "/stock-alerts",
            json={"product_id": "item-1", "email": "user1@example.com"},
        )
        self.client.post(
            "/stock-alerts",
            json={"product_id": "item-2", "email": "user2@example.com"},
        )

        list_resp = self.client.get("/stock-alerts")
        self.assertEqual(list_resp.status_code, 200)
        items = list_resp.get_json()
        self.assertEqual(len(items), 2)

        # Filter by product_id
        filtered_resp = self.client.get("/stock-alerts?product_id=item-1")
        self.assertEqual(filtered_resp.status_code, 200)
        filtered_items = filtered_resp.get_json()
        self.assertEqual(len(filtered_items), 1)
        self.assertEqual(filtered_items[0]["product_id"], "item-1")

        # Get by id
        alert_id = items[0]["id"]
        get_resp = self.client.get(f"/stock-alerts/{alert_id}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.get_json()["id"], alert_id)

        # Get non-existent
        not_found = self.client.get("/stock-alerts/999")
        self.assertEqual(not_found.status_code, 404)


class TestStockAlertReplenishment(StockAlertsTestCase):
    def test_replenishment_triggers_email_to_subscribers(self):
        # Register two customers for item-A and one for item-B
        self.client.post(
            "/stock-alerts",
            json={"product_id": "item-A", "email": "alice@example.com"},
        )
        self.client.post(
            "/stock-alerts",
            json={"product_id": "item-A", "email": "bob@example.com"},
        )
        self.client.post(
            "/stock-alerts",
            json={"product_id": "item-B", "email": "carol@example.com"},
        )

        # Replenish item-A with positive inventory
        response = self.client.post(
            "/stock-alerts/replenish",
            json={"product_id": "item-A", "inventory": 15},
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["notified_count"], 2)
        self.assertEqual(data["product_id"], "item-A")

        # Verify mock recorded exactly 2 sent emails
        self.assertEqual(len(self.mock_client.sent_emails), 2)
        recipient_emails = {m["to"] for m in self.mock_client.sent_emails}
        self.assertEqual(recipient_emails, {"alice@example.com", "bob@example.com"})
        for email in self.mock_client.sent_emails:
            self.assertEqual(email["product_id"], "item-A")
            self.assertEqual(email["template"], "back_in_stock_alert")
            self.assertEqual(email["status"], "delivered")

        # Verify notifications in store marked sent
        pending_item_a = store.get_pending_notifications_for_product("item-A")
        self.assertEqual(len(pending_item_a), 0)

        item_a_alerts = store.get_stock_notifications(product_id="item-A")
        for alert in item_a_alerts:
            self.assertEqual(alert.status, "sent")
            self.assertIsNotNone(alert.notified_at)

        # Carol's alert for item-B remains pending
        pending_item_b = store.get_pending_notifications_for_product("item-B")
        self.assertEqual(len(pending_item_b), 1)

    def test_second_replenishment_does_not_duplicate_alerts(self):
        self.client.post(
            "/stock-alerts",
            json={"product_id": "item-A", "email": "alice@example.com"},
        )
        # First replenishment
        self.client.post(
            "/stock-alerts/replenish",
            json={"product_id": "item-A", "inventory": 5},
        )
        self.assertEqual(len(self.mock_client.sent_emails), 1)

        # Second replenishment of item-A
        response = self.client.post(
            "/stock-alerts/replenish",
            json={"product_id": "item-A", "inventory": 10},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["notified_count"], 0)
        self.assertEqual(len(self.mock_client.sent_emails), 1)

    def test_replenishment_with_zero_inventory_does_not_send(self):
        self.client.post(
            "/stock-alerts",
            json={"product_id": "item-A", "email": "alice@example.com"},
        )
        response = self.client.post(
            "/stock-alerts/replenish",
            json={"product_id": "item-A", "inventory": 0},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["notified_count"], 0)
        self.assertEqual(len(self.mock_client.sent_emails), 0)

        # Subscriber is still pending
        pending = store.get_pending_notifications_for_product("item-A")
        self.assertEqual(len(pending), 1)

    def test_replenish_missing_product_id(self):
        response = self.client.post(
            "/stock-alerts/replenish",
            json={"inventory": 10},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("product_id is required", response.get_json()["error"])

    def test_replenish_service_error_returns_502(self):
        self.client.post(
            "/stock-alerts",
            json={"product_id": "item-A", "email": "alice@example.com"},
        )
        self.mock_client.should_fail = True
        self.mock_client.failure_message = "Downstream email provider failure"

        response = self.client.post(
            "/stock-alerts/replenish",
            json={"product_id": "item-A", "inventory": 10},
        )
        self.assertEqual(response.status_code, 502)
        self.assertIn("Downstream email provider failure", response.get_json()["error"])

    def test_mock_patch_adapter_directly(self):
        # Explicit test validating mock strategy with patch as requested by plan
        app = create_app()
        client = app.test_client()

        store.add_stock_notification("item-X", "subscriber@example.com")

        with patch.object(
            NotificationsClient,
            "send_back_in_stock_email",
            return_value={
                "id": "notif_mock_patch_123",
                "to": "subscriber@example.com",
                "product_id": "item-X",
                "template": "back_in_stock_alert",
                "status": "delivered",
            },
        ) as mock_send:
            response = client.post(
                "/stock-alerts/replenish",
                json={"product_id": "item-X", "inventory": 3},
            )
            self.assertEqual(response.status_code, 200)
            mock_send.assert_called_once_with(
                to_email="subscriber@example.com",
                product_id="item-X",
                product_name=None,
            )


if __name__ == "__main__":
    unittest.main()
