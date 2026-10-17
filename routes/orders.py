from flask import Blueprint, jsonify

import store

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
    
    if payment:
        payload["refund_status"] = payment.status
        payload["refund_requested_at"] = payment.refund_requested_at.isoformat() if payment.refund_requested_at else None
    else:
        payload["refund_status"] = None
        payload["refund_requested_at"] = None
        
    return jsonify(payload)
