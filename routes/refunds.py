from datetime import datetime, timezone, timedelta
import os

from flask import Blueprint, jsonify, request

import store
from integrations.payments_gateway import PaymentsGateway, PaymentsGatewayError
from integrations import notifications_service

bp = Blueprint("refunds", __name__)


@bp.route("/refunds")
def list_refunds():
    """Every payment currently awaiting or completing a refund."""
    pending = [
        payment.to_dict()
        for payment in store.payments.values()
        if payment.status in ("refund_requested", "refunded")
    ]
    return jsonify(pending)


@bp.route("/refunds", methods=["POST"])
def request_refund():
    body = request.get_json(silent=True) or {}
    order_id = body.get("order_id")

    payment = store.payment_for_order(order_id) if order_id else None
    if payment is None:
        return jsonify({"error": "no payment for that order"}), 404
    if payment.status != "captured":
        return jsonify({"error": f"payment is {payment.status}"}), 409

    gateway = PaymentsGateway()
    try:
        gateway.refund(payment.provider_ref)
    except PaymentsGatewayError as exc:
        return jsonify({"error": str(exc)}), 502

    payment.status = "refund_requested"
    payment.refund_requested_at = datetime.now(timezone.utc)

    return jsonify(payment.to_dict()), 202

@bp.route("/internal/notify-delayed-refunds", methods=["POST"])
def notify_delayed_refunds():
    """Notify customers about delayed refunds."""
    delay_days = int(os.environ.get("REFUND_DELAY_DAYS", 3))
    now = datetime.now(timezone.utc)
    notified_count = 0

    for payment in store.payments.values():
        if (
            payment.status == "refund_requested"
            and payment.refund_requested_at
            and (now - payment.refund_requested_at) > timedelta(days=delay_days)
            and not payment.delayed_notification_sent_at
        ):
            order = store.orders.get(payment.order_id)
            if not order:
                continue
            user = store.users.get(order.user_id)
            if not user:
                continue

            notifications_service.send_email(
                user_email=user.email,
                subject=f"Update on your refund for order #{order.id}",
                body=f"Hi {user.name}, we are still processing your refund for order #{order.id}. We will notify you again once the refund is complete.",
            )
            payment.delayed_notification_sent_at = now
            notified_count += 1

    return jsonify({"notified_count": notified_count})
