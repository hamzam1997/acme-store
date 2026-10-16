"""Mock adapter for the external notifications-service.

Used for testing and prototype runs without needing live credentials
or network access. Records calls and returns realistic responses.
"""

from datetime import datetime, timezone
import uuid

from integrations.notifications_client import NotificationsClientError


class MockNotificationsClient:
    def __init__(
        self,
        api_key: str = "mock-notifications-key",
        base_url: str = "https://mock.notifications.local",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.sent_emails: list[dict] = []
        self.calls: list[dict] = []
        self.should_fail: bool = False
        self.failure_message: str = "Notification service unavailable"

    @property
    def configured(self) -> bool:
        return True

    def send_back_in_stock_email(
        self, to_email: str, product_id: str | int, product_name: str | None = None
    ) -> dict:
        if self.should_fail:
            raise NotificationsClientError(self.failure_message)

        if not to_email:
            raise NotificationsClientError("to_email is required")
        if not product_id:
            raise NotificationsClientError("product_id is required")

        payload = {
            "id": f"notif_mock_{uuid.uuid4().hex[:10]}",
            "to": to_email,
            "product_id": str(product_id),
            "product_name": product_name or "",
            "template": "back_in_stock_alert",
            "status": "delivered",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

        self.sent_emails.append(payload)
        self.calls.append(
            {
                "method": "send_back_in_stock_email",
                "to_email": to_email,
                "product_id": str(product_id),
                "product_name": product_name,
                "response": payload,
            }
        )
        return payload

    def reset(self) -> None:
        """Reset recorded calls and error state."""
        self.sent_emails.clear()
        self.calls.clear()
        self.should_fail = False
