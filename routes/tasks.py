"""Background tasks for the Acme Store."""

import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify

from integrations.notifications_service import NotificationsService
import store

tasks = Blueprint("tasks", __name__, url_prefix="/tasks")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@tasks.route("/notify-delayed-refunds", methods=["POST"])
def notify_delayed_refunds():
    """Scan for delayed refunds and notify customers."""
    delay_days = int(os.environ.get("REFUND_DELAY_NOTIFY_DAYS", 3))

    notifications_service = NotificationsService()

    belated_payments = []
    for payment in store.payments.values():
        if payment.status != "refund_requested" or not payment.refund_requested_at:
            continue

        is_delayed = payment.refund_requested_at < _now() - timedelta(days=delay_days)
        if not is_delayed or payment.delayed_notification_sent_at:
            continue

        order = store.orders.get(payment.order_id)
        if not order:
            continue

        user = store.users.get(order.user_id)
        if not user:
            continue

        notifications_service.send_delayed_refund_notification(
            user_email=user.email, order_id=order.id
        )

        payment.delayed_notification_sent_at = _now()
        belated_payments.append(payment)

    return jsonify(
        {
            "message": f"Notified {len(belated_payments)} users about delayed refunds.",
            "belated_payments": [p.to_dict() for p in belated_payments],
        }
    )
