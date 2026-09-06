"""User repository."""

from typing import Sequence

from sqlalchemy import BigInteger, Select, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.user import User, UserRole
from bot.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """User repository with specialized queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Get user by Telegram ID."""
        return await self.get_by(telegram_id=telegram_id)

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username (without @)."""
        username = username.lstrip("@")
        return await self.get_by(username=username)

    async def get_by_referral_code(self, code: str) -> User | None:
        """Get user by referral code."""
        return await self.get_by(referral_code=code)

    async def get_admins(self) -> Sequence[User]:
        """Get all admin users."""
        stmt = select(User).where(User.role == UserRole.ADMIN)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_banned_users(self) -> Sequence[User]:
        """Get all banned users."""
        stmt = select(User).where(User.is_banned == True)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def search_users(
        self,
        query: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[User]:
        """Search users by username, first_name, last_name, or telegram_id."""
        stmt = select(User).where(
            or_(
                User.username.ilike(f"%{query}%"),
                User.first_name.ilike(f"%{query}%"),
                User.last_name.ilike(f"%{query}%"),
                User.telegram_id == query if query.isdigit() else False,
            )
        ).order_by(desc(User.created_at)).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_search(self, query: str) -> int:
        """Count users matching search query."""
        stmt = select(func.count()).select_from(User).where(
            or_(
                User.username.ilike(f"%{query}%"),
                User.first_name.ilike(f"%{query}%"),
                User.last_name.ilike(f"%{query}%"),
                User.telegram_id == query if query.isdigit() else False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_new_users_today(self) -> int:
        """Get count of new users today."""
        from datetime import datetime, timedelta, timezone
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(func.count()).select_from(User).where(User.created_at >= today)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_active_users_count(self, days: int = 7) -> int:
        """Get count of active users in last N days."""
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = select(func.count()).select_from(User).where(User.last_activity >= cutoff)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_total_users(self) -> int:
        """Get total user count."""
        return await self.count()

    async def get_users_with_pagination(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        role: UserRole | None = None,
        is_banned: bool | None = None,
    ) -> Sequence[User]:
        """Get users with pagination and filters."""
        stmt = select(User).order_by(desc(User.created_at))
        if role:
            stmt = stmt.where(User.role == role)
        if is_banned is not None:
            stmt = stmt.where(User.is_banned == is_banned)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_last_activity(self, user_id: str) -> None:
        """Update user's last activity timestamp."""
        from datetime import datetime, timezone
        await self.update(user_id, last_activity=datetime.now(timezone.utc))

    async def increment_spent(self, user_id: str, amount: int) -> None:
        """Increment user's total spent."""
        user = await self.get(user_id)
        if user:
            user.total_spent += amount
            await self.session.flush()