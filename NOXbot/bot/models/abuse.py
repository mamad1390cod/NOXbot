"""Anti-abuse models — events, auto-actions, and enforcement state."""

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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin, UUIDMixin


class AbuseType(str, enum.Enum):
    """Categories of detected abuse."""

    SPAM = "spam"
    FLOOD = "flood"
    DUPLICATE_ORDER = "duplicate_order"
    DUPLICATE_PAYMENT = "duplicate_payment"
    FAKE_RECEIPT = "fake_receipt"
    RECEIPT_REUSE = "receipt_reuse"
    MASS_REGISTRATION = "mass_registration"
    CALLBACK_MANIPULATION = "callback_manipulation"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    ADMIN_ABUSE = "admin_abuse"
    BRUTE_FORCE_LOGIN = "brute_force_login"
    MESSAGE_FLOOD = "message_flood"
    BOT_ATTACK = "bot_attack"
    SUSPICIOUS = "suspicious"


class Severity(str, enum.Enum):
    """Severity levels for abuse events."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AutoActionType(str, enum.Enum):
    """Automatic enforcement actions."""

    MUTE = "mute"
    TEMP_BAN = "temp_ban"
    PERM_BAN = "perm_ban"
    RATE_LIMIT = "rate_limit"


class AbuseEvent(Base, UUIDMixin, TimestampMixin):
    """A single detected abuse/violation event."""

    __tablename__ = "abuse_events"

    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    type: Mapped[AbuseType] = mapped_column(
        Enum(AbuseType),
        nullable=False,
        index=True,
    )
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity),
        default=Severity.MEDIUM,
        nullable=False,
    )
    event_data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # JSON
    source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # message / callback / login / payment / order / admin
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    # Relationships
    user: Mapped["User | None"] = relationship(
        "User",
    )

    __table_args__ = (
        Index("ix_abuse_events_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AbuseEvent(user={self.user_id}, type={self.type}, severity={self.severity})>"


class AutoAction(Base, UUIDMixin, TimestampMixin):
    """A recorded automatic (or manual) enforcement action."""

    __tablename__ = "auto_actions"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[AutoActionType] = mapped_column(
        Enum(AutoActionType),
        nullable=False,
        index=True,
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_manual: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    admin_applied_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    lifted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
    )
    admin: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[admin_applied_by],
    )

    @property
    def elapsed_seconds(self) -> int:
        """Seconds since the action was applied (0 if not active)."""
        if not self.duration_seconds:
            return 0
        from datetime import datetime as _dt, timezone as _tz
        now = _dt.now(_tz.utc)
        delta = (now - self.applied_at).total_seconds()
        return max(0, int(self.duration_seconds - delta))

    def __repr__(self) -> str:
        return f"<AutoAction(user={self.user_id}, action={self.action}, active={self.active})>"