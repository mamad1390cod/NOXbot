"""Admin and RBAC filters."""

import logging
from typing import Any

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.config import get_settings
from bot.models.rbac import Permission
from bot.services.rbac import RbacService

logger = logging.getLogger(__name__)


class IsAdmin(BaseFilter):
    """Filter that allows the owner OR any user with an ACTIVE admin profile.

    This fixes the previous owner-only gating: DB-promoted admins (via an
    AdminProfile) can now access the admin panel. The owner always passes.
    """

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = getattr(event.from_user, "id", None)
        if user_id == get_settings().admin_id:
            return True
        # Middleware injects the ORM user; fall back to a DB check otherwise.
        # Note: the UserContextMiddleware runs first and injects data["user"],
        # but filters are evaluated before handlers, so we check by telegram_id.
        from bot.database.uow import UnitOfWork
        try:
            uow = UnitOfWork()
            async with uow:
                rbac = RbacService(uow)
                user = await rbac.uow.users.get_by_telegram_id(user_id)
                if not user:
                    return False
                return await rbac.is_admin(user)
        except Exception as e:
            logger.exception("IsAdmin check failed: %s", e)
            return False


class HasPermission(BaseFilter):
    """Filter that requires the user to hold a given permission.

    The owner always passes (owner = full access).
    """

    def __init__(self, permission: Permission | list[Permission]) -> None:
        self.permissions = (
            permission if isinstance(permission, list) else [permission]
        )

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = getattr(event.from_user, "id", None)
        if user_id == get_settings().admin_id:
            return True
        from bot.database.uow import UnitOfWork
        try:
            uow = UnitOfWork()
            async with uow:
                rbac = RbacService(uow)
                user = await rbac.uow.users.get_by_telegram_id(user_id)
                if not user:
                    return False
                perms = await rbac.effective_permissions(user)
                return any(p in perms for p in self.permissions)
        except Exception as e:
            logger.exception("HasPermission check failed: %s", e)
            return False


class HasPasswordAccess(BaseFilter):
    """Filter that passes only when the user has admin password access.

    In this version the admin login is password-based and temporary.
    The owner always has access.
    """

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = getattr(event.from_user, "id", None)
        if user_id == get_settings().admin_id:
            return True
        return False