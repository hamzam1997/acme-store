import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request

import store
from integrations.notifications_client import (
    NotificationsClient,
    NotificationsClientError,
)
from integrations.payments_gateway import PaymentsGateway, PaymentsGatewayError

bp = Blueprint("refunds", __name__)

DEFAULT_DELAY_THRESHOLD_DAYS = int(
    os.environ.get("DELAYED_REFUND_THRESHOLD_DAYS", 3)
)

_notifications_client: NotificationsClient | None = None


def get_notifications_client() -> NotificationsClient:
    global _notifications_client
    if _notifications_client is not None:
        return _notifications_client
    try:
        if current_app and "NOTIFICATIONS_CLIENT" in current_app.config:
            return current_app.config["NOTIFICATIONS_CLIENT"]
    except Exception:
        pass
    return NotificationsClient()


def set_notifications_client(client: NotificationsClient | None) -> None:
    global _notifications_client
    _notifications_client = client


def check_and_notify_delayed_refunds(
    threshold_days: int | None = None,
    client: NotificationsClient | None = None,
) -> dict:
    """Scan refund_requested payments older than threshold_days and notify customers."""
    now = datetime.now(timezone.utc)
    threshold = (
        threshold_days
        if threshold_days is not None
        else DEFAULT_DELAY_THRESHOLD_DAYS
    )
    cutoff = now - timedelta(days=threshold)
    notifications_client = client or get_notifications_client()

    notified = []
    failed = []
    scanned_count = 0
    delayed_count = 0

    for payment in sorted(store.payments.values(), key=lambda p: p.id):
        if payment.status != "refund_requested":
            continue
        scanned_count += 1
        if payment.refund_requested_at is None:
            continue
        if payment.refund_requested_at > cutoff:
            continue
        delayed_count += 1
        if payment.last_delayed_notice_at is not None:
            # Already notified of delay; prevent duplicate sends
            continue

        order = store.orders.get(payment.order_id)
        if not order:
            failed.append({
                "payment_id": payment.id,
                "error": f"order {payment.order_id} not found",
            })
            continue

        user = store.users.get(order.user_id)
        if not user or not user.email:
            failed.append({
                "payment_id": payment.id,
                "order_id": order.id,
                "error": f"user or email not found for order {order.id}",
            })
            continue

        try:
            response = notifications_client.send_delayed_refund_notice(
                recipient_email=user.email,
                customer_name=user.name,
                order_id=order.id,
                amount_cents=payment.amount_cents,
                refund_requested_at=payment.refund_requested_at.isoformat(),
            )
            payment.last_delayed_notice_at = now
            notified.append({
                "payment_id": payment.id,
                "order_id": order.id,
                "recipient_email": user.email,
                "customer_name": user.name,
                "amount_cents": payment.amount_cents,
                "notification_id": response.get("notification_id"),
                "status": response.get("status"),
            })
        except Exception as exc:
            failed.append({
                "payment_id": payment.id,
                "order_id": order.id,
                "recipient_email": user.email,
                "error": str(exc),
            })

    return {
        "threshold_days": threshold,
        "scanned_count": scanned_count,
        "delayed_count": delayed_count,
        "notified_count": len(notified),
        "failed_count": len(failed),
        "notified": notified,
        "failed": failed,
    }


@bp.route("/refunds")
def list_refunds():
    """Every payment currently awaiting or completing a refund."""
    pending = [
        payment.to_dict()
        for payment in store.payments.values()
        if payment.status in ("refund_requested", "refunded")
    ]
    return jsonify(pending)


@bp.route("/refunds/notify-delayed", methods=["POST"])
def notify_delayed_refunds():
    """Trigger automated notification emails for delayed refunds."""
    body = request.get_json(silent=True) or {}
    raw_threshold = body.get("threshold_days")
    if raw_threshold is None and "threshold_days" in request.args:
        raw_threshold = request.args.get("threshold_days")

    threshold_days = None
    if raw_threshold is not None:
        try:
            threshold_days = int(raw_threshold)
            if threshold_days < 0:
                return jsonify({"error": "threshold_days must be non-negative"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "invalid threshold_days parameter"}), 400

    results = check_and_notify_delayed_refunds(threshold_days=threshold_days)
    return jsonify(results), 200


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
