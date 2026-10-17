"""Core domain models for the Acme Store."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class User:
    id: int
    name: str
    email: str


@dataclass
class Order:
    id: int
    user_id: int
    total_cents: int
    status: str = "placed"
    created_at: datetime = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "total_cents": self.total_cents,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Payment:
    id: int
    order_id: int
    amount_cents: int
    status: str = "captured"
    provider_ref: str = ""
    refund_requested_at: datetime | None = None
    refunded_at: datetime | None = None
    created_at: datetime = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "order_id": self.order_id,
            "amount_cents": self.amount_cents,
            "status": self.status,
            "provider_ref": self.provider_ref,
            "refund_requested_at": (
                self.refund_requested_at.isoformat()
                if self.refund_requested_at
                else None
            ),
            "refunded_at": self.refunded_at.isoformat() if self.refunded_at else None,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Product:
    id: int
    name: str
    price_cents: int
    stock: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "price_cents": self.price_cents,
            "stock": self.stock,
        }


@dataclass
class StockAlert:
    id: int
    product_id: int
    email: str
    user_id: int | None = None
    status: str = "pending"
    created_at: datetime = field(default_factory=_now)
    sent_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "user_id": self.user_id,
            "email": self.email,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }

