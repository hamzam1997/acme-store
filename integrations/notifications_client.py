import os
import requests

class NotificationsClient:
    def __init__(self):
        self.api_key = os.environ.get("NOTIFICATIONS_API_KEY")
        self.base_url = os.environ.get("NOTIFICATIONS_API_BASE")

    def send_email(self, email, subject, message):
        if not self.api_key or not self.base_url:
            print(f"Email not sent: API key or base URL not configured. To: {email}, Subject: {subject}")
            return {"status": "not_sent", "reason": "not_configured"}

        url = f"{self.base_url}/email"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "email": email,
            "subject": subject,
            "message": message,
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending email: {e}")
            return {"status": "error", "reason": str(e)}

notifications_client = NotificationsClient()
