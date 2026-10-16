import logging
from flask import Blueprint, current_app, jsonify, request

import store
from integrations.notifications_client import (
    NotificationsClient,
    NotificationsClientError,
)
from integrations.payments_gateway import PaymentsGateway, PaymentsGatewayError
from models import Order, Payment

logger = logging.getLogger(__name__)

bp = Blueprint("checkout", __name__)

default_notifications_client = None
default_payments_gateway = None


def get_notifications_client(override=None):
    if override is not None:
        return override
    try:
        if current_app and current_app.config.get("NOTIFICATIONS_CLIENT"):
            return current_app.config["NOTIFICATIONS_CLIENT"]
    except RuntimeError:
        pass
    if default_notifications_client is not None:
        return default_notifications_client
    return NotificationsClient()


def get_payments_gateway(override=None):
    if override is not None:
        return override
    try:
        if current_app and current_app.config.get("PAYMENTS_GATEWAY"):
            return current_app.config["PAYMENTS_GATEWAY"]
    except RuntimeError:
        pass
    if default_payments_gateway is not None:
        return default_payments_gateway
    return PaymentsGateway()


@bp.route("/checkout", methods=["POST"])
def checkout(notifications_client=None, payments_gateway=None):
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    total_cents = body.get("total_cents")

    if user_id not in store.users:
        return jsonify({"error": "unknown user"}), 400
    if not isinstance(total_cents, int) or total_cents <= 0:
        return jsonify({"error": "total_cents must be a positive integer"}), 400

    order = Order(id=store.next_id("order"), user_id=user_id, total_cents=total_cents)
    store.orders[order.id] = order

    gateway = get_payments_gateway(payments_gateway)
    try:
        charge = gateway.charge(total_cents, description=f"order {order.id}")
    except PaymentsGatewayError as exc:
        return jsonify({"error": str(exc)}), 502

    payment = Payment(
        id=store.next_id("payment"),
        order_id=order.id,
        amount_cents=total_cents,
        status=charge["status"],
        provider_ref=charge["reference"],
    )
    store.payments[payment.id] = payment

    user = store.users[user_id]
    phone_number = body.get("phone_number") or getattr(user, "phone_number", None)
    sms_receipt = None
    if phone_number:
        notifier = get_notifications_client(notifications_client)
        try:
            sms_receipt = notifier.send_sms_receipt(
                to_phone=phone_number,
                order_id=order.id,
                total_cents=total_cents,
            )
        except Exception as exc:
            logger.warning("Failed to send SMS receipt for order %s: %s", order.id, exc)
            sms_receipt = {"status": "failed", "error": str(exc)}

    response_data = {"order": order.to_dict(), "payment": payment.to_dict()}
    if sms_receipt is not None:
        response_data["sms_receipt"] = sms_receipt

    return jsonify(response_data), 201
