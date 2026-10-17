import unittest
from unittest.mock import patch

from app import create_app
import store


class TestOrderCancellation(unittest.TestCase):
    def setUp(self):
        store.reset()
        self.app = create_app()
        self.client = self.app.test_client()

    @patch("integrations.payments_gateway.PaymentsGateway.refund")
    def test_cancel_pending_order_success(self, mock_refund):
        mock_refund.return_value = {"reference": "pay_test", "status": "refund_pending"}
        
        # We need a pending order. Let's create one directly in the store.
        order_id = store.next_id("order")
        order = store.Order(id=order_id, user_id=1, total_cents=1000, status="pending")
        store.orders[order.id] = order
        
        payment_id = store.next_id("payment")
        payment = store.Payment(id=payment_id, order_id=order_id, amount_cents=1000, status="captured", provider_ref="pay_test_ref")
        store.payments[payment.id] = payment
        
        response = self.client.post(f"/orders/{order_id}/cancel")
            
        self.assertEqual(response.status_code, 200)
        
        # Verify refund was called correctly
        mock_refund.assert_called_once_with("pay_test_ref")
        
        # Verify order and payment statuses were updated
        self.assertEqual(store.orders[order_id].status, "cancelled")
        self.assertEqual(store.payments[payment_id].status, "refund_requested")
        self.assertIsNotNone(store.payments[payment_id].refund_requested_at)

    @patch("integrations.payments_gateway.PaymentsGateway.refund")
    def test_cancel_non_pending_order_rejected(self, mock_refund):
        # order id 1 is 'delivered' based on store.py seeds
        response = self.client.post("/orders/1/cancel")
            
        self.assertEqual(response.status_code, 400)
        self.assertIn("order is not pending", response.get_json()["error"])
        
        # Verify refund was NOT called
        mock_refund.assert_not_called()
        
        # Verify order status is unchanged
        self.assertEqual(store.orders[1].status, "delivered")

    def test_cancel_unknown_order(self):
        response = self.client.post("/orders/999/cancel")
        self.assertEqual(response.status_code, 404)
        self.assertIn("order not found", response.get_json()["error"])

if __name__ == "__main__":
    unittest.main()
