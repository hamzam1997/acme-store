"""Runnable mock adapter for SMS provider (e.g. Twilio)."""

import uuid
from integrations.mock_notifications_client import MockNotificationsClient
from integrations.notifications_client import NotificationsClientError


class MockTwilioClient(MockNotificationsClient):
    """Runnable mock adapter simulating a Twilio SMS client."""

    def __init__(
        self,
        account_sid: str | None = "mock_account_sid",
        auth_token: str | None = "mock_auth_token",
        should_fail: bool = False,
        fail_error: Exception | None = None,
    ):
        super().__init__(
            api_key=auth_token,
            base_url="https://api.twilio.mock",
            should_fail=should_fail,
            fail_error=fail_error,
        )
        self.account_sid = account_sid
        self.messages = _MockTwilioMessages(self)


class _MockTwilioMessages:
    def __init__(self, client: MockTwilioClient):
        self.client = client

    def create(self, to: str, from_: str = "+15005550006", body: str = "") -> dict:
        call_info = {"method": "messages.create", "to": to, "from": from_, "body": body}
        self.client.calls.append(call_info)

        if self.client.should_fail:
            if self.client.fail_error:
                raise self.client.fail_error
            raise NotificationsClientError("Twilio SMS delivery failure")

        if not to:
            raise NotificationsClientError("to is required")
        if not body:
            raise NotificationsClientError("body is required")

        return {
            "sid": f"SM{uuid.uuid4().hex[:32]}",
            "to": to,
            "from": from_,
            "body": body,
            "status": "delivered",
        }
