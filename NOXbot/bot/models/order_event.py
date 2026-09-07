"""Order status event model — full audit trail of status transitions."""

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin, UUIDMixin
from bot.models.order import OrderStatus


class OrderStatusEvent(Base, UUIDMixin, TimestampMixin):
    """Records a single status transition for an order."""

    __tablename__ = "order_status_events"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[OrderStatus | None] = mapped_column(
        Enum(OrderStatus),
        nullable=True,
    )
    to_status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus),
        nullable=False,
    )
    changed_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_system: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )  # True if the transition happened automatically

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="status_events",
    )
    changed_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[changed_by_id],
    )

    __table_args__ = (
        Index("ix_order_status_events_order_created", "order_id", "created_at"),
    )

    @property
    def from_label(self) -> str:
        return OrderStatus(self.from_status).label if self.from_status else "—"

    @property
    def to_label(self) -> str:
        return OrderStatus(self.to_status).label

    def __repr__(self) -> str:
        return f"<OrderStatusEvent(order_id={self.order_id}, {self.from_status}→{self.to_status})>"