"""Adapter for the external notifications service."""

import os
import uuid


class NotificationsServiceError(RuntimeError):
    pass


class NotificationsService:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.environ.get("NOTIFICATIONS_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "NOTIFICATIONS_API_BASE", "https://api.notifications.example.com"
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def send_delayed_refund_notification(self, user_email: str, order_id: int) -> dict:
        if not user_email:
            raise NotificationsServiceError("user_email is required")
        if not order_id:
            raise NotificationsServiceError("order_id is required")

        # In a real system, this would make an API call to the notifications service.
        # For this prototype, we'll just return a mock response.
        return {
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "status": "sent",
            "template": "delayed_refund",
            "recipient": user_email,
            "params": {"order_id": order_id},
        }
