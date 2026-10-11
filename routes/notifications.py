
from flask import Blueprint, jsonify
from datetime import datetime, timedelta, timezone

import store
from integrations.notifications_service import NotificationsService

notifications_bp = Blueprint("notifications", __name__, url_prefix="/tasks")

DELAY_THRESHOLD = timedelta(days=3)
NOTIFICATION_TEMPLATE_ID = "refund_delayed" # Assumed template

@notifications_bp.route("/send-delayed-refund-notifications", methods=["POST"])
def send_delayed_refund_notifications():
    """
    Scheduled task to notify customers about delayed refunds.
    This is an internal endpoint, not exposed to the public API.
    """
    notifications_service = NotificationsService()
    if not notifications_service.configured:
        return jsonify({"error": "Notifications service not configured"}), 500

    now = datetime.now(timezone.utc)
    notifications_sent = 0

    for payment in store.payments.values():
        if (
            payment.refund_requested_at
            and not payment.refunded_at
            and not payment.delay_notification_sent_at
            and (now - payment.refund_requested_at) > DELAY_THRESHOLD
        ):
            order = store.orders.get(payment.order_id)
            if not order:
                continue

            user = store.users.get(order.user_id)
            if not user:
                continue

            try:
                notifications_service.send_email(
                    email_address=user.email,
                    template_id=NOTIFICATION_TEMPLATE_ID,
                    template_context={
                        "order_id": order.id,
                        "refund_amount": payment.amount_cents / 100,
                    },
                )
                payment.delay_notification_sent_at = now
                notifications_sent += 1
            except Exception as e:
                # In a real app, we'd log this error and maybe retry
                print(f"Failed to send notification for order {order.id}: {e}")

    return jsonify({"notifications_sent": notifications_sent})
