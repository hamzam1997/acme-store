
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

from app import create_app
import store
from models import User, Order, Payment

class TestNotifications(unittest.TestCase):

    def setUp(self):
        app = create_app()
        app.config.update({
            "TESTING": True,
        })
        self.client = app.test_client()
        store.users.clear()
        store.orders.clear()
        store.payments.clear()

    @patch('routes.notifications.NotificationsService')
    def test_sends_notification_for_delayed_refund(self, MockNotificationsService):
        """A delayed refund should trigger a notification."""
        # Arrange
        mock_service_instance = MockNotificationsService.return_value
        mock_service_instance.configured = True
        mock_service_instance.send_email.return_value = {"status": "sent"}

        user = User(id=1, name="Test User", email="test@example.com")
        store.users[user.id] = user
        order = Order(id=1, user_id=1, total_cents=1000)
        store.orders[order.id] = order
        payment = Payment(
            id=1,
            order_id=1,
            amount_cents=1000,
            status="refund_requested",
            refund_requested_at=datetime.now(timezone.utc) - timedelta(days=4),
        )
        store.payments[payment.id] = payment

        # Act
        response = self.client.post("/tasks/send-delayed-refund-notifications")

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"notifications_sent": 1})
        mock_service_instance.send_email.assert_called_once()
        
        updated_payment = store.payments.get(payment.id)
        self.assertIsNotNone(updated_payment.delay_notification_sent_at)

    @patch('routes.notifications.NotificationsService')
    def test_no_notification_for_recent_refund_request(self, MockNotificationsService):
        """A recent refund request should not trigger a notification."""
        # Arrange
        mock_service_instance = MockNotificationsService.return_value
        mock_service_instance.configured = True

        user = User(id=1, name="Test User", email="test@example.com")
        store.users[user.id] = user
        order = Order(id=1, user_id=1, total_cents=1000)
        store.orders[order.id] = order
        payment = Payment(
            id=1,
            order_id=1,
            amount_cents=1000,
            status="refund_requested",
            refund_requested_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        store.payments[payment.id] = payment

        # Act
        response = self.client.post("/tasks/send-delayed-refund-notifications")

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"notifications_sent": 0})
        mock_service_instance.send_email.assert_not_called()

    @patch('routes.notifications.NotificationsService')
    def test_no_notification_for_completed_refund(self, MockNotificationsService):
        """A completed refund should not trigger a notification."""
        # Arrange
        mock_service_instance = MockNotificationsService.return_value
        mock_service_instance.configured = True

        user = User(id=1, name="Test User", email="test@example.com")
        store.users[user.id] = user
        order = Order(id=1, user_id=1, total_cents=1000)
        store.orders[order.id] = order
        payment = Payment(
            id=1,
            order_id=1,
            amount_cents=1000,
            status="refunded",
            refund_requested_at=datetime.now(timezone.utc) - timedelta(days=5),
            refunded_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        store.payments[payment.id] = payment

        # Act
        response = self.client.post("/tasks/send-delayed-refund-notifications")

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"notifications_sent": 0})
        mock_service_instance.send_email.assert_not_called()

    @patch('routes.notifications.NotificationsService')
    def test_no_duplicate_notifications(self, MockNotificationsService):
        """A second notification should not be sent for the same delayed refund."""
        # Arrange
        mock_service_instance = MockNotificationsService.return_value
        mock_service_instance.configured = True

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
            delay_notification_sent_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        store.payments[payment.id] = payment

        # Act
        response = self.client.post("/tasks/send-delayed-refund-notifications")

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"notifications_sent": 0})
        mock_service_instance.send_email.assert_not_called()

    @patch('routes.notifications.NotificationsService')
    def test_notification_service_not_configured(self, MockNotificationsService):
        """Should return 500 if notification service is not configured."""
        # Arrange
        mock_service_instance = MockNotificationsService.return_value
        mock_service_instance.configured = False

        # Act
        response = self.client.post("/tasks/send-delayed-refund-notifications")

        # Assert
        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.json)
        self.assertEqual(response.json["error"], "Notifications service not configured")
