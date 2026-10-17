from flask import Blueprint, jsonify, request

import store
from integrations.payments_gateway import PaymentsGateway, PaymentsGatewayError
from datetime import datetime, timezone

bp = Blueprint("orders", __name__)



@bp.route("/orders")
def list_orders():
    return jsonify([order.to_dict() for order in store.orders.values()])


@bp.route("/orders/<int:order_id>")
def get_order(order_id: int):
    order = store.orders.get(order_id)
    if order is None:
        return jsonify({"error": "order not found"}), 404

    payload = order.to_dict()
    payment = store.payment_for_order(order_id)
    payload["payment"] = payment.to_dict() if payment else None
    return jsonify(payload)


@bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
def cancel_order(order_id: int):
    # To support injection in tests
    gateway = request.environ.get("acme.payments_gateway")
    
    order = store.orders.get(order_id)
    if order is None:
        return jsonify({"error": "order not found"}), 404
    
    if order.status != "pending":
        return jsonify({"error": "order is not pending"}), 400
    
    payment = store.payment_for_order(order_id)
    if payment is None:
        return jsonify({"error": "no payment for that order"}), 404
    
    if gateway is None:
        gateway = PaymentsGateway()
        
    try:
        gateway.refund(payment.provider_ref)
    except PaymentsGatewayError as exc:
        return jsonify({"error": str(exc)}), 502
    
    order.status = "cancelled"
    payment.status = "refund_requested"
    payment.refund_requested_at = datetime.now(timezone.utc)
    
    payload = order.to_dict()
    payload["payment"] = payment.to_dict()
    return jsonify(payload), 200

