"""User dashboard data models — wishlist, wallet ledger, achievements, badges."""

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
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


class TransactionType(str, enum.Enum):
    """Wallet transaction types."""

    DEPOSIT = "deposit"
    SPEND = "spend"
    REWARD = "reward"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    TOPUP = "topup"
    ADMIN_CREDIT = "admin_credit"
    ADMIN_DEBIT = "admin_debit"
    PURCHASE = "purchase"
    CUSTOM_REGISTRATION = "custom_registration"


class WishlistItem(Base, UUIDMixin, TimestampMixin):
    """A product/config saved by a user for later (separate from the cart)."""

    __tablename__ = "wishlist_items"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[str | None] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=True,
    )
    config_product_id: Mapped[str | None] = mapped_column(
        ForeignKey("config_products.id", ondelete="CASCADE"),
        nullable=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="wishlist")
    product: Mapped["Product | None"] = relationship("Product")
    config_product: Mapped["ConfigProduct | None"] = relationship("ConfigProduct")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_wishlist_product"),
        UniqueConstraint("user_id", "config_product_id", name="uq_wishlist_config"),
    )

    @property
    def title(self) -> str:
        if self.product:
            return self.product.title
        if self.config_product:
            return self.config_product.title
        return "نامشخص"

    @property
    def price(self) -> int:
        if self.product:
            return self.product.discounted_price
        if self.config_product:
            return self.config_product.price
        return 0

    def __repr__(self) -> str:
        return f"<WishlistItem(user={self.user_id}, product={self.product_id}, config={self.config_product_id})>"


class Transaction(Base, UUIDMixin, TimestampMixin):
    """A wallet/points ledger entry."""

    __tablename__ = "transactions"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType),
        nullable=False,
        index=True,
    )
    amount: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    balance_before: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    balance_after: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    ref_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    admin_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="wallet_ledger", foreign_keys=[user_id])
    admin: Mapped["User | None"] = relationship("User", foreign_keys=[admin_id])

    __table_args__ = (
        Index("ix_transactions_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Transaction(user={self.user_id}, type={self.type}, amount={self.amount})>"


class Badge(Base, UUIDMixin):
    """Achievement catalog row (seeded)."""

    __tablename__ = "badges"

    key: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    icon: Mapped[str] = mapped_column(
        String(20),
        default="🎖",
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Badge(key={self.key}, name={self.name})>"


class Achievement(Base, UUIDMixin, TimestampMixin):
    """A badge unlocked by a user."""

    __tablename__ = "achievements"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    badge_key: Mapped[str] = mapped_column(
        ForeignKey("badges.key", ondelete="RESTRICT"),
        nullable=False,
    )
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="achievements")
    badge: Mapped["Badge"] = relationship("Badge")

    __table_args__ = (
        UniqueConstraint("user_id", "badge_key", name="uq_achievement_user_badge"),
    )

    def __repr__(self) -> str:
        return f"<Achievement(user={self.user_id}, badge={self.badge_key})>"