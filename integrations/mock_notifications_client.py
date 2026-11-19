import uuid

class MockNotificationsClient:
    def __init__(self):
        self.calls = []

    @property
    def configured(self) -> bool:
        return True

    def send_email(self, to_email: str, subject: str, body: str) -> dict:
        self.calls.append({
            "to_email": to_email,
            "subject": subject,
            "body": body
        })
        return {
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "status": "sent",
            "to": to_email,
            "subject": subject,
        }
