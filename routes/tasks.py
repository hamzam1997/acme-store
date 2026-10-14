from flask import Blueprint, jsonify
from datetime import datetime, timedelta, timezone
from store import get_all_payments, get_user_by_id, get_order_by_id
from integrations.notifications_client import notifications_client

tasks_blueprint = Blueprint("tasks", __name__)

DELAY_THRESHOLD_DAYS = 3

@tasks_blueprint.route("/tasks/notify-delayed-refunds", methods=["POST"])
def notify_delayed_refunds():
    """Identifies delayed refunds and triggers email notifications to customers."""
    now = datetime.now(timezone.utc)
    notifications_sent = []

    for payment in get_all_payments():
        if payment.status == "refund_requested" and payment.refund_requested_at:
            refund_age = now - payment.refund_requested_at
            if refund_age > timedelta(days=DELAY_THRESHOLD_DAYS):
                order = get_order_by_id(payment.order_id)
                if order:
                    user = get_user_by_id(order.user_id)
                    if user:
                        subject = f"Update on your refund for order #{order.id}"
                        message = f"Hi {user.name}, we're still processing your refund for order #{order.id}. We'll notify you again as soon as it's complete."
                        
                        response = notifications_client.send_email(
                            email=user.email,
                            subject=subject,
                            message=message
                        )
                        notifications_sent.append(
                            {
                                "user_id": user.id,
                                "order_id": order.id,
                                "notification_status": response.get("status")
                            }
                        )

    return jsonify({"notifications_sent": notifications_sent}), 200
