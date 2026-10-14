"""Adapter for the external notifications service."""

import os
import json
import requests

def send_email(user_email: str, subject: str, body: str) -> dict:
    """Send an email to a user."""
    api_key = os.environ["NOTIFICATIONS_API_KEY"]
    base_url = os.environ["NOTIFICATIONS_API_BASE"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "user_email": user_email,
        "subject": subject,
        "body": body,
    }
    # In a real scenario, this would make a request to the notifications service.
    # For this prototype, we'll just simulate a successful response.
    print(f"Sending email to {user_email} with subject '{subject}'")
    return {"status": "sent", "message_id": "mock-message-id"}
