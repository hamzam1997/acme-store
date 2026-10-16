"""Routes for managing back-in-stock alert subscriptions and replenishment notifications."""

from flask import Blueprint, current_app, jsonify, request

from integrations.notifications_client import (
    NotificationsClient,
    NotificationsClientError,
)
from models import StockNotification
import store

bp = Blueprint("stock_alerts", __name__)

_injected_notifications_client: NotificationsClient | None = None


def get_notifications_client() -> NotificationsClient:
    """Retrieve the notifications client, respecting dependency injection."""
    if current_app:
        app_client = current_app.config.get("NOTIFICATIONS_CLIENT")
        if app_client is not None:
            return app_client

    if _injected_notifications_client is not None:
        return _injected_notifications_client

    return NotificationsClient()


def set_notifications_client(client: NotificationsClient | None) -> None:
    """Set a module-level notification client for dependency injection."""
    global _injected_notifications_client
    _injected_notifications_client = client


def trigger_stock_replenishment_alerts(
    product_id: str | int,
    client: NotificationsClient | None = None,
    product_name: str | None = None,
) -> list[StockNotification]:
    """Send back-in-stock email notifications to all pending subscribers for a product."""
    notifications_client = client or get_notifications_client()
    clean_product_id = str(product_id).strip()
    pending = store.get_pending_notifications_for_product(clean_product_id)

    dispatched: list[StockNotification] = []
    for notif in pending:
        notifications_client.send_back_in_stock_email(
            to_email=notif.email,
            product_id=notif.product_id,
            product_name=product_name,
        )
        store.mark_notification_sent(notif.id)
        dispatched.append(notif)

    return dispatched


@bp.route("/stock-alerts", methods=["GET"])
def list_stock_alerts():
    """List stock alert subscriptions, optionally filtered by product_id and/or status."""
    product_id = request.args.get("product_id")
    status = request.args.get("status")
    alerts = store.get_stock_notifications(product_id=product_id, status=status)
    return jsonify([alert.to_dict() for alert in alerts])


@bp.route("/stock-alerts/<int:alert_id>", methods=["GET"])
def get_stock_alert(alert_id: int):
    """Retrieve a single stock alert subscription by ID."""
    alert = store.stock_notifications.get(alert_id)
    if alert is None:
        return jsonify({"error": "stock alert not found"}), 404
    return jsonify(alert.to_dict())


@bp.route("/stock-alerts", methods=["POST"])
@bp.route("/stock-alerts/subscribe", methods=["POST"])
def subscribe_stock_alert():
    """Register a customer email for back-in-stock alerts."""
    body = request.get_json(silent=True) or {}
    product_id = body.get("product_id")
    user_id = body.get("user_id")
    email = body.get("email")

    if not product_id or str(product_id).strip() == "":
        return jsonify({"error": "product_id is required"}), 400

    if user_id is not None and not email:
        user = store.users.get(user_id)
        if user is None:
            return jsonify({"error": "unknown user"}), 400
        email = user.email

    if not email or not isinstance(email, str) or "@" not in email.strip():
        return jsonify({"error": "valid email is required"}), 400

    clean_email = email.strip()
    clean_product_id = str(product_id).strip()

    alert = store.add_stock_notification(clean_product_id, clean_email)
    return jsonify(alert.to_dict()), 201


@bp.route("/stock-alerts/replenish", methods=["POST"])
@bp.route("/stock-alerts/notify", methods=["POST"])
def replenish_stock():
    """Handle replenishment events and send email alerts if inventory is positive."""
    body = request.get_json(silent=True) or {}
    product_id = body.get("product_id")

    if not product_id or str(product_id).strip() == "":
        return jsonify({"error": "product_id is required"}), 400

    clean_product_id = str(product_id).strip()
    product_name = body.get("product_name")

    # Inventory quantity checks
    inventory = None
    for key in ("inventory", "inventory_count", "quantity", "count", "stock"):
        if key in body:
            inventory = body[key]
            break

    if inventory is not None:
        if not isinstance(inventory, (int, float)):
            return jsonify({"error": "inventory must be a numeric value"}), 400
        if inventory <= 0:
            return (
                jsonify(
                    {
                        "message": "inventory is not positive; no alerts dispatched",
                        "product_id": clean_product_id,
                        "notified_count": 0,
                        "notifications": [],
                    }
                ),
                200,
            )

    client = get_notifications_client()
    try:
        dispatched = trigger_stock_replenishment_alerts(
            clean_product_id, client=client, product_name=product_name
        )
    except NotificationsClientError as exc:
        return jsonify({"error": str(exc)}), 502

    return (
        jsonify(
            {
                "product_id": clean_product_id,
                "notified_count": len(dispatched),
                "notifications": [item.to_dict() for item in dispatched],
            }
        ),
        200,
    )
