from flask import Blueprint, jsonify, Response
import io
import csv

import store

bp = Blueprint("orders", __name__)


@bp.route("/orders/export.csv")
def export_orders_csv():
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(["ID", "Customer Email", "Amount", "Status", "Creation Date"])
    
    for order in store.orders.values():
        user = store.users.get(order.user_id)
        email = user.email if user else ""
        writer.writerow([order.id, email, order.total_cents, order.status, order.created_at.isoformat()])
        
    return Response(si.getvalue(), mimetype="text/csv")


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
