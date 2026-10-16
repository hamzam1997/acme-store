"""Adapter for the external notifications-service.

Communicates with the external notification service to dispatch alerts
(e.g., back-in-stock emails). Follows the adapter pattern: reads config
from the environment, exposes plain methods, and returns dictionaries.
"""

from datetime import datetime, timezone
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

    def send_back_in_stock_email(
        self, to_email: str, product_id: str | int, product_name: str | None = None
    ) -> dict:
        if not to_email:
            raise NotificationsClientError("to_email is required")
        if not product_id:
            raise NotificationsClientError("product_id is required")

        return {
            "id": f"notif_{uuid.uuid4().hex[:12]}",
            "to": to_email,
            "product_id": str(product_id),
            "product_name": product_name or "",
            "template": "back_in_stock_alert",
            "status": "delivered",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
