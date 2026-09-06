"""Custom tournament repository."""

from typing import Sequence

from sqlalchemy import Select, desc, func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models.custom import (
    Custom,
    CustomCategory,
    CustomRegistration,
    CustomCart,
    CustomCartItem,
    CustomStatus,
    CustomType,
)
from bot.repositories.base import BaseRepository


class CustomCategoryRepository(BaseRepository[CustomCategory]):
    """Custom category repository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CustomCategory)

    async def get_active_categories(self) -> Sequence[CustomCategory]:
        """Get all active custom categories."""
        stmt = select(CustomCategory).where(
            CustomCategory.is_active == True
        ).order_by(CustomCategory.sort_order, CustomCategory.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_for_admin(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[CustomCategory]:
        """Get all custom categories for admin."""
        stmt = select(CustomCategory).order_by(
            CustomCategory.sort_order, CustomCategory.name
        ).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class CustomRepository(BaseRepository[Custom]):
    """Custom tournament repository with specialized queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Custom)

    async def get_by_category(
        self,
        category_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        visible_only: bool = True,
        status: CustomStatus | None = None,
    ) -> Sequence[Custom]:
        """Get customs by category with pagination."""
        stmt = select(Custom).where(Custom.custom_category_id == category_id)
        if visible_only:
            stmt = stmt.where(Custom.is_visible == True)
        if status:
            stmt = stmt.where(Custom.status == status)
        stmt = stmt.order_by(Custom.sort_order, desc(Custom.created_at))
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_category(self, category_id: str, visible_only: bool = True) -> int:
        """Count customs in category."""
        stmt = select(func.count()).select_from(Custom).where(Custom.custom_category_id == category_id)
        if visible_only:
            stmt = stmt.where(Custom.is_visible == True)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_open_registrations(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        category_id: str | None = None,
    ) -> Sequence[Custom]:
        """Get customs with open registration."""
        stmt = select(Custom).where(
            Custom.status == CustomStatus.REGISTRATION_OPEN,
            Custom.registration_open == True,
            Custom.is_visible == True,
        )
        if category_id:
            stmt = stmt.where(Custom.custom_category_id == category_id)
        stmt = stmt.order_by(Custom.event_date, Custom.sort_order).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_custom_with_details(self, custom_id: str) -> Custom | None:
        """Get custom with all relations loaded."""
        stmt = select(Custom).where(Custom.id == custom_id).options(
            selectinload(Custom.custom_category),
            selectinload(Custom.registrations).selectinload(CustomRegistration.user),
            selectinload(Custom.winner),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_registration(self, user_id: str, custom_id: str) -> CustomRegistration | None:
        """Get user's registration for a custom."""
        stmt = select(CustomRegistration).where(
            CustomRegistration.user_id == user_id,
            CustomRegistration.custom_id == custom_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_registrations(
        self,
        custom_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
    ) -> Sequence[CustomRegistration]:
        """Get registrations for a custom."""
        stmt = select(CustomRegistration).where(CustomRegistration.custom_id == custom_id).options(
            selectinload(CustomRegistration.user),
        )
        if status:
            stmt = stmt.where(CustomRegistration.status == status)
        stmt = stmt.order_by(CustomRegistration.created_at).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_registrations(self, custom_id: str, status: str | None = None) -> int:
        """Count registrations for a custom."""
        stmt = select(func.count()).select_from(CustomRegistration).where(
            CustomRegistration.custom_id == custom_id
        )
        if status:
            stmt = stmt.where(CustomRegistration.status == status)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def register_user(
        self,
        user_id: str,
        custom_id: str,
        codm_username: str,
        team_name: str | None = None,
        status: str = "pending",
    ) -> CustomRegistration:
        """Register user for custom with proper locking to prevent race conditions."""
        from sqlalchemy import select as sa_select
        
        # Lock custom row for atomic update
        stmt = (
            sa_select(Custom)
            .where(Custom.id == custom_id)
            .with_for_update(skip_locked=False)
        )
        result = await self.session.execute(stmt)
        custom = result.scalar_one_or_none()
        
        if not custom:
            raise ValueError("کاستوم یافت نشد")
        
        # Check capacity under lock (only for confirmed registrations)
        if status == "confirmed" and custom.is_full:
            raise ValueError("ظرفیت کاستوم پر شده است")
        
        registration = CustomRegistration(
            user_id=user_id,
            custom_id=custom_id,
            codm_username=codm_username,
            team_name=team_name,
            status=status,
        )
        self.session.add(registration)

        # Only increment current_players for confirmed registrations
        if status == "confirmed":
            custom.current_players += 1

        await self.session.flush()
        await self.session.refresh(registration)
        return registration

    async def update_registration_status(
        self,
        registration_id: str,
        status: str,
        admin_id: str | None = None,
    ) -> CustomRegistration | None:
        """Update registration status and adjust current_players."""
        from datetime import datetime, timezone
        
        # Get current registration to check status change
        reg = await self.get(registration_id)
        if not reg:
            return None
        
        old_status = reg.status
        updates = {"status": status}
        if status == "confirmed":
            updates["confirmed_at"] = datetime.now(timezone.utc)
            updates["confirmed_by"] = admin_id
        
        updated_reg = await self.update(registration_id, **updates)
        
        # Adjust current_players when status changes
        if old_status != status:
            custom = await self.get(reg.custom_id)
            if custom:
                if status == "confirmed" and old_status != "confirmed":
                    custom.current_players += 1
                elif old_status == "confirmed" and status != "confirmed":
                    custom.current_players = max(0, custom.current_players - 1)
                await self.session.flush()
        
        return updated_reg

    async def increment_view_count(self, custom_id: str) -> None:
        """Increment custom view count."""
        custom = await self.get(custom_id)
        if custom:
            custom.view_count += 1
            await self.session.flush()

    async def get_all_for_admin(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: CustomStatus | None = None,
        category_id: str | None = None,
        type: CustomType | None = None,
    ) -> Sequence[Custom]:
        """Get all customs for admin with filters."""
        stmt = select(Custom).options(
            selectinload(Custom.custom_category),
        ).order_by(desc(Custom.created_at))
        if status:
            stmt = stmt.where(Custom.status == status)
        if category_id:
            stmt = stmt.where(Custom.custom_category_id == category_id)
        if type:
            stmt = stmt.where(Custom.type == type)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_for_admin(
        self,
        status: CustomStatus | None = None,
        category_id: str | None = None,
        type: CustomType | None = None,
    ) -> int:
        """Count customs for admin with filters."""
        stmt = select(func.count()).select_from(Custom)
        if status:
            stmt = stmt.where(Custom.status == status)
        if category_id:
            stmt = stmt.where(Custom.custom_category_id == category_id)
        if type:
            stmt = stmt.where(Custom.type == type)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def set_winner(
        self,
        custom_id: str,
        winner_id: str | None = None,
        winner_team_name: str | None = None,
    ) -> Custom | None:
        """Set custom winner."""
        from datetime import datetime, timezone
        return await self.update(
            custom_id,
            status=CustomStatus.COMPLETED,
            winner_id=winner_id,
            winner_team_name=winner_team_name,
            completed_at=datetime.now(timezone.utc),
        )

    async def cancel_custom(self, custom_id: str, reason: str) -> Custom | None:
        """Cancel custom tournament."""
        from datetime import datetime, timezone
        return await self.update(
            custom_id,
            status=CustomStatus.CANCELLED,
            cancelled_at=datetime.now(timezone.utc),
            cancel_reason=reason,
        )


class CustomRegistrationRepository(BaseRepository[CustomRegistration]):
    """Custom registration repository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CustomRegistration)

    async def get_by_user(self, user_id: str) -> Sequence[CustomRegistration]:
        """Get all registrations by user."""
        stmt = select(CustomRegistration).where(CustomRegistration.user_id == user_id).options(
            selectinload(CustomRegistration.custom),
        ).order_by(desc(CustomRegistration.created_at))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_confirmed_registrations(self, custom_id: str) -> Sequence[CustomRegistration]:
        """Get confirmed registrations for a custom."""
        stmt = select(CustomRegistration).where(
            CustomRegistration.custom_id == custom_id,
            CustomRegistration.status == "confirmed",
        ).options(
            selectinload(CustomRegistration.user),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class CustomCartRepository(BaseRepository[CustomCart]):
    """Custom cart repository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CustomCart)

    async def get_by_user_id(self, user_id: str) -> CustomCart | None:
        """Get custom cart by user ID with items loaded."""
        stmt = select(CustomCart).where(CustomCart.user_id == user_id).options(
            selectinload(CustomCart.items).selectinload(CustomCartItem.custom),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: str) -> CustomCart:
        """Get existing cart or create new one."""
        cart = await self.get_by_user_id(user_id)
        if cart is None:
            cart = await self.create(user_id=user_id)
        return cart

    async def add_item(self, cart_id: str, custom_id: str, team_name: str | None = None) -> CustomCartItem:
        """Add custom to cart."""
        item = CustomCartItem(
            cart_id=cart_id,
            custom_id=custom_id,
            team_name=team_name,
        )
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def remove_item(self, item_id: str) -> bool:
        """Remove item from cart."""
        item = await self.session.get(CustomCartItem, item_id)
        if item:
            await self.session.delete(item)
            await self.session.flush()
            return True
        return False

    async def clear_cart(self, cart_id: str) -> int:
        """Clear all items from cart."""
        stmt = select(CustomCartItem).where(CustomCartItem.cart_id == cart_id)
        result = await self.session.execute(stmt)
        items = result.scalars().all()
        count = len(items)
        for item in items:
            await self.session.delete(item)
        await self.session.flush()
        return count

    async def get_items(self, cart_id: str) -> Sequence[CustomCartItem]:
        """Get cart items with customs loaded."""
        stmt = select(CustomCartItem).where(CustomCartItem.cart_id == cart_id).options(
            selectinload(CustomCartItem.custom),
        ).order_by(CustomCartItem.created_at)
        result = await self.session.execute(stmt)
        return result.scalars().all()