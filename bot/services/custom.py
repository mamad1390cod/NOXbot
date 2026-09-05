"""Custom (tournament) service."""

from typing import Sequence

from bot.models.custom import (
    Custom,
    CustomCategory,
    CustomRegistration,
    CustomCart,
    CustomCartItem,
    CustomStatus,
    CustomType,
    WinnerType,
)
from bot.services.base import BaseService
from bot.database.uow import UnitOfWork


class CustomService(BaseService):
    """Custom tournament service."""

    def __init__(self, uow: UnitOfWork) -> None:
        super().__init__(uow)

    # --- Custom Categories ---
    async def get_active_categories(self) -> Sequence[CustomCategory]:
        """Get active custom categories for users."""
        return await self.uow.custom_categories.get_active_categories()

    async def get_category(self, category_id: str) -> CustomCategory | None:
        return await self.uow.custom_categories.get(category_id)

    async def create_category(
        self,
        name: str,
        name_en: str | None = None,
        description: str | None = None,
        sort_order: int = 0,
    ) -> CustomCategory:
        category = await self.uow.custom_categories.create(
            name=name,
            name_en=name_en,
            description=description,
            sort_order=sort_order,
            is_active=True,
        )
        await self.uow.flush()
        return category

    async def update_category(self, category_id: str, **kwargs) -> CustomCategory | None:
        return await self.uow.custom_categories.update(category_id, **kwargs)

    async def delete_category(self, category_id: str) -> bool:
        return await self.uow.custom_categories.delete(category_id)

    async def toggle_category_active(self, category_id: str) -> CustomCategory | None:
        category = await self.uow.custom_categories.get(category_id)
        if category:
            return await self.uow.custom_categories.update(category_id, is_active=not category.is_active)
        return None

    async def get_all_categories_for_admin(self, offset: int = 0, limit: int = 50) -> Sequence[CustomCategory]:
        return await self.uow.custom_categories.get_all_for_admin(offset=offset, limit=limit)

    # --- Customs ---
    async def get_custom(self, custom_id: str) -> Custom | None:
        return await self.uow.customs.get_custom_with_details(custom_id)

    async def get_open_registrations(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        category_id: str | None = None,
    ) -> Sequence[Custom]:
        return await self.uow.customs.get_open_registrations(
            offset=offset, limit=limit, category_id=category_id
        )

    async def get_by_category(
        self,
        category_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[Custom]:
        return await self.uow.customs.get_by_category(
            category_id, offset=offset, limit=limit
        )

    async def create_custom(
        self,
        title: str,
        custom_category_id: str | None,
        custom_type: CustomType = CustomType.FREE,
        description: str | None = None,
        rules: str | None = None,
        entry_fee: int = 0,
        prize: str | None = None,
        banner_url: str | None = None,
        event_date=None,
        event_time: str | None = None,
        max_capacity: int | None = None,
        is_visible: bool = True,
        sort_order: int = 0,
    ) -> Custom:
        custom = await self.uow.customs.create(
            title=title,
            title_en=None,
            description=description,
            rules=rules,
            type=custom_type,
            entry_fee=entry_fee,
            prize=prize,
            banner_url=banner_url,
            gallery=None,
            event_date=event_date,
            event_time=event_time,
            max_capacity=max_capacity,
            current_players=0,
            is_visible=is_visible,
            registration_open=False,
            status=CustomStatus.DRAFT,
            sort_order=sort_order,
            custom_category_id=custom_category_id,
        )
        await self.uow.flush()
        return custom

    async def update_custom(self, custom_id: str, **kwargs) -> Custom | None:
        return await self.uow.customs.update(custom_id, **kwargs)

    async def delete_custom(self, custom_id: str) -> bool:
        return await self.uow.customs.delete(custom_id)

    async def toggle_visibility(self, custom_id: str) -> Custom | None:
        custom = await self.uow.customs.get(custom_id)
        if custom:
            return await self.uow.customs.update(custom_id, is_visible=not custom.is_visible)
        return None

    async def set_registration_status(self, custom_id: str, open: bool) -> Custom | None:
        """Open or close registration for a custom."""
        custom = await self.uow.customs.get(custom_id)
        if not custom:
            return None
        status = CustomStatus.REGISTRATION_OPEN if open else CustomStatus.REGISTRATION_CLOSED
        return await self.uow.customs.update(
            custom_id, registration_open=open, status=status
        )

    async def start_custom(self, custom_id: str) -> Custom | None:
        return await self.uow.customs.update(
            custom_id,
            status=CustomStatus.IN_PROGRESS,
            registration_open=False,
        )

    async def cancel_custom(self, custom_id: str, reason: str) -> Custom | None:
        return await self.uow.customs.cancel_custom(custom_id, reason)

    async def set_winner(
        self,
        custom_id: str,
        winner_type: WinnerType,
        winner_user_id: str | None = None,
        winner_team_name: str | None = None,
    ) -> Custom | None:
        # Set winner_type first
        await self.uow.customs.update(custom_id, winner_type=winner_type)
        return await self.uow.customs.set_winner(
            custom_id,
            winner_id=winner_user_id,
            winner_team_name=winner_team_name,
        )

    async def broadcast_to_participants(self, custom_id: str, message: str) -> list:
        """Get confirmed participants for broadcasting."""
        registrations = await self.uow.custom_registrations.get_confirmed_registrations(custom_id)
        return registrations

    async def is_user_registered(self, user_id: str, custom_id: str) -> bool:
        """Check if user is already registered (prevent duplicates)."""
        registration = await self.uow.customs.get_user_registration(user_id, custom_id)
        return registration is not None

    async def register_user(
        self,
        user_id: str,
        custom_id: str,
        codm_username: str,
        team_name: str | None = None,
        status: str = "confirmed",
    ) -> CustomRegistration:
        """Register user for a custom."""
        custom = await self.uow.customs.get(custom_id)
        if not custom:
            raise ValueError("کاستوم یافت نشد")

        # Double-check capacity
        if custom.is_full:
            raise ValueError("ظرفیت کاستوم پر شده است")

        # Double-check duplicates
        if await self.is_user_registered(user_id, custom_id):
            raise ValueError("شما قبلاً در این کاستوم ثبت نام کرده‌اید")

        registration = await self.uow.customs.register_user(
            user_id=user_id,
            custom_id=custom_id,
            codm_username=codm_username,
            team_name=team_name,
            status=status,
        )

        await self.validate_registration_count(custom_id)
        await self.uow.flush()
        return registration

    async def validate_registration_count(self, custom_id: str) -> None:
        """Keep current_players consistent with confirmed registrations."""
        custom = await self.uow.customs.get(custom_id)
        count = await self.uow.customs.count_registrations(custom_id)
        if custom:
            custom.current_players = count


    async def approve_registration(
        self, registration_id: str, admin_id: str
    ) -> CustomRegistration | None:
        reg = await self.uow.custom_registrations.update_registration_status(
            registration_id,
            "confirmed",
            admin_id=admin_id,
        )
        # Re-sync current players
        if reg:
            await self.validate_registration_count(reg.custom_id)
            await self.uow.flush()
        return reg

    async def reject_registration(
        self, registration_id: str, admin_id: str
    ) -> CustomRegistration | None:
        return await self.uow.custom_registrations.update_registration_status(
            registration_id, "rejected", admin_id=admin_id
        )

    async def get_all_for_admin(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: CustomStatus | None = None,
        category_id: str | None = None,
    ) -> Sequence[Custom]:
        return await self.uow.customs.get_all_for_admin(
            offset=offset, limit=limit, status=status, category_id=category_id
        )

    async def count_for_admin(
        self,
        status: CustomStatus | None = None,
        category_id: str | None = None,
    ) -> int:
        return await self.uow.customs.count_for_admin(status=status, category_id=category_id)

    async def get_registrations(self, custom_id: str) -> Sequence[CustomRegistration]:
        return await self.uow.customs.get_registrations(custom_id, limit=100)

    async def get_registration(self, registration_id: str) -> CustomRegistration | None:
        return await self.uow.custom_registrations.get(registration_id)

    async def get_user_registrations(self, user_id: str) -> Sequence[CustomRegistration]:
        return await self.uow.custom_registrations.get_by_user(user_id)