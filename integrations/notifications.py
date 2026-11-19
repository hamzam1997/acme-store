import os
import uuid

class NotificationsError(RuntimeError):
    pass

class NotificationsClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.environ.get("NOTIFICATIONS_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "NOTIFICATIONS_API_BASE", "https://api.notifications.example.com"
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def send_email(self, to_email: str, subject: str, body: str) -> dict:
        if not to_email:
            raise NotificationsError("to_email is required")
        return {
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "status": "sent",
            "to": to_email,
            "subject": subject,
        }
