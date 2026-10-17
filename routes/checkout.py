from flask import Blueprint, jsonify, request

import store
from integrations.payments_gateway import PaymentsGateway, PaymentsGatewayError
from models import Order, Payment

bp = Blueprint("checkout", __name__)


@bp.route("/checkout", methods=["POST"])
def checkout():
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    total_cents = body.get("total_cents")
    idempotency_key = body.get("idempotency_key")

    if idempotency_key:
        existing_order = store.get_order_by_idempotency_key(idempotency_key)
        if existing_order:
            existing_payment = store.payment_for_order(existing_order.id)
            return jsonify({"order": existing_order.to_dict(), "payment": existing_payment.to_dict() if existing_payment else None}), 200

    if user_id not in store.users:
        return jsonify({"error": "unknown user"}), 400
    if not isinstance(total_cents, int) or total_cents <= 0:
        return jsonify({"error": "total_cents must be a positive integer"}), 400

    order = Order(id=store.next_id("order"), user_id=user_id, total_cents=total_cents, idempotency_key=idempotency_key)
    store.orders[order.id] = order

    gateway = PaymentsGateway()
    try:
        charge = gateway.charge(total_cents, description=f"order {order.id}", idempotency_key=idempotency_key)
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

    return jsonify({"order": order.to_dict(), "payment": payment.to_dict()}), 201
