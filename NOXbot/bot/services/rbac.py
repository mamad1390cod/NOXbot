"""RBAC service — roles, permissions, admin accounts and permission checks."""

import json
from datetime import datetime, timezone
from typing import Sequence

from bot.config import get_settings
from bot.models.log import LogAction
from bot.models.rbac import (
    AdminProfile,
    AdminRole,
    AdminStatus,
    ALL_PERMISSIONS,
    Permission,
    RoleSlug,
)
from bot.models.user import User
from bot.services.base import BaseService
from bot.database.uow import UnitOfWork

# Default permission sets per well-known role.
ROLE_DEFAULTS: dict[RoleSlug, list[Permission]] = {
    RoleSlug.OWNER: ALL_PERMISSIONS,
    RoleSlug.SUPER_ADMIN: [
        p for p in ALL_PERMISSIONS if p != Permission.MANAGE_ADMINS
    ],
    RoleSlug.FINANCIAL_MANAGER: [
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_STATISTICS,
        Permission.MANAGE_PAYMENTS,
        Permission.APPROVE_PAYMENTS,
        Permission.REJECT_PAYMENTS,
        Permission.VIEW_FINANCIAL_REPORTS,
        Permission.EXPORT_REPORTS,
        Permission.BACKUP_DATABASE,
        Permission.RESTORE_DATABASE,
    ],
    RoleSlug.SUPPORT_MANAGER: [
        Permission.VIEW_DASHBOARD,
        Permission.MANAGE_TICKETS,
        Permission.SEND_BROADCAST,
    ],
    RoleSlug.TOURNAMENT_MANAGER: [
        Permission.VIEW_DASHBOARD,
        Permission.MANAGE_CUSTOMS,
        Permission.VIEW_STATISTICS,
    ],
    RoleSlug.PRODUCT_MANAGER: [
        Permission.VIEW_DASHBOARD,
        Permission.MANAGE_PRODUCTS,
        Permission.MANAGE_CONFIGS,
        Permission.DELETE_PRODUCTS,
        Permission.VIEW_STATISTICS,
    ],
    RoleSlug.CONTENT_MANAGER: [
        Permission.VIEW_DASHBOARD,
        Permission.MANAGE_CUSTOMS,
        Permission.SEND_BROADCAST,
    ],
    RoleSlug.OPERATOR: [
        Permission.VIEW_DASHBOARD,
        Permission.MANAGE_PAYMENTS,
        Permission.APPROVE_PAYMENTS,
        Permission.REJECT_PAYMENTS,
        Permission.MANAGE_TICKETS,
    ],
    RoleSlug.MODERATOR: [
        Permission.VIEW_DASHBOARD,
        Permission.MANAGE_TICKETS,
        Permission.MANAGE_USERS,
    ],
    RoleSlug.VIEWER: [
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_STATISTICS,
        Permission.EXPORT_REPORTS,
    ],
    RoleSlug.DEVELOPER: [
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_STATISTICS,
        Permission.EXPORT_REPORTS,
        Permission.BACKUP_DATABASE,
        Permission.RESTORE_DATABASE,
        Permission.CHANGE_SETTINGS,
    ],
}

ROLE_NAMES: dict[RoleSlug, str] = {
    RoleSlug.OWNER: "مالک",
    RoleSlug.SUPER_ADMIN: "ادمین ارشد",
    RoleSlug.FINANCIAL_MANAGER: "مدیر مالی",
    RoleSlug.SUPPORT_MANAGER: "مدیر پشتیبانی",
    RoleSlug.TOURNAMENT_MANAGER: "مدیر کاستوم‌ها",
    RoleSlug.PRODUCT_MANAGER: "مدیر محصولات",
    RoleSlug.CONTENT_MANAGER: "مدیر محتوا",
    RoleSlug.OPERATOR: "اپراتور",
    RoleSlug.MODERATOR: "ناظر",
    RoleSlug.VIEWER: "بیننده",
    RoleSlug.DEVELOPER: "توسعه‌دهنده",
}

