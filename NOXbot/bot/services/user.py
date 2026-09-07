"""User service."""

import secrets
from typing import Sequence

from bot.models.user import User, UserRole
from bot.services.base import BaseService
from bot.database.uow import UnitOfWork


class UserService(BaseService):
    """User service for user management."""

    def __init__(self, uow: UnitOfWork) -> None:
        super().__init__(uow)

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str = "fa",
        referred_by: str | None = None,
    ) -> User:
        """Get existing user or create new one."""
        user = await self.uow.users.get_by_telegram_id(telegram_id)
        if user:
            # Update info if changed
            updates = {}
            if username is not None and user.username != username:
                updates["username"] = username
            if first_name is not None and user.first_name != first_name:
                updates["first_name"] = first_name
            if last_name is not None and user.last_name != last_name:
                updates["last_name"] = last_name
            if updates:
                await self.uow.users.update(user.id, **updates)
                await self.uow.flush()
                user = await self.uow.users.get(user.id)
            return user

        # Generate unique referral code
        referral_code = await self._generate_referral_code()

        user = await self.uow.users.create(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
            referred_by=referred_by,
            referral_code=referral_code,
        )
        await self.uow.flush()
        return user

    async def _generate_referral_code(self) -> str:
        """Generate unique referral code."""
        while True:
            code = secrets.token_urlsafe(8)[:10].upper()
            existing = await self.uow.users.get_by_referral_code(code)
            if not existing:
                return code

    async def get_user(self, user_id: str) -> User | None:
        """Get user by ID."""
        return await self.uow.users.get(user_id)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Get user by Telegram ID."""
        return await self.uow.users.get_by_telegram_id(telegram_id)

    async def update_user(self, user_id: str, **kwargs) -> User | None:
        """Update user."""
        return await self.uow.users.update(user_id, **kwargs)

    async def ban_user(self, user_id: str, reason: str | None = None) -> User | None:
        """Ban user."""
        return await self.uow.users.update(user_id, is_banned=True, ban_reason=reason, role=UserRole.BANNED)

    async def unban_user(self, user_id: str) -> User | None:
        """Unban user."""
        return await self.uow.users.update(user_id, is_banned=False, ban_reason=None, role=UserRole.USER)

    async def make_admin(self, user_id: str) -> User | None:
        """Make user admin."""
        return await self.uow.users.update(user_id, role=UserRole.ADMIN)

    async def remove_admin(self, user_id: str) -> User | None:
        """Remove admin role."""
        return await self.uow.users.update(user_id, role=UserRole.USER)

    async def search_users(self, query: str, offset: int = 0, limit: int = 20) -> Sequence[User]:
        """Search users."""
        return await self.uow.users.search_users(query, offset=offset, limit=limit)

    async def count_search(self, query: str) -> int:
        """Count search results."""
        return await self.uow.users.count_search(query)

    async def get_stats(self) -> dict:
        """Get user statistics."""
        total = await self.uow.users.get_total_users()
        new_today = await self.uow.users.get_new_users_today()
        active = await self.uow.users.get_active_users_count(7)
        banned = await self.uow.users.count(is_banned=True)
        admins = await self.uow.users.count(role=UserRole.ADMIN)
        return {
            "total": total,
            "new_today": new_today,
            "active_week": active,
            "banned": banned,
            "admins": admins,
        }

    async def update_activity(self, user_id: str) -> None:
        """Update user last activity."""
        await self.uow.users.update_last_activity(user_id)

    async def add_spent(self, user_id: str, amount: int) -> None:
        """Add to user's total spent."""
        await self.uow.users.increment_spent(user_id, amount)

    async def get_all_for_admin(
        self,
        offset: int = 0,
        limit: int = 20,
        role: UserRole | None = None,
        is_banned: bool | None = None,
    ) -> Sequence[User]:
        """Get all users for admin panel."""
        return await self.uow.users.get_users_with_pagination(
            offset=offset,
            limit=limit,
            role=role,
            is_banned=is_banned,
        )

    async def get_user_details(self, user_id: str) -> dict | None:
        """Get detailed user info for admin."""
        user = await self.uow.users.get(user_id)
        if not user:
            return None

        orders = await self.uow.orders.get_by_user(user_id, limit=10)
        payments = await self.uow.payments.get_by_user(user_id, limit=10)
        tickets = await self.uow.tickets.get_by_user(user_id, limit=10)
        registrations = await self.uow.custom_registrations.get_by_user(user_id)

        return {
            "user": user,
            "recent_orders": orders,
            "recent_payments": payments,
            "recent_tickets": tickets,
            "custom_registrations": registrations,
            "stats": {
                "total_orders": len(orders),
                "total_payments": len(payments),
                "total_tickets": len(tickets),
                "total_registrations": len(registrations),
            },
        }