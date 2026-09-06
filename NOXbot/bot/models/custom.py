"""Custom/Tournament models."""

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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin, UUIDMixin


class CustomStatus(str, enum.Enum):
    """Custom tournament status."""

    DRAFT = "draft"
    READY = "ready"  # Prize set, ready to open registration
    REGISTRATION_OPEN = "registration_open"
    REGISTRATION_CLOSED = "registration_closed"
    STARTED = "started"  # Tournament has started, no more registrations
    IN_PROGRESS = "in_progress"  # Legacy status, kept for backward compatibility
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CustomType(str, enum.Enum):
    """Custom tournament type."""

    FREE = "free"
    PAID = "paid"


class WinnerType(str, enum.Enum):
    """Winner selection type."""

    PLAYER = "player"
    TEAM = "team"


class CustomCategory(Base, UUIDMixin, TimestampMixin):
    """Custom tournament category model."""

    __tablename__ = "custom_categories"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    name_en: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    emoji: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Foreign key
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    customs: Mapped[list["Custom"]] = relationship(
        "Custom",
        back_populates="custom_category",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<CustomCategory(id={self.id}, name={self.name})>"


class Custom(Base, UUIDMixin, TimestampMixin):
    """Custom tournament model."""

    __tablename__ = "customs"

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    title_en: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    rules: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    type: Mapped[CustomType] = mapped_column(
        Enum(CustomType),
        default=CustomType.FREE,
        nullable=False,
    )
    status: Mapped[CustomStatus] = mapped_column(
        Enum(CustomStatus),
        default=CustomStatus.DRAFT,
        nullable=False,
        index=True,
    )
    entry_fee: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    prize: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    prize_file_id: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )  # Telegram file_id for media prizes
    prize_file_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # photo, video, document, audio, voice, text
    prize_caption: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # Caption for media prizes
    prize_set: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )  # Whether prize has been set
    start_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # Message to send when tournament starts
    banner_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    gallery: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # JSON array of image URLs
    event_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    event_time: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # e.g., "20:00"
    max_capacity: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    current_players: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    is_visible: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    registration_open: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    winner_type: Mapped[WinnerType | None] = mapped_column(
        Enum(WinnerType),
        nullable=True,
    )
    winner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    winner_team_name: Mapped[str | None] = mapped_column(
        String(255),
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
    cancel_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    view_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Foreign keys
    custom_category_id: Mapped[str | None] = mapped_column(
        ForeignKey("custom_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    custom_category: Mapped["CustomCategory | None"] = relationship(
        "CustomCategory",
        back_populates="customs",
    )
    registrations: Mapped[list["CustomRegistration"]] = relationship(
        "CustomRegistration",
        back_populates="custom",
        cascade="all, delete-orphan",
    )
    cart_items: Mapped[list["CustomCartItem"]] = relationship(
        "CustomCartItem",
        back_populates="custom",
        cascade="all, delete-orphan",
    )
    winner: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[winner_id],
    )

    @property
    def is_full(self) -> bool:
        """Check if tournament is full."""
        if self.max_capacity is None:
            return False
        return self.current_players >= self.max_capacity

    @property
    def available_slots(self) -> int | None:
        """Get available slots."""
        if self.max_capacity is None:
            return None
        return max(0, self.max_capacity - self.current_players)

    @property
    def can_register(self) -> bool:
        """Check if registration is possible."""
        return (
            self.status == CustomStatus.REGISTRATION_OPEN
            and self.registration_open
            and self.is_visible
            and not self.is_full
            and self.prize_set  # Prize must be set
        )

    def __repr__(self) -> str:
        return f"<Custom(id={self.id}, title={self.title}, status={self.status}, players={self.current_players})>"


class CustomRegistration(Base, UUIDMixin, TimestampMixin):
    """Custom tournament registration model."""

    __tablename__ = "custom_registrations"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    custom_id: Mapped[str] = mapped_column(
        ForeignKey("customs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    codm_username: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    team_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
    )  # pending, confirmed, rejected, cancelled
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    confirmed_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="custom_registrations",
        foreign_keys=[user_id],
    )
    custom: Mapped["Custom"] = relationship(
        "Custom",
        back_populates="registrations",
    )
    confirmed_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[confirmed_by],
    )

    __table_args__ = (
        UniqueConstraint("user_id", "custom_id", name="uq_user_custom_registration"),
    )

    def __repr__(self) -> str:
        return f"<CustomRegistration(id={self.id}, user_id={self.user_id}, custom_id={self.custom_id}, status={self.status})>"


class CustomCart(Base, UUIDMixin, TimestampMixin):
    """Custom tournament cart for multiple registrations."""

    __tablename__ = "custom_carts"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="custom_cart",
    )
    items: Mapped[list["CustomCartItem"]] = relationship(
        "CustomCartItem",
        back_populates="cart",
        cascade="all, delete-orphan",
    )

    @property
    def total_items(self) -> int:
        """Get total number of customs in cart."""
        return len(self.items)

    @property
    def total_price(self) -> int:
        """Calculate total entry fees."""
        return sum(item.custom.entry_fee for item in self.items if item.custom.type == CustomType.PAID)

    def __repr__(self) -> str:
        return f"<CustomCart(id={self.id}, user_id={self.user_id}, items={self.total_items})>"


class CustomCartItem(Base, UUIDMixin, TimestampMixin):
    """Individual custom in cart."""

    __tablename__ = "custom_cart_items"

    cart_id: Mapped[str] = mapped_column(
        ForeignKey("custom_carts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    custom_id: Mapped[str] = mapped_column(
        ForeignKey("customs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    cart: Mapped["CustomCart"] = relationship(
        "CustomCart",
        back_populates="items",
    )
    custom: Mapped["Custom"] = relationship(
        "Custom",
        back_populates="cart_items",
    )

    __table_args__ = (
        UniqueConstraint("cart_id", "custom_id", name="uq_cart_custom"),
    )

    def __repr__(self) -> str:
        return f"<CustomCartItem(id={self.id}, cart_id={self.cart_id}, custom_id={self.custom_id})>"