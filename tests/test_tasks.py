import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from app import create_app
from store import (get_all_users, get_all_orders, get_all_payments,
                   create_user, create_order, create_payment, reset_store)

class TestTasks(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        reset_store()

    @patch("integrations.notifications_client.notifications_client.send_email")
    def test_notify_delayed_refunds(self, mock_send_email):
        """Should trigger email for refunds older than DELAY_THRESHOLD_DAYS."""
        # Arrange: Create a user, order, and payment with a delayed refund
        user = create_user("John Doe", "john.doe@example.com")
        order = create_order(user.id, 1000)
        payment = create_payment(order.id, 1000, "test_ref")
        payment.status = "refund_requested"
        payment.refund_requested_at = datetime.utcnow() - timedelta(days=4)

        # Act: Call the notification endpoint
        response = self.client.post("/tasks/notify-delayed-refunds")

        # Assert: Verify the notification was sent
        self.assertEqual(response.status_code, 200)
        mock_send_email.assert_called_once()
        
        # Assert on the content of the email
        args, kwargs = mock_send_email.call_args
        self.assertEqual(kwargs["email"], user.email)
        self.assertIn(str(order.id), kwargs["subject"])
        self.assertIn(str(order.id), kwargs["message"])

    @patch("integrations.notifications_client.notifications_client.send_email")
    def test_no_notification_for_recent_refunds(self, mock_send_email):
        """Should not trigger email for refunds newer than DELAY_THRESHOLD_DAYS."""
        # Arrange: Create a user, order, and payment with a recent refund
        user = create_user("Jane Doe", "jane.doe@example.com")
        order = create_order(user.id, 2000)
        payment = create_payment(order.id, 2000, "test_ref_2")
        payment.status = "refund_requested"
        payment.refund_requested_at = datetime.utcnow() - timedelta(days=1)

        # Act: Call the notification endpoint
        response = self.client.post("/tasks/notify-delayed-refunds")

        # Assert: Verify no notification was sent
        self.assertEqual(response.status_code, 200)
        mock_send_email.assert_not_called()

    @patch("integrations.notifications_client.notifications_client.send_email")
    def test_no_notification_for_non_refund_statuses(self, mock_send_email):
        """Should not trigger email for payments not in 'refund_requested' status."""
        # Arrange: Create a user, order, and payment with a non-refund status
        user = create_user("Peter Pan", "peter.pan@example.com")
        order = create_order(user.id, 3000)
        payment = create_payment(order.id, 3000, "test_ref_3")
        payment.status = "completed" # Not a refund status

        # Act: Call the notification endpoint
        response = self.client.post("/tasks/notify-delayed-refunds")

        # Assert: Verify no notification was sent
        self.assertEqual(response.status_code, 200)
        mock_send_email.assert_not_called()

if __name__ == "__main__":
    unittest.main()
