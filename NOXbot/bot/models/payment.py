"""Payment model."""

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin, UUIDMixin


class PaymentStatus(str, enum.Enum):
    """Payment status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class PaymentMethod(str, enum.Enum):
    """Payment methods."""

    CARD = "card"
    CRYPTO = "crypto"
    BALANCE = "balance"
    FREE = "free"


class Payment(Base, UUIDMixin, TimestampMixin):
    """Payment model."""

    __tablename__ = "payments"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[str | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    custom_registration_id: Mapped[str | None] = mapped_column(
        ForeignKey("custom_registrations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod),
        default=PaymentMethod.CARD,
        nullable=False,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus),
        default=PaymentStatus.PENDING,
        nullable=False,
        index=True,
    )
    receipt_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    card_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    card_holder: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    bank_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    transaction_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reject_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="payments",
        foreign_keys=[user_id],
    )
    order: Mapped["Order | None"] = relationship(
        "Order",
        back_populates="payments",
    )
    custom_registration: Mapped["CustomRegistration | None"] = relationship(
        "CustomRegistration",
    )
    reviewed_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[reviewed_by],
    )

    @property
    def is_pending(self) -> bool:
        """Check if payment is pending."""
        return self.status == PaymentStatus.PENDING

    @property
    def is_approved(self) -> bool:
        """Check if payment is approved."""
        return self.status == PaymentStatus.APPROVED

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, user_id={self.user_id}, amount={self.amount}, status={self.status})>"