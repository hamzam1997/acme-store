from flask import Blueprint, jsonify, request

import store

bp = Blueprint("orders", __name__)


@bp.route("/orders")
def list_orders():
    email = request.args.get("email")
    if email is not None:
        user = store.get_user_by_email(email)
        if user is None:
            return jsonify([])
        
        filtered_orders = [order for order in store.orders.values() if order.user_id == user.id]
        sorted_orders = sorted(filtered_orders, key=lambda o: o.created_at, reverse=True)
        return jsonify([order.to_dict() for order in sorted_orders])

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
