import unittest
from unittest.mock import patch

from app import create_app
import store


class TestCheckoutPrototype(unittest.TestCase):
    def setUp(self):
        store.reset()
        self.app = create_app()
        self.client = self.app.test_client()

    @patch("routes.checkout.PaymentsGateway")
    def test_idempotent_checkout(self, MockPaymentsGateway):
        # Set up the mock charge method
        mock_gateway_instance = MockPaymentsGateway.return_value
        mock_gateway_instance.charge.return_value = {
            "reference": "pay_mocked_123",
            "amount_cents": 1000,
            "description": "order 6",
            "idempotency_key": "idem-key-123",
            "status": "captured",
        }

        checkout_payload = {
            "user_id": 1,
            "total_cents": 1000,
            "idempotency_key": "idem-key-123"
        }

        # First request
        resp1 = self.client.post("/checkout", json=checkout_payload)
        self.assertEqual(resp1.status_code, 201)
        data1 = resp1.get_json()
        self.assertEqual(data1["order"]["user_id"], 1)
        self.assertEqual(data1["order"]["total_cents"], 1000)
        self.assertEqual(data1["order"]["idempotency_key"], "idem-key-123")
        self.assertEqual(data1["payment"]["amount_cents"], 1000)
        
        # Verify charge was called once
        mock_gateway_instance.charge.assert_called_once_with(
            1000, description=f"order {data1['order']['id']}", idempotency_key="idem-key-123"
        )
        
        # Reset mock call count to verify it isn't called again
        mock_gateway_instance.charge.reset_mock()

        # Second request with the same idempotency key
        resp2 = self.client.post("/checkout", json=checkout_payload)
        self.assertEqual(resp2.status_code, 200) # Returned existing order
        data2 = resp2.get_json()
        
        # Assert same order ID
        self.assertEqual(data1["order"]["id"], data2["order"]["id"])
        self.assertEqual(data1["payment"]["id"], data2["payment"]["id"])
        
        # Verify charge was NOT called
        mock_gateway_instance.charge.assert_not_called()

if __name__ == "__main__":
    unittest.main()
