"""Routes and handlers for stock alert subscriptions and restocking events."""

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

import store
from integrations.notifications_client import (
    NotificationsClient,
    NotificationsClientError,
)
from models import StockAlert

bp = Blueprint("stock_alerts", __name__)


def get_notifications_client() -> NotificationsClient:
    """Retrieve injected notifications client or initialize default."""
    if current_app:
        client = current_app.config.get("NOTIFICATIONS_CLIENT")
        if client is not None:
            return client
    return NotificationsClient()


def restock_product(
    product_id: int, quantity: int, client: NotificationsClient | None = None
) -> dict:
    """Restock a product and trigger alerts if stock transitioned from 0 to positive."""
    if not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("quantity must be a positive integer")

    product = store.products.get(product_id)
    if product is None:
        raise KeyError(f"product {product_id} not found")

    previous_stock = product.stock
    product.stock += quantity
    transitioned = previous_stock == 0 and product.stock > 0

    sent_alerts: list[StockAlert] = []
    failed_alerts: list[dict] = []

    if transitioned:
        notifier = client or get_notifications_client()
        pending = store.pending_alerts_for_product(product_id)

        for alert in pending:
            try:
                notifier.send_back_in_stock_email(
                    to_email=alert.email,
                    product_id=product.id,
                    product_name=product.name,
                    stock_quantity=product.stock,
                )
                alert.status = "sent"
                alert.sent_at = datetime.now(timezone.utc)
                sent_alerts.append(alert)
            except NotificationsClientError as exc:
                failed_alerts.append(
                    {"alert_id": alert.id, "email": alert.email, "error": str(exc)}
                )

    return {
        "product": product.to_dict(),
        "previous_stock": previous_stock,
        "transitioned": transitioned,
        "notifications_sent": len(sent_alerts),
        "alerts": [a.to_dict() for a in sent_alerts],
        "failed": failed_alerts,
    }


@bp.route("/products", methods=["GET"])
def list_products():
    """List all products in catalog."""
    return jsonify([p.to_dict() for p in store.products.values()])


@bp.route("/products/<int:product_id>", methods=["GET"])
def get_product(product_id: int):
    """Retrieve details for a single product."""
    product = store.products.get(product_id)
    if product is None:
        return jsonify({"error": "product not found"}), 404
    return jsonify(product.to_dict())


@bp.route("/stock-alerts", methods=["POST"])
def subscribe_stock_alert():
    """Subscribe a customer to back-in-stock notifications for a sold-out product."""
    body = request.get_json(silent=True) or {}
    product_id = body.get("product_id")
    email = body.get("email")
    user_id = body.get("user_id")

    if product_id is None or not isinstance(product_id, int):
        return jsonify({"error": "product_id is required"}), 400

    product = store.products.get(product_id)
    if product is None:
        return jsonify({"error": "product not found"}), 404

    if product.stock > 0:
        return jsonify({"error": "product is currently in stock"}), 400

    if user_id is not None:
        if user_id not in store.users:
            return jsonify({"error": "unknown user"}), 400
        if not email:
            email = store.users[user_id].email

    if not email or not isinstance(email, str) or "@" not in email:
        return jsonify({"error": "valid email is required"}), 400

    email = email.strip()

    if store.find_pending_alert(product_id, email):
        return (
            jsonify(
                {"error": "already subscribed to back-in-stock alerts for this product"}
            ),
            409,
        )

    alert = StockAlert(
        id=store.next_id("stock_alert"),
        product_id=product_id,
        email=email,
        user_id=user_id,
        status="pending",
    )
    store.stock_alerts[alert.id] = alert

    return jsonify(alert.to_dict()), 201


@bp.route("/stock-alerts", methods=["GET"])
def list_stock_alerts():
    """List stock alert subscriptions with optional filters."""
    product_id_param = request.args.get("product_id")
    status_param = request.args.get("status")

    alerts = list(store.stock_alerts.values())

    if product_id_param is not None:
        try:
            p_id = int(product_id_param)
            alerts = [a for a in alerts if a.product_id == p_id]
        except ValueError:
            return jsonify({"error": "invalid product_id parameter"}), 400

    if status_param:
        alerts = [a for a in alerts if a.status == status_param]

    return jsonify([a.to_dict() for a in alerts])


@bp.route("/stock-alerts/<int:alert_id>", methods=["GET"])
def get_stock_alert(alert_id: int):
    """Retrieve details for a single stock alert subscription."""
    alert = store.stock_alerts.get(alert_id)
    if alert is None:
        return jsonify({"error": "stock alert not found"}), 404
    return jsonify(alert.to_dict())


@bp.route("/stock-alerts/<int:alert_id>", methods=["DELETE"])
def cancel_stock_alert(alert_id: int):
    """Cancel a pending stock alert subscription."""
    alert = store.stock_alerts.get(alert_id)
    if alert is None:
        return jsonify({"error": "stock alert not found"}), 404

    alert.status = "cancelled"
    return jsonify(alert.to_dict())


@bp.route("/products/<int:product_id>/restock", methods=["POST"])
def restock_product_route(product_id: int):
    """Restock a product by ID and trigger alerts if stock transitioned from 0."""
    body = request.get_json(silent=True) or {}
    quantity = body.get("quantity")

    try:
        result = restock_product(
            product_id, quantity, client=get_notifications_client()
        )
        return jsonify(result), 200
    except KeyError:
        return jsonify({"error": "product not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.route("/stock-alerts/restock", methods=["POST"])
def restock_via_stock_alerts():
    """Restock endpoint accepting product_id and quantity in body."""
    body = request.get_json(silent=True) or {}
    product_id = body.get("product_id")
    quantity = body.get("quantity")

    if product_id is None or not isinstance(product_id, int):
        return jsonify({"error": "product_id is required"}), 400

    try:
        result = restock_product(
            product_id, quantity, client=get_notifications_client()
        )
        return jsonify(result), 200
    except KeyError:
        return jsonify({"error": "product not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
