"""Broadcast system models."""

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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin, UUIDMixin


class BroadcastStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"      # scheduled, awaiting due time or ready to send
    PAUSED = "paused"
    SENDING = "sending"
    SENT = "sent"
    CANCELLED = "cancelled"


class MediaType(str, enum.Enum):
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    ANIMATION = "animation"
    VOICE = "voice"
    POLL = "poll"


class Broadcast(Base, UUIDMixin, TimestampMixin):
    """A persisted broadcast job with audience + content + delivery stats."""

    __tablename__ = "broadcasts"

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    status: Mapped[BroadcastStatus] = mapped_column(
        String(30),
        default=BroadcastStatus.DRAFT,
        nullable=False,
        index=True,
    )
    # Audience: JSON config, e.g. {"groups": ["all"], "roles": [...], "category_id": ...}
    audience: Mapped[str] = mapped_column(
        Text,
        default="{}",
        nullable=False,
    )
    media_type: Mapped[MediaType] = mapped_column(
        Enum(MediaType),
        default=MediaType.TEXT,
        nullable=False,
    )
    media_file_id: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    caption: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    # Inline keyboard as a JSON list of [[{text,url/callback}],...]
    buttons: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    poll: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # JSON: {"question": "...", "options": [...], "is_anonymous": bool}
    notification_category: Mapped[str] = mapped_column(
        String(30),
        default="promos",
        nullable=False,
    )

    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Scheduling / recurring
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    interval_seconds: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )  # None → one-shot; set → recurring

    # Delivery stats
    total_target: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    sent_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    failed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    blocked_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    opted_out_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    # JSON list of telegram IDs that failed / blocked (for the failure report).
    failed_ids: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    blocked_ids: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by: Mapped["User | None"] = relationship("User")

    __table_args__ = (
        Index("ix_broadcasts_scheduled_status", "scheduled_at", "status"),
    )

    def __repr__(self) -> str:
        return f"<Broadcast(title={self.title}, status={self.status}, media={self.media_type})>"


class BroadcastTemplate(Base, UUIDMixin, TimestampMixin):
    """A reusable saved message/template."""

    __tablename__ = "broadcast_templates"

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    media_type: Mapped[MediaType] = mapped_column(
        Enum(MediaType),
        default=MediaType.TEXT,
        nullable=False,
    )
    media_file_id: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    caption: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    buttons: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return f"<BroadcastTemplate(name={self.name}, media={self.media_type})>"