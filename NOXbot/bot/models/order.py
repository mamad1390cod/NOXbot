"""Order models."""

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin, UUIDMixin


class OrderStatus(str, enum.Enum):
    """Full order lifecycle status."""

    PENDING = "pending"  # Order created, before payment instructions
    WAITING_PAYMENT = "waiting_payment"  # Payment instructions shown, waiting for receipt
    PAYMENT_UPLOADED = "payment_uploaded"  # User submitted receipt
    PAYMENT_REVIEWING = "payment_reviewing"  # Admin started reviewing the receipt
    APPROVED = "approved"  # Payment approved
    PREPARING = "preparing"  # Admin preparing the product
    DELIVERED = "delivered"  # Product sent to customer
    COMPLETED = "completed"  # Order fully closed
    CANCELLED = "cancelled"  # Cancelled (before payment or by admin)
    REFUNDED = "refunded"  # Money returned
    REJECTED = "rejected"  # Payment rejected / order refused

    @property
    def label(self) -> str:
        """Persian label for a status."""
        return STATUS_LABELS[self]


STATUS_LABELS: dict[OrderStatus, str] = {
    OrderStatus.PENDING: "⏳ در انتظار",
    OrderStatus.WAITING_PAYMENT: "💳 در انتظار پرداخت",
    OrderStatus.PAYMENT_UPLOADED: "📤 رسید ارسال شد",
    OrderStatus.PAYMENT_REVIEWING: "🕵️ در حال بررسی رسید",
    OrderStatus.APPROVED: "✅ تایید شده",
    OrderStatus.PREPARING: "🔧 در حال آماده‌سازی",
    OrderStatus.DELIVERED: "📦 ارسال شد",
    OrderStatus.COMPLETED: "🎉 تکمیل شده",
    OrderStatus.CANCELLED: "🚫 لغو شده",
    OrderStatus.REFUNDED: "💰 بازگشت وجه",
    OrderStatus.REJECTED: "❌ رد شده",
}


class PaymentMethod(str, enum.Enum):
    """Payment methods."""

    CARD = "card"  # Bank card transfer
    CRYPTO = "crypto"  # Cryptocurrency
    BALANCE = "balance"  # User balance
    FREE = "free"  # Free order


class Order(Base, UUIDMixin, TimestampMixin):
    """Order model with full lifecycle tracking."""

    __tablename__ = "orders"

    # Human-readable order number, e.g. NOX-2026-000001
    order_number: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus),
        default=OrderStatus.PENDING,
        nullable=False,
        index=True,
    )
    payment_method: Mapped[PaymentMethod | None] = mapped_column(
        Enum(PaymentMethod),
        nullable=True,
    )

    # Amounts
    total_amount: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    discount_amount: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    final_amount: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    coupon_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Notes
    internal_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # Admin-only notes
    customer_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # Visible to customer
    cancellation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    refund_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Lifecycle timestamps
    payment_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    payment_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )  # = approved_at
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    preparing_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    refunded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Delivery timing
    estimated_delivery_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Admin attribution
    approved_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    delivered_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cancelled_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rejected_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Linked support ticket
    linked_ticket_id: Mapped[str | None] = mapped_column(
        ForeignKey("tickets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Optional: if this order came from a custom registration
    custom_registration_id: Mapped[str | None] = mapped_column(
        ForeignKey("custom_registrations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="orders",
        foreign_keys=[user_id],
    )
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    status_events: Mapped[list["OrderStatusEvent"]] = relationship(
        "OrderStatusEvent",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusEvent.created_at",
    )
    approved_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[approved_by_id],
    )
    delivered_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[delivered_by_id],
    )
    cancelled_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[cancelled_by_id],
    )
    rejected_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[rejected_by_id],
    )
    linked_ticket: Mapped["Ticket | None"] = relationship(
        "Ticket",
        foreign_keys=[linked_ticket_id],
    )
    delivery: Mapped["OrderDelivery | None"] = relationship(
        "OrderDelivery",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_orders_status_created", "status", "created_at"),
    )

    @property
    def is_paid(self) -> bool:
        """Check if order is paid (payment approved)."""
        return self.status in (
            OrderStatus.APPROVED,
            OrderStatus.PREPARING,
            OrderStatus.DELIVERED,
            OrderStatus.COMPLETED,
        )

    @property
    def is_active(self) -> bool:
        """Order is in an active (non-terminal) state."""
        return self.status not in (
            OrderStatus.CANCELLED,
            OrderStatus.REFUNDED,
            OrderStatus.REJECTED,
            OrderStatus.COMPLETED,
        )

    @property
    def can_cancel(self) -> bool:
        """Order can be cancelled (before payment or while pending review)."""
        return self.status in (
            OrderStatus.PENDING,
            OrderStatus.WAITING_PAYMENT,
            OrderStatus.PAYMENT_UPLOADED,
            OrderStatus.PAYMENT_REVIEWING,
        )

    @property
    def status_label(self) -> str:
        """Persian label of the current status."""
        return STATUS_LABELS[self.status]

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, number={self.order_number}, status={self.status}, amount={self.final_amount})>"


class OrderItem(Base, UUIDMixin, TimestampMixin):
    """Individual item in an order."""

    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[str | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    config_product_id: Mapped[str | None] = mapped_column(
        ForeignKey("config_products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    unit_price: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    total_price: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    product_title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    product_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    # For account type products - store delivered account info
    delivered_data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # JSON: {"username": "...", "email": "...", "password": "..."}

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="items",
    )
    product: Mapped["Product | None"] = relationship(
        "Product",
        back_populates="order_items",
    )
    config_product: Mapped["ConfigProduct | None"] = relationship(
        "ConfigProduct",
        back_populates="order_items",
    )

    def __repr__(self) -> str:
        return f"<OrderItem(id={self.id}, order_id={self.order_id}, title={self.product_title}, qty={self.quantity})>"

class OrderDelivery(Base, UUIDMixin, TimestampMixin):
    """Config delivery data for an order.

    Stores the config text/file that admin prepares before sending to customer.
    Status flow: draft → delivered (on order complete) or failed (send error).
    """

    __tablename__ = "order_deliveries"

    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    delivery_type: Mapped[str] = mapped_column(
        String(20),
        default="config_text",
        nullable=False,
    )  # "config_text", "config_file", "mixed"
    config_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Telegram file_id
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",
        nullable=False,
    )  # "draft", "delivered", "failed"
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="delivery")
    created_by: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return f"<OrderDelivery(order_id={self.order_id}, type={self.delivery_type}, status={self.status})>"
