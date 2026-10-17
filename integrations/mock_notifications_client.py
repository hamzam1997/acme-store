"""Mock adapter for the external notifications service owned by @team-comms.

Records calls in memory, returns realistic response payloads, and supports error injection.
"""

from integrations.notifications_client import NotificationsClientError


class MockNotificationsClient:
    def __init__(
        self,
        api_key: str = "mock-notifications-api-key",
        base_url: str = "https://mock.notifications.example.com",
        template_id: str = "tpl_back_in_stock_v1",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.template_id = template_id
        self.sent_emails: list[dict] = []
        self.calls: list[dict] = []
        self.should_fail: bool = False
        self.fail_error: str = "Mock notification dispatch failed"

    @property
    def configured(self) -> bool:
        return True

    def reset(self) -> None:
        self.sent_emails.clear()
        self.calls.clear()
        self.should_fail = False

    def send_back_in_stock_email(
        self,
        to_email: str,
        product_id: int,
        product_name: str,
        stock_quantity: int = 1,
        template_id: str | None = None,
    ) -> dict:
        self.calls.append(
            {
                "method": "send_back_in_stock_email",
                "to_email": to_email,
                "product_id": product_id,
                "product_name": product_name,
                "stock_quantity": stock_quantity,
                "template_id": template_id,
            }
        )

        if self.should_fail:
            raise NotificationsClientError(self.fail_error)
        if not to_email or "@" not in to_email:
            raise NotificationsClientError("valid recipient email is required")
        if stock_quantity <= 0:
            raise NotificationsClientError("stock quantity must be positive")

        tpl = template_id or self.template_id
        payload = {
            "notification_id": f"notif_mock_{len(self.sent_emails) + 1:04d}",
            "recipient": to_email,
            "template_id": tpl,
            "template_params": {
                "product_id": product_id,
                "product_name": product_name,
                "stock_quantity": stock_quantity,
            },
            "status": "sent",
        }
        self.sent_emails.append(payload)
        return payload

    def send_email(
        self,
        to_email: str,
        template_id: str,
        template_params: dict | None = None,
    ) -> dict:
        self.calls.append(
            {
                "method": "send_email",
                "to_email": to_email,
                "template_id": template_id,
                "template_params": template_params,
            }
        )

        if self.should_fail:
            raise NotificationsClientError(self.fail_error)
        if not to_email or "@" not in to_email:
            raise NotificationsClientError("valid recipient email is required")

        payload = {
            "notification_id": f"notif_mock_{len(self.sent_emails) + 1:04d}",
            "recipient": to_email,
            "template_id": template_id,
            "template_params": template_params or {},
            "status": "sent",
        }
        self.sent_emails.append(payload)
        return payload