ROLE_DESCRIPTIONS: dict[RoleSlug, str] = {
    RoleSlug.OWNER: "دسترسی کامل به همه چیز",
    RoleSlug.SUPER_ADMIN: "دسترسی کامل به جز مدیریت ادمین‌ها",
    RoleSlug.FINANCIAL_MANAGER: "مدیریت پرداخت‌ها و گزارش‌های مالی",
    RoleSlug.SUPPORT_MANAGER: "مدیریت تیکت‌ها و ارسال پیام همگانی",
    RoleSlug.TOURNAMENT_MANAGER: "مدیریت کاستوم‌ها",
    RoleSlug.PRODUCT_MANAGER: "مدیریت محصولات و کانفیگ‌ها",
    RoleSlug.CONTENT_MANAGER: "مدیریت کاستوم‌ها و محتوا",
    RoleSlug.OPERATOR: "مدیریت سفارش‌ها و پرداخت‌ها",
    RoleSlug.MODERATOR: "مدیریت تیکت‌ها و کاربران",
    RoleSlug.VIEWER: "فقط مشاهده داشبورد و آمار",
    RoleSlug.DEVELOPER: "دسترسی فنی و پشتیبان‌گیری",
}


class PermissionDenied(Exception):
    """Raised when a user lacks the required permission."""


