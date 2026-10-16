"""Runnable mock adapter for Twilio SMS messaging service."""

import uuid
from datetime import datetime, timezone


class MockTwilioMessages:
    def __init__(self, client):
        self._client = client

    def create(self, to: str, body: str, from_: str = "+15005550006", **kwargs) -> dict:
        return self._client.send_sms(to=to, message=body, from_=from_, **kwargs)


class MockTwilioClient:
    """Mock adapter for Twilio SMS API."""

    def __init__(
        self,
        account_sid: str = "mock_account_sid",
        auth_token: str = "mock_auth_token",
    ):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.calls: list[dict] = []
        self.messages = MockTwilioMessages(self)

    @property
    def configured(self) -> bool:
        return True

    def send_sms(
        self,
        to: str,
        message: str = "",
        body: str = "",
        from_: str = "+15005550006",
        **kwargs,
    ) -> dict:
        content = message or body
        call_record = {
            "to": to,
            "message": content,
            "body": content,
            "from": from_,
            **kwargs,
        }
        self.calls.append(call_record)
        return {
            "sid": f"SM{uuid.uuid4().hex}",
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "to": to,
            "from": from_,
            "body": content,
            "message": content,
            "status": "queued",
            "date_created": datetime.now(timezone.utc).isoformat(),
        }

    def send_order_shipped_sms(self, to: str, order_id: int) -> dict:
        message = f"Your order #{order_id} has shipped!"
        return self.send_sms(to=to, message=message)

    def reset(self) -> None:
        self.calls.clear()
