"""RBAC models — roles, permissions, and admin profiles."""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin, UUIDMixin


class Permission(str, enum.Enum):
    """Granular admin permissions."""

    VIEW_DASHBOARD = "view_dashboard"
    VIEW_STATISTICS = "view_statistics"
    MANAGE_USERS = "manage_users"
    MANAGE_PRODUCTS = "manage_products"
    MANAGE_CONFIGS = "manage_configs"
    MANAGE_CUSTOMS = "manage_customs"
    MANAGE_PAYMENTS = "manage_payments"
    APPROVE_PAYMENTS = "approve_payments"
    REJECT_PAYMENTS = "reject_payments"
    MANAGE_TICKETS = "manage_tickets"
    SEND_BROADCAST = "send_broadcast"
    EXPORT_REPORTS = "export_reports"
    BACKUP_DATABASE = "backup_database"
    RESTORE_DATABASE = "restore_database"
    CHANGE_SETTINGS = "change_settings"
    MANAGE_ADMINS = "manage_admins"
    DELETE_PRODUCTS = "delete_products"
    DELETE_ORDERS = "delete_orders"
    DELETE_USERS = "delete_users"
    VIEW_FINANCIAL_REPORTS = "view_financial_reports"

    @property
    def label(self) -> str:
        """Persian label for the permission."""
        return PERMISSION_LABELS[self]


PERMISSION_LABELS: dict[Permission, str] = {
    Permission.VIEW_DASHBOARD: "مشاهده داشبورد",
    Permission.VIEW_STATISTICS: "مشاهده آمار",
    Permission.MANAGE_USERS: "مدیریت کاربران",
    Permission.MANAGE_PRODUCTS: "مدیریت محصولات",
    Permission.MANAGE_CONFIGS: "مدیریت کانفیگ‌ها",
    Permission.MANAGE_CUSTOMS: "مدیریت کاستوم‌ها",
    Permission.MANAGE_PAYMENTS: "مدیریت پرداخت‌ها",
    Permission.APPROVE_PAYMENTS: "تایید پرداخت‌ها",
    Permission.REJECT_PAYMENTS: "رد پرداخت‌ها",
    Permission.MANAGE_TICKETS: "مدیریت تیکت‌ها",
    Permission.SEND_BROADCAST: "ارسال پیام همگانی",
    Permission.EXPORT_REPORTS: "خروجی گرفتن از گزارش‌ها",
    Permission.BACKUP_DATABASE: "پشتیبان‌گیری دیتابیس",
    Permission.RESTORE_DATABASE: "بازیابی دیتابیس",
    Permission.CHANGE_SETTINGS: "تغییر تنظیمات",
    Permission.MANAGE_ADMINS: "مدیریت ادمین‌ها",
    Permission.DELETE_PRODUCTS: "حذف محصولات",
    Permission.DELETE_ORDERS: "حذف سفارشات",
    Permission.DELETE_USERS: "حذف کاربران",
    Permission.VIEW_FINANCIAL_REPORTS: "مشاهده گزارش‌های مالی",
}

ALL_PERMISSIONS: list[Permission] = list(Permission)


class RoleSlug(str, enum.Enum):
    """Well-known role slugs."""

    OWNER = "owner"
    SUPER_ADMIN = "super_admin"
    FINANCIAL_MANAGER = "financial_manager"
    SUPPORT_MANAGER = "support_manager"
    TOURNAMENT_MANAGER = "tournament_manager"
    PRODUCT_MANAGER = "product_manager"
    CONTENT_MANAGER = "content_manager"
    OPERATOR = "operator"
    MODERATOR = "moderator"
    VIEWER = "viewer"
    DEVELOPER = "developer"


class AdminStatus(str, enum.Enum):
    """Admin account lifecycle status."""

    ACTIVE = "active"
    DISABLED = "disabled"
    SUSPENDED = "suspended"


class AdminRole(Base, UUIDMixin, TimestampMixin):
    """A role holding a shared, editable permission set."""

    __tablename__ = "admin_roles"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )  # built-in roles (owner/super_admin) cannot be deleted
    permissions: Mapped[str] = mapped_column(
        Text,
        default="[]",
        nullable=False,
    )  # JSON list of permission slug strings
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Relationships
    profiles: Mapped[list["AdminProfile"]] = relationship(
        "AdminProfile",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    def permission_set(self) -> set[Permission]:
        """Parse the stored permission list into a set."""
        import json
        try:
            slugs = json.loads(self.permissions or "[]")
            return {Permission(s) for s in slugs if s in Permission.__members__.values()}
        except (ValueError, TypeError):
            return set()

    def has(self, perm: Permission) -> bool:
        return perm in self.permission_set()

    def __repr__(self) -> str:
        return f"<AdminRole(slug={self.slug}, permissions={self.permissions})>"


class AdminProfile(Base, UUIDMixin, TimestampMixin):
    """Links a user to an admin role with an account status."""

    __tablename__ = "admin_profiles"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    role_id: Mapped[str | None] = mapped_column(
        ForeignKey("admin_roles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[AdminStatus] = mapped_column(
        Enum(AdminStatus),
        default=AdminStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    suspended_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    added_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="admin_profile",
        foreign_keys=[user_id],
    )
    role: Mapped["AdminRole | None"] = relationship(
        "AdminRole",
        back_populates="profiles",
    )
    added_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[added_by_id],
    )

    @property
    def is_active(self) -> bool:
        return self.status == AdminStatus.ACTIVE

    def __repr__(self) -> str:
        return f"<AdminProfile(user_id={self.user_id}, role={self.role.slug if self.role else None}, status={self.status})>"