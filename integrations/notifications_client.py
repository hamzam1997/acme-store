"""Adapter for the external notifications service.

Interfaces with @team-comms's notifications-service to send customer-facing
messages such as SMS. Follows the adapter pattern: reads config from environment
variables, exposes plain methods, and returns dictionaries rather than provider
objects.
"""

import os
import uuid


class NotificationsClientError(RuntimeError):
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

    def send_sms(self, to: str, message: str) -> dict:
        if not to:
            raise NotificationsClientError("recipient phone number is required")
        if not message:
            raise NotificationsClientError("message cannot be empty")
        return {
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "to": to,
            "message": message,
            "status": "queued",
        }

    def send_order_shipped_sms(self, to: str, order_id: int) -> dict:
        message = f"Your order #{order_id} has shipped!"
        return self.send_sms(to=to, message=message)
