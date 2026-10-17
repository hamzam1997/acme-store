import unittest

import store
from app import create_app
from integrations.mock_notifications_client import MockNotificationsClient
from integrations.notifications_client import NotificationsClientError
from routes.stock_alerts import restock_product


class StockAlertsTestCase(unittest.TestCase):
    def setUp(self):
        store.reset()
        self.mock_notifier = MockNotificationsClient()
        self.app = create_app(notifications_client=self.mock_notifier)
        self.client = self.app.test_client()


class TestSubscribeStockAlert(StockAlertsTestCase):
    def test_subscribe_sold_out_product_with_email(self):
        # Product 2 has stock = 0
        response = self.client.post(
            "/stock-alerts",
            json={"product_id": 2, "email": "customer@example.com"},
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["product_id"], 2)
        self.assertEqual(data["email"], "customer@example.com")
        self.assertEqual(data["status"], "pending")
        self.assertIsNone(data["sent_at"])
        self.assertIsNotNone(data["created_at"])

    def test_subscribe_with_user_id(self):
        # User 1 is Dana Whitfield (dana@example.com)
        response = self.client.post(
            "/stock-alerts",
            json={"product_id": 2, "user_id": 1},
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["product_id"], 2)
        self.assertEqual(data["user_id"], 1)
        self.assertEqual(data["email"], "dana@example.com")
        self.assertEqual(data["status"], "pending")

    def test_subscribe_in_stock_product_fails(self):
        # Product 1 has stock = 10
        response = self.client.post(
            "/stock-alerts",
            json={"product_id": 1, "email": "customer@example.com"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("in stock", response.get_json()["error"])

    def test_subscribe_unknown_product_fails(self):
        response = self.client.post(
            "/stock-alerts",
            json={"product_id": 9999, "email": "customer@example.com"},
        )
        self.assertEqual(response.status_code, 404)

    def test_subscribe_invalid_email_fails(self):
        response = self.client.post(
            "/stock-alerts",
            json={"product_id": 2, "email": "not-an-email"},
        )
        self.assertEqual(response.status_code, 400)

    def test_subscribe_missing_email_and_user_fails(self):
        response = self.client.post(
            "/stock-alerts",
            json={"product_id": 2},
        )
        self.assertEqual(response.status_code, 400)

    def test_subscribe_unknown_user_fails(self):
        response = self.client.post(
            "/stock-alerts",
            json={"product_id": 2, "user_id": 999},
        )
        self.assertEqual(response.status_code, 400)

    def test_cannot_subscribe_twice_to_same_product(self):
        self.client.post(
            "/stock-alerts",
            json={"product_id": 2, "email": "duplicate@example.com"},
        )
        response = self.client.post(
            "/stock-alerts",
            json={"product_id": 2, "email": "duplicate@example.com"},
        )
        self.assertEqual(response.status_code, 409)


class TestManageStockAlerts(StockAlertsTestCase):
    def test_list_and_get_stock_alerts(self):
        # Create 2 subscriptions
        self.client.post(
            "/stock-alerts", json={"product_id": 2, "email": "user1@example.com"}
        )
        res2 = self.client.post(
            "/stock-alerts", json={"product_id": 3, "email": "user2@example.com"}
        )
        alert2_id = res2.get_json()["id"]

        list_resp = self.client.get("/stock-alerts")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.get_json()), 2)

        # Filter by product_id
        filtered_resp = self.client.get("/stock-alerts?product_id=2")
        self.assertEqual(filtered_resp.status_code, 200)
        self.assertEqual(len(filtered_resp.get_json()), 1)
        self.assertEqual(filtered_resp.get_json()[0]["email"], "user1@example.com")

        # Get single alert
        get_resp = self.client.get(f"/stock-alerts/{alert2_id}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.get_json()["product_id"], 3)

    def test_cancel_stock_alert(self):
        res = self.client.post(
            "/stock-alerts", json={"product_id": 2, "email": "user1@example.com"}
        )
        alert_id = res.get_json()["id"]

        cancel_resp = self.client.delete(f"/stock-alerts/{alert_id}")
        self.assertEqual(cancel_resp.status_code, 200)
        self.assertEqual(cancel_resp.get_json()["status"], "cancelled")


class TestRestockingAndNotifications(StockAlertsTestCase):
    def test_restock_sends_notifications_when_transitioning_from_zero(self):
        # Subscribe two users to product 2 (stock = 0)
        self.client.post(
            "/stock-alerts", json={"product_id": 2, "email": "buyer1@example.com"}
        )
        self.client.post(
            "/stock-alerts", json={"product_id": 2, "email": "buyer2@example.com"}
        )

        # Restock product 2 with quantity = 5
        response = self.client.post(
            "/products/2/restock",
            json={"quantity": 5},
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["previous_stock"], 0)
        self.assertEqual(body["product"]["stock"], 5)
        self.assertTrue(body["transitioned"])
        self.assertEqual(body["notifications_sent"], 2)

        # Check mock notifier received both notifications
        self.assertEqual(len(self.mock_notifier.sent_emails), 2)
        recipients = {call["recipient"] for call in self.mock_notifier.sent_emails}
        self.assertEqual(recipients, {"buyer1@example.com", "buyer2@example.com"})

        # Check alert status in database
        alerts_resp = self.client.get("/stock-alerts?product_id=2")
        alerts = alerts_resp.get_json()
        for a in alerts:
            self.assertEqual(a["status"], "sent")
            self.assertIsNotNone(a["sent_at"])

    def test_restock_via_stock_alerts_route(self):
        self.client.post(
            "/stock-alerts", json={"product_id": 2, "email": "buyer@example.com"}
        )
        response = self.client.post(
            "/stock-alerts/restock",
            json={"product_id": 2, "quantity": 15},
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["product"]["stock"], 15)
        self.assertEqual(body["notifications_sent"], 1)
        self.assertEqual(len(self.mock_notifier.sent_emails), 1)

    def test_restocking_product_already_in_stock_does_not_send_alerts(self):
        # Product 1 is already in stock with stock = 10
        response = self.client.post(
            "/products/1/restock",
            json={"quantity": 5},
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["previous_stock"], 10)
        self.assertEqual(body["product"]["stock"], 15)
        self.assertFalse(body["transitioned"])
        self.assertEqual(body["notifications_sent"], 0)
        self.assertEqual(len(self.mock_notifier.sent_emails), 0)

    def test_restock_invalid_quantity(self):
        response = self.client.post("/products/2/restock", json={"quantity": -2})
        self.assertEqual(response.status_code, 400)

        response2 = self.client.post(
            "/products/2/restock", json={"quantity": "not-an-int"}
        )
        self.assertEqual(response2.status_code, 400)

    def test_restock_unknown_product(self):
        response = self.client.post("/products/999/restock", json={"quantity": 5})
        self.assertEqual(response.status_code, 404)

    def test_handles_notifications_service_failure(self):
        self.client.post(
            "/stock-alerts", json={"product_id": 2, "email": "buyer@example.com"}
        )
        self.mock_notifier.should_fail = True

        response = self.client.post("/products/2/restock", json={"quantity": 10})
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["notifications_sent"], 0)
        self.assertEqual(len(body["failed"]), 1)
        self.assertIn("Mock notification dispatch failed", body["failed"][0]["error"])

        # Check alert is still pending
        alerts = self.client.get("/stock-alerts?product_id=2").get_json()
        self.assertEqual(alerts[0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
