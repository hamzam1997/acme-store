from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

import store
from integrations.payments_gateway import PaymentsGateway, PaymentsGatewayError
from integrations.notifications import NotificationsClient, NotificationsError

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


def check_and_notify_delayed_refunds(notifications: NotificationsClient) -> int:
    threshold_days = 3
    threshold = datetime.now(timezone.utc) - timedelta(days=threshold_days)
    notified_count = 0

    for payment in store.payments.values():
        if payment.status == "refund_requested" and payment.refund_requested_at and payment.refund_requested_at < threshold:
            order = store.orders.get(payment.order_id)
            if not order:
                continue
            user = store.users.get(order.user_id)
            if not user:
                continue

            try:
                notifications.send_email(
                    to_email=user.email,
                    subject="Update on your refund",
                    body=f"Hi {user.name}, your refund for order {order.id} is still in progress."
                )
                notified_count += 1
            except NotificationsError:
                pass
    return notified_count


@bp.route("/refunds/notify-delayed", methods=["POST"])
def notify_delayed_refunds():
    notifications = NotificationsClient()
    notified_count = check_and_notify_delayed_refunds(notifications)
    return jsonify({"notified_count": notified_count}), 200
