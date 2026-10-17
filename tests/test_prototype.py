import unittest
from unittest.mock import patch

from app import create_app
import store
from integrations.mock_payments_gateway import MockPaymentsGateway


class TestOrderCancellationPrototype(unittest.TestCase):
    def setUp(self):
        store.reset()
        self.app = create_app()
        self.client = self.app.test_client()

    def test_cancel_pending_order_success(self):
        order_id = store.next_id("order")
        order = store.Order(id=order_id, user_id=1, total_cents=1000, status="pending")
        store.orders[order.id] = order
        
        payment_id = store.next_id("payment")
        payment = store.Payment(id=payment_id, order_id=order_id, amount_cents=1000, status="captured", provider_ref="pay_prototype123")
        store.payments[payment.id] = payment
        
        mock_gateway = MockPaymentsGateway()
        
        # Inject the mock gateway via WSGI environ
        response = self.client.post(
            f"/orders/{order_id}/cancel",
            environ_base={"acme.payments_gateway": mock_gateway}
        )
            
        self.assertEqual(response.status_code, 200)
        
        # Check that refund was called on our mock adapter
        self.assertEqual(len(mock_gateway.refund_calls), 1)
        self.assertEqual(mock_gateway.refund_calls[0]["provider_ref"], "pay_prototype123")
        
        # Check that order and payment statuses were updated
        self.assertEqual(store.orders[order_id].status, "cancelled")
        self.assertEqual(store.payments[payment_id].status, "refund_requested")
        
    def test_cancel_non_pending_order_rejected(self):
        mock_gateway = MockPaymentsGateway()
        
        response = self.client.post(
            "/orders/1/cancel",
            environ_base={"acme.payments_gateway": mock_gateway}
        )
            
        self.assertEqual(response.status_code, 400)
        self.assertIn("order is not pending", response.get_json()["error"])
        
        self.assertEqual(len(mock_gateway.refund_calls), 0)
        self.assertEqual(store.orders[1].status, "delivered")

if __name__ == "__main__":
    unittest.main()
