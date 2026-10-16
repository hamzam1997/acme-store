"""Runnable mock adapter for the external notifications-service."""

import uuid
from integrations.notifications_client import NotificationsClientError


class MockNotificationsClient:
    """Mock notifications client for testing without external services."""

    def __init__(
        self,
        api_key: str | None = "mock_api_key",
        base_url: str | None = "https://mock.notifications.example.com",
        should_fail: bool = False,
        fail_error: Exception | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.should_fail = should_fail
        self.fail_error = fail_error
        self.calls: list[dict] = []

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def send_sms_receipt(
        self, to_phone: str, order_id: int, total_cents: int
    ) -> dict:
        call_info = {
            "method": "send_sms_receipt",
            "to_phone": to_phone,
            "order_id": order_id,
            "total_cents": total_cents,
        }
        self.calls.append(call_info)

        if self.should_fail:
            if self.fail_error:
                raise self.fail_error
            raise NotificationsClientError("Simulated SMS delivery failure")

        if not to_phone:
            raise NotificationsClientError("phone number is required")
        if order_id is None:
            raise NotificationsClientError("order_id is required")
        if not isinstance(total_cents, int) or total_cents <= 0:
            raise NotificationsClientError("total_cents must be a positive integer")

        total_dollars = f"${total_cents / 100:.2f}"
        message = f"Thanks for your order! Order #{order_id} total: {total_dollars}"
        return {
            "id": f"mock_notif_{uuid.uuid4().hex[:12]}",
            "to": to_phone,
            "order_id": order_id,
            "total_cents": total_cents,
            "message": message,
            "status": "delivered",
        }

    def send_sms(self, to_phone: str, message: str) -> dict:
        call_info = {
            "method": "send_sms",
            "to_phone": to_phone,
            "message": message,
        }
        self.calls.append(call_info)

        if self.should_fail:
            if self.fail_error:
                raise self.fail_error
            raise NotificationsClientError("Simulated SMS delivery failure")

        if not to_phone:
            raise NotificationsClientError("phone number is required")
        if not message:
            raise NotificationsClientError("message is required")

        return {
            "id": f"mock_notif_{uuid.uuid4().hex[:12]}",
            "to": to_phone,
            "message": message,
            "status": "delivered",
        }

    def reset(self) -> None:
        self.calls.clear()
