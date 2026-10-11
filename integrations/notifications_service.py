"""Adapter for the external notifications service."""

import os
import uuid


class NotificationsServiceError(RuntimeError):
    pass


class NotificationsService:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.environ.get("NOTIFICATIONS_API_KEY", "fake-api-key")
        self.base_url = base_url or os.environ.get(
            "NOTIFICATIONS_API_BASE", "https://api.notifications.example.com"
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def send_email(self, email_address: str, template_id: str, template_context: dict) -> dict:
        if not email_address or not template_id:
            raise NotificationsServiceError("email_address and template_id are required")
        print(f"Sending email to {email_address} with template {template_id}...")
        return {
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "status": "sent",
        }