class RbacService(BaseService):
    """RBAC service — permission resolution and admin account management."""

    def __init__(self, uow: UnitOfWork) -> None:
        super().__init__(uow)
        self._owner_id = get_settings().admin_id

    # --- Permission resolution -------------------------------------------- #
    def is_owner(self, user: User) -> bool:
        return user.telegram_id == self._owner_id

    async def is_admin(self, user: User) -> bool:
        """True if the user is the owner or has an ACTIVE admin profile."""
        if self.is_owner(user):
            return True
        profile = await self.uow.admin_profiles.get_for_telegram_id(user.telegram_id)
        return bool(profile and profile.is_active)

    async def get_profile(self, user: User) -> AdminProfile | None:
        return await self.uow.admin_profiles.get_for_telegram_id(user.telegram_id)

    async def effective_permissions(self, user: User) -> set[Permission]:
        """Return the permission set for a user (owner → all permissions)."""
        if self.is_owner(user):
            return set(ALL_PERMISSIONS)
        profile = await self.uow.admin_profiles.get_for_telegram_id(user.telegram_id)
        if not profile or not profile.is_active:
            return set()
        role = await self.uow.admin_roles.get(profile.role_id) if profile.role_id else None
        if not role:
            return set()
        return role.permission_set()

    async def has_permission(self, user: User, perm: Permission) -> bool:
        return perm in await self.effective_permissions(user)

    async def require_permission(self, user: User, perm: Permission) -> None:
        if not await self.has_permission(user, perm):
            raise PermissionDenied(perm)

    # --- Role management --------------------------------------------------- #
    async def list_roles(self, *, include_system: bool = True) -> Sequence[AdminRole]:
        return await self.uow.admin_roles.list_roles(include_system=include_system)

    async def get_role(self, role_id: str) -> AdminRole | None:
        return await self.uow.admin_roles.get(role_id)

    async def get_role_by_slug(self, slug: RoleSlug | str) -> AdminRole | None:
        s = slug.value if isinstance(slug, RoleSlug) else slug
        return await self.uow.admin_roles.get_by_slug(s)

    async def set_role_permissions(self, role_id: str, permissions: set[Permission]) -> AdminRole | None:
        role = await self.uow.admin_roles.get(role_id)
        if not role:
            return None
        role.permissions = json.dumps(sorted(p.value for p in permissions))
        await self.uow.flush()
        await self.uow.session.refresh(role)
        return role

    async def toggle_role_permission(self, role_id: str, perm: Permission) -> AdminRole | None:
        role = await self.uow.admin_roles.get(role_id)
        if not role:
            return None
        current = role.permission_set()
        if perm in current:
            current.discard(perm)
        else:
            current.add(perm)
        role.permissions = json.dumps(sorted(p.value for p in current))
        await self.uow.flush()
        await self.uow.session.refresh(role)
        return role

    async def seed_roles(self) -> None:
        """Create the built-in roles if they don't exist."""
        order = 0
        for slug in RoleSlug:
            existing = await self.uow.admin_roles.get_by_slug(slug.value)
            if not existing:
                await self.uow.admin_roles.create(
                    name=ROLE_NAMES[slug],
                    slug=slug.value,
                    description=ROLE_DESCRIPTIONS[slug],
                    is_system=True,
                    permissions=json.dumps(sorted(p.value for p in ROLE_DEFAULTS[slug])),
                    sort_order=order,
                )
            order += 1
        await self.uow.flush()

    # --- Admin account management ------------------------------------------ #
    async def list_admins(self, *, offset: int = 0, limit: int = 50) -> Sequence[AdminProfile]:
        return await self.uow.admin_profiles.get_profiles_with_role(
            offset=offset, limit=limit
        )

    async def count_admins(self) -> int:
        return await self.uow.admin_profiles.count_admin_profiles()

    async def create_admin(
        self,
        telegram_id: int,
        role_slug: RoleSlug | str,
        added_by: User,
    ) -> AdminProfile:
        """Create an admin profile for a user. Only MANAGE_ADMINS holders may
        call this (checked by the caller/handler)."""
        user = await self.uow.users.get_by_telegram_id(telegram_id)
        if not user:
            raise ValueError("کاربر یافت نشد")
        if self.is_owner(user):
            raise ValueError("مالک همیشه ادمین است")
        existing = await self.uow.admin_profiles.get_by_user_id(user.id)
        if existing:
            raise ValueError("این کاربر قبلاً ادمین است")

        role = await self.get_role_by_slug(role_slug)
        if not role:
            raise ValueError("نقش نامعتبر است")

        profile = await self.uow.admin_profiles.create(
            user_id=user.id,
            role_id=role.id,
            status=AdminStatus.ACTIVE,
            added_by_id=added_by.id,
            added_at=datetime.now(timezone.utc),
        )
        # Mark the user's role so the general taxonomy is consistent.
        await self.uow.users.update(user.id, role="admin")
        await self.uow.flush()
        return profile

    async def set_admin_role(
        self, user_id: str, role_slug: RoleSlug | str
    ) -> AdminProfile | None:
        role = await self.get_role_by_slug(role_slug)
        if not role:
            return None
        return await self.uow.admin_profiles.set_role(user_id, role.id)

    async def set_admin_status(
        self, user_id: str, status: AdminStatus, reason: str | None = None
    ) -> AdminProfile | None:
        return await self.uow.admin_profiles.set_status(user_id, status, reason)

    async def remove_admin(self, user_id: str) -> bool:
        """Remove an admin profile entirely (does not delete the user)."""
        return await self.uow.admin_profiles.remove(user_id)

    async def touch_login(self, user_id: str) -> None:
        profile = await self.uow.admin_profiles.get_by_user_id(user_id)
        if profile:
            await self.uow.admin_profiles.update(
                profile.id, last_login_at=datetime.now(timezone.utc)
            )

    # --- Logging ----------------------------------------------------------- #
    async def log_admin_action(
        self,
        admin: User,
        action: LogAction,
        target_type: str | None = None,
        target_id: str | None = None,
        description: str | None = None,
        old_data: str | None = None,
        new_data: str | None = None,
        session_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ):
        """Record an admin action with before/after data and session info."""
        return await self.uow.admin_logs.log_action(
            admin_id=admin.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            description=description,
            old_data=old_data,
            new_data=new_data,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
        )