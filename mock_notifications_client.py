"""Runnable mock adapter for notifications-service."""

import uuid


class MockNotificationsClient:
    """Mock adapter for notifications-service API owned by @team-comms."""

    def __init__(
        self,
        api_key: str = "mock-notifications-key",
        base_url: str = "https://mock.notifications.example.com",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.calls: list[dict] = []

    @property
    def configured(self) -> bool:
        return True

    def send_sms(self, to: str, message: str) -> dict:
        call_record = {"to": to, "message": message}
        self.calls.append(call_record)
        return {
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "to": to,
            "message": message,
            "channel": "sms",
            "status": "queued",
        }

    def send_order_shipped_sms(self, to: str, order_id: int) -> dict:
        message = f"Your order #{order_id} has shipped!"
        return self.send_sms(to=to, message=message)

    def reset(self) -> None:
        self.calls.clear()
