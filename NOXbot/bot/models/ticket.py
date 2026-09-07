"""Ticket models."""

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


class TicketStatus(str, enum.Enum):
    """Ticket status."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_USER = "waiting_user"
    CLOSED = "closed"


class TicketPriority(str, enum.Enum):
    """Ticket priority."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TicketCategory(Base, UUIDMixin, TimestampMixin):
    """Ticket category model."""

    __tablename__ = "ticket_categories"

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
    color: Mapped[str | None] = mapped_column(
        String(7),
        nullable=True,
    )  # Hex color
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
    category: Mapped["Category | None"] = relationship(
        "Category",
        back_populates="ticket_categories",
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket",
        back_populates="ticket_category",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<TicketCategory(id={self.id}, name={self.name})>"


class Ticket(Base, UUIDMixin, TimestampMixin):
    """Support ticket model."""

    __tablename__ = "tickets"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_category_id: Mapped[str] = mapped_column(
        ForeignKey("ticket_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus),
        default=TicketStatus.OPEN,
        nullable=False,
        index=True,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority),
        default=TicketPriority.NORMAL,
        nullable=False,
    )
    assigned_admin_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    closed_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    close_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="tickets",
        foreign_keys=[user_id],
    )
    ticket_category: Mapped["TicketCategory"] = relationship(
        "TicketCategory",
        back_populates="tickets",
    )
    assigned_admin: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[assigned_admin_id],
    )
    closed_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[closed_by],
    )
    messages: Mapped[list["TicketMessage"]] = relationship(
        "TicketMessage",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Ticket(id={self.id}, user_id={self.user_id}, subject={self.subject}, status={self.status})>"


class TicketMessage(Base, UUIDMixin, TimestampMixin):
    """Ticket message/reply model."""

    __tablename__ = "ticket_messages"

    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    attachment_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Relationships
    ticket: Mapped["Ticket"] = relationship(
        "Ticket",
        back_populates="messages",
    )
    user: Mapped["User"] = relationship(
        "User",
    )

    def __repr__(self) -> str:
        return f"<TicketMessage(id={self.id}, ticket_id={self.ticket_id}, is_admin={self.is_admin})>"