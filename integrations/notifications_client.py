"""Adapter for the external notifications-service.

Provides an interface for sending notifications (e.g. SMS receipts) to customers.
Follows the same shape as payments_gateway: reads config from environment variables,
exposes plain methods, and returns dictionaries rather than provider objects.
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

    def send_sms_receipt(
        self, to_phone: str, order_id: int, total_cents: int
    ) -> dict:
        if not to_phone:
            raise NotificationsClientError("phone number is required")
        if order_id is None:
            raise NotificationsClientError("order_id is required")
        if not isinstance(total_cents, int) or total_cents <= 0:
            raise NotificationsClientError("total_cents must be a positive integer")

        total_dollars = f"${total_cents / 100:.2f}"
        message = f"Thanks for your order! Order #{order_id} total: {total_dollars}"
        return {
            "id": f"notif_{uuid.uuid4().hex[:12]}",
            "to": to_phone,
            "order_id": order_id,
            "total_cents": total_cents,
            "message": message,
            "status": "sent",
        }

    def send_sms(self, to_phone: str, message: str) -> dict:
        if not to_phone:
            raise NotificationsClientError("phone number is required")
        if not message:
            raise NotificationsClientError("message is required")

        return {
            "id": f"notif_{uuid.uuid4().hex[:12]}",
            "to": to_phone,
            "message": message,
            "status": "sent",
        }
