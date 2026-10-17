import unittest
import store
from app import create_app

class TestPrototype(unittest.TestCase):
    def setUp(self):
        store.reset()
        self.client = create_app().test_client()

    def test_prototype(self):
        # Fetch order with no refund
        res1 = self.client.get("/orders/1")
        self.assertEqual(res1.status_code, 200)
        data1 = res1.get_json()
        self.assertIn("refund_status", data1)
        self.assertEqual(data1["refund_status"], "captured")
        self.assertIsNone(data1["refund_requested_at"])

        # Fetch order with a requested refund
        res2 = self.client.get("/orders/2")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertEqual(data2["refund_status"], "refund_requested")
        self.assertIsNotNone(data2["refund_requested_at"])

        # Request a new refund and ensure order endpoint reflects it
        res_refund = self.client.post("/refunds", json={"order_id": 5})
        self.assertEqual(res_refund.status_code, 202)

        res5 = self.client.get("/orders/5")
        data5 = res5.get_json()
        self.assertEqual(data5["refund_status"], "refund_requested")
        self.assertIsNotNone(data5["refund_requested_at"])

if __name__ == '__main__':
    unittest.main()
