import unittest
from app import create_app
import store

class PrototypeTestCase(unittest.TestCase):
    def setUp(self):
        store.reset()
        self.app = create_app()
        self.client = self.app.test_client()

    def test_prototype(self):
        # 1. Fetch all orders
        res = self.client.get("/orders")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.get_json()), 5)

        # 2. Fetch orders by email
        res = self.client.get("/orders?email=dana@example.com")
        self.assertEqual(res.status_code, 200)
        orders = res.get_json()
        self.assertEqual(len(orders), 2)
        # Verify user_id is 1 (Dana)
        for o in orders:
            self.assertEqual(o["user_id"], 1)

if __name__ == "__main__":
    unittest.main()
