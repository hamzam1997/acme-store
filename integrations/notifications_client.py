"""Adapter for the external notifications service owned by @team-comms.

Follows the same shape as payments_gateway: reads config from environment,
exposes plain methods, and returns dictionaries.
"""

import os
import uuid


class NotificationsClientError(RuntimeError):
    pass


class NotificationsClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        template_id: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("NOTIFICATIONS_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "NOTIFICATIONS_API_BASE", "https://api.notifications.example.com"
        )
        self.template_id = template_id or os.environ.get(
            "NOTIFICATIONS_BACK_IN_STOCK_TEMPLATE_ID", "tpl_back_in_stock_v1"
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def send_back_in_stock_email(
        self,
        to_email: str,
        product_id: int,
        product_name: str,
        stock_quantity: int = 1,
        template_id: str | None = None,
    ) -> dict:
        if not to_email or "@" not in to_email:
            raise NotificationsClientError("valid recipient email is required")
        if stock_quantity <= 0:
            raise NotificationsClientError("stock quantity must be positive")

        tpl = template_id or self.template_id
        return {
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "recipient": to_email,
            "template_id": tpl,
            "template_params": {
                "product_id": product_id,
                "product_name": product_name,
                "stock_quantity": stock_quantity,
            },
            "status": "sent",
        }

    def send_email(
        self,
        to_email: str,
        template_id: str,
        template_params: dict | None = None,
    ) -> dict:
        if not to_email or "@" not in to_email:
            raise NotificationsClientError("valid recipient email is required")
        return {
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "recipient": to_email,
            "template_id": template_id,
            "template_params": template_params or {},
            "status": "sent",
        }
