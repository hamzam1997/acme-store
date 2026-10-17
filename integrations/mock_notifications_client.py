"""Runnable mock adapter for the external notifications-service.

Records calls and returns realistic response payloads without network requests.
"""

import uuid
from integrations.notifications_client import (
    DEFAULT_DELAYED_REFUND_TEMPLATE_ID,
    NotificationsClientError,
)


class MockNotificationsClient:
    """Mock adapter for notifications-service."""

    def __init__(
        self,
        api_key: str = "mock_notifications_key",
        base_url: str = "https://mock.notifications.local",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.calls: list[dict] = []
        self.should_fail: bool = False
        self.fail_error_message: str = "Mock notification dispatch error"

    @property
    def configured(self) -> bool:
        return True

    def reset(self) -> None:
        self.calls.clear()
        self.should_fail = False

    def send_email(
        self,
        recipient_email: str,
        template_id: str,
        template_vars: dict | None = None,
    ) -> dict:
        call_record = {
            "method": "send_email",
            "recipient_email": recipient_email,
            "template_id": template_id,
            "template_vars": template_vars or {},
        }
        self.calls.append(call_record)

        if self.should_fail:
            raise NotificationsClientError(self.fail_error_message)

        if not recipient_email:
            raise NotificationsClientError("recipient_email is required")
        if not template_id:
            raise NotificationsClientError("template_id is required")

        return {
            "notification_id": f"notif_mock_{uuid.uuid4().hex[:12]}",
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
        template = template_id or DEFAULT_DELAYED_REFUND_TEMPLATE_ID
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
