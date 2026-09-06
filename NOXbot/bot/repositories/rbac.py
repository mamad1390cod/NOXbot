"""RBAC repository — roles and admin profiles."""

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models.rbac import AdminProfile, AdminRole, AdminStatus, RoleSlug
from bot.models.user import User
from bot.repositories.base import BaseRepository


class AdminRoleRepository(BaseRepository[AdminRole]):
    """Repository for admin roles."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AdminRole)

    async def get_by_slug(self, slug: str) -> AdminRole | None:
        return await self.get_by(slug=slug)

    async def get_by_slug_enum(self, slug: RoleSlug) -> AdminRole | None:
        return await self.get_by(slug=slug.value)

    async def list_roles(self, *, include_system: bool = True) -> Sequence[AdminRole]:
        stmt = select(AdminRole)
        if not include_system:
            stmt = stmt.where(AdminRole.is_system == False)
        stmt = stmt.order_by(AdminRole.sort_order, AdminRole.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def role_exists(self, role_id: str) -> bool:
        return await self.exists(id=role_id)


class AdminProfileRepository(BaseRepository[AdminProfile]):
    """Repository for admin profiles."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AdminProfile)

    async def get_by_user_id(self, user_id: str) -> AdminProfile | None:
        """Get an admin profile by user id, eager-loading its relations so that
        reading ``profile.role`` / ``profile.user`` never triggers a lazy-load
        in a synchronous keyboard-building context (MissingGreenlet)."""
        stmt = (
            select(AdminProfile)
            .where(AdminProfile.user_id == user_id)
            .options(
                selectinload(AdminProfile.role),
                selectinload(AdminProfile.user),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_telegram_id(self, telegram_id: int) -> AdminProfile | None:
        stmt = (
            select(AdminProfile)
            .join(AdminProfile.user)
            .where(User.telegram_id == telegram_id)
            .options(selectinload(AdminProfile.role))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_profiles_with_role(
        self, *, offset: int = 0, limit: int = 50
    ) -> Sequence[AdminProfile]:
        stmt = (
            select(AdminProfile)
            .options(
                selectinload(AdminProfile.user),
                selectinload(AdminProfile.role),
                selectinload(AdminProfile.added_by),
            )
            .order_by(AdminProfile.added_at)
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_admin_profiles(self) -> int:
        return await self.count()

    async def set_role(self, user_id: str, role_id: str) -> AdminProfile | None:
        """Update the role of the profile owned by ``user_id`` (not profile PK)."""
        profile = await self.get_by_user_id(user_id)
        if not profile:
            return None
        return await self.update(profile.id, role_id=role_id)

    async def set_status(
        self, user_id: str, status, reason: str | None = None
    ) -> AdminProfile | None:
        """Update the status of the profile owned by ``user_id``."""
        profile = await self.get_by_user_id(user_id)
        if not profile:
            return None
        updates = {"status": status}
        if reason:
            updates["suspended_reason"] = reason
        return await self.update(profile.id, **updates)

    async def remove(self, user_id: str) -> bool:
        profile = await self.get_by_user_id(user_id)
        if profile:
            await self.session.delete(profile)
            await self.session.flush()
            return True
        return False