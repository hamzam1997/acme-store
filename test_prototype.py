import unittest
from app import create_app
import store
from routes.refunds import check_and_notify_delayed_refunds
from integrations.mock_notifications_client import MockNotificationsClient

class TestPrototype(unittest.TestCase):
    def setUp(self):
        store.reset()

    def test_notify_delayed_refunds_with_mock_client(self):
        mock_client = MockNotificationsClient()
        notified_count = check_and_notify_delayed_refunds(mock_client)
        
        self.assertEqual(notified_count, 2)
        self.assertEqual(len(mock_client.calls), 2)
        
        emails_sent = [call["to_email"] for call in mock_client.calls]
        self.assertIn("marco@example.com", emails_sent)
        self.assertIn("priya@example.com", emails_sent)

if __name__ == "__main__":
    unittest.main()
