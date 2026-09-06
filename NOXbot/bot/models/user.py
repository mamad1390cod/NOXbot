"""User model."""

from datetime import datetime
from sqlalchemy import (
    Integer,
    Boolean,
    DateTime,
    Enum,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin, UUIDMixin
import enum


class UserRole(str, enum.Enum):
    """User roles."""

    USER = "user"
    ADMIN = "admin"
    BANNED = "banned"


class User(Base, UUIDMixin, TimestampMixin):
    """Telegram user model."""

    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        nullable=False,
        index=True,
    )
    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    first_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    last_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    @property
    def display_name(self) -> str:
        """Return the best available display name for the user."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        if self.first_name:
            return self.first_name
        if self.username:
            return f"@{self.username}"
        return str(self.telegram_id)
    language_code: Mapped[str] = mapped_column(
        String(10),
        default="fa",
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        default=UserRole.USER,
        nullable=False,
        index=True,
    )
    is_banned: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    ban_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    
    # --- Customer info (for orders) ---
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    customer_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    
    # --- Anti-abuse state ---
    violation_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    muted_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    abuse_suspended_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    whitelisted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    blacklisted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    blacklist_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    # --- User dashboard / wallet ---
    wallet_balance: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    reward_points: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    # JSON: {"promos":"on","orders":"on", ...} — per-category notification opt-in.
    notification_preferences: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    referred_by: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    referral_code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )
    total_spent: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_activity: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    achievements: Mapped[list["Achievement"]] = relationship(
        "Achievement",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    admin_profile: Mapped["AdminProfile | None"] = relationship(
        "AdminProfile",
        back_populates="user",
        foreign_keys="AdminProfile.user_id",
    )
    cart: Mapped["Cart"] = relationship(
        "Cart",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    custom_cart: Mapped["CustomCart"] = relationship(
        "CustomCart",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Order.user_id",
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Ticket.user_id",
    )
    custom_registrations: Mapped[list["CustomRegistration"]] = relationship(
        "CustomRegistration",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="CustomRegistration.user_id",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Payment.user_id",
    )
    wishlist: Mapped[list["WishlistItem"]] = relationship(
        "WishlistItem",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="WishlistItem.user_id",
    )
    wallet_ledger: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Transaction.user_id",
    )
    topup_requests: Mapped[list["TopUpRequest"]] = relationship(
        "TopUpRequest",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="TopUpRequest.user_id",
    )