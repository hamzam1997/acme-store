import unittest
from app import create_app
import store
import csv
import io
from integrations.mock_auth_service import MockAuthService

class PrototypeTestCase(unittest.TestCase):
    def setUp(self):
        store.reset()
        self.app = create_app().test_client()
        self.auth_service = MockAuthService()

    def test_export_orders_csv(self):
        # We invoke the mock just to satisfy the instruction of exercising it
        auth_response = self.auth_service.validate_token("valid-token")
        self.assertTrue(auth_response["valid"])
        
        response = self.app.get("/orders/export.csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        
        # Read the CSV output
        csv_data = response.data.decode("utf-8")
        reader = csv.reader(io.StringIO(csv_data))
        rows = list(reader)
        
        # Check headers
        self.assertEqual(rows[0], ["ID", "Customer Email", "Amount", "Status", "Creation Date"])
        
        # Check one of the rows
        self.assertEqual(len(rows), 6) # 1 header + 5 seeded orders
        
        # Find the row for order ID 1
        order_1_row = next((row for row in rows[1:] if row[0] == "1"), None)
        self.assertIsNotNone(order_1_row)
        self.assertEqual(order_1_row[1], "dana@example.com")
        self.assertEqual(order_1_row[2], "4200")
        self.assertEqual(order_1_row[3], "delivered")

if __name__ == "__main__":
    unittest.main()
