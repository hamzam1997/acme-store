"""Adapter for the external notifications-service provider.

Owned by @team-comms for customer email, SMS, and push notifications.
Follows the repo integration shape: reads config from environment, exposes plain
methods, and returns dictionaries.
"""

import os
import uuid

DEFAULT_DELAYED_REFUND_TEMPLATE_ID = "delayed_refund_in_progress"


class NotificationsClientError(RuntimeError):
    pass


class NotificationsClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.environ.get("NOTIFICATIONS_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "NOTIFICATIONS_SERVICE_BASE", "https://notifications.example.com"
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def send_email(
        self,
        recipient_email: str,
        template_id: str,
        template_vars: dict | None = None,
    ) -> dict:
        if not recipient_email:
            raise NotificationsClientError("recipient_email is required")
        if not template_id:
            raise NotificationsClientError("template_id is required")

        return {
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "recipient_email": recipient_email,
            "template_id": template_id,
            "template_vars": template_vars or {},
            "status": "sent",
        }

    def send_delayed_refund_notice(
        self,
        recipient_email: str,
        customer_name: str,
        order_id: int,
        amount_cents: int,
        refund_requested_at: str,
        template_id: str | None = None,
    ) -> dict:
        if not recipient_email:
            raise NotificationsClientError("recipient_email is required")

        template = (
            template_id
            or os.environ.get("DELAYED_REFUND_TEMPLATE_ID")
            or DEFAULT_DELAYED_REFUND_TEMPLATE_ID
        )
        template_vars = {
            "customer_name": customer_name,
            "order_id": order_id,
            "amount_cents": amount_cents,
            "refund_requested_at": refund_requested_at,
            "message": "Your refund is taking longer than usual and is still in progress.",
        }
        return self.send_email(
            recipient_email=recipient_email,
            template_id=template,
            template_vars=template_vars,
        )
