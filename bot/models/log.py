"""Admin log model."""

import enum
from sqlalchemy import (
    BigInteger,
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


class LogAction(str, enum.Enum):
    """Log action types."""

    # User actions
    USER_REGISTER = "user_register"
    USER_BAN = "user_ban"
    USER_UNBAN = "user_unban"
    USER_DELETE = "user_delete"
    USER_EDIT = "user_edit"

    # Product actions
    PRODUCT_CREATE = "product_create"
    PRODUCT_EDIT = "product_edit"
    PRODUCT_DELETE = "product_delete"
    PRODUCT_TOGGLE = "product_toggle"

    # Category actions
    CATEGORY_CREATE = "category_create"
    CATEGORY_EDIT = "category_edit"
    CATEGORY_DELETE = "category_delete"

    # Order actions
    ORDER_CREATE = "order_create"
    ORDER_EDIT = "order_edit"
    ORDER_CANCEL = "order_cancel"
    ORDER_COMPLETE = "order_complete"

    # Payment actions
    PAYMENT_CREATE = "payment_create"
    PAYMENT_APPROVE = "payment_approve"
    PAYMENT_REJECT = "payment_reject"

    # Custom actions
    CUSTOM_CREATE = "custom_create"
    CUSTOM_EDIT = "custom_edit"
    CUSTOM_DELETE = "custom_delete"
    CUSTOM_REGISTER = "custom_register"
    CUSTOM_APPROVE = "custom_approve"
    CUSTOM_REJECT = "custom_reject"
    CUSTOM_WINNER = "custom_winner"
    CUSTOM_CANCEL = "custom_cancel"

    # Config actions
    CONFIG_CREATE = "config_create"
    CONFIG_EDIT = "config_edit"
    CONFIG_DELETE = "config_delete"

    # Ticket actions
    TICKET_CREATE = "ticket_create"
    TICKET_REPLY = "ticket_reply"
    TICKET_CLOSE = "ticket_close"
    TICKET_ASSIGN = "ticket_assign"

    # Settings actions
    SETTINGS_CHANGE = "settings_change"

    # Broadcast actions
    BROADCAST_SEND = "broadcast_send"

    # Backup actions
    BACKUP_CREATE = "backup_create"
    BACKUP_RESTORE = "backup_restore"

    # Report / export actions
    EXPORT_REPORTS = "export_reports"
    VIEW_FINANCIALS = "view_financials"


class AdminLog(Base, UUIDMixin, TimestampMixin):
    """Admin action log model."""

    __tablename__ = "admin_logs"

    admin_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[LogAction] = mapped_column(
        Enum(LogAction),
        nullable=False,
        index=True,
    )
    target_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # user, product, order, etc.
    target_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    old_data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # JSON
    new_data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # JSON
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    session_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    # Relationships
    admin: Mapped["User | None"] = relationship(
        "User",
    )

    def __repr__(self) -> str:
        return f"<AdminLog(id={self.id}, admin_id={self.admin_id}, action={self.action}, target={self.target_type}:{self.target_id})>"