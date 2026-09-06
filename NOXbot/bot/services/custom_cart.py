"""Custom cart service."""

from typing import Sequence

from bot.models.custom import CustomCart, CustomCartItem, CustomStatus
from bot.services.base import BaseService
from bot.database.uow import UnitOfWork


class CustomCartService(BaseService):
    """Custom cart service for tournament registration cart."""

    def __init__(self, uow: UnitOfWork) -> None:
        super().__init__(uow)

    async def get_cart(self, user_id: str) -> CustomCart | None:
        return await self.uow.custom_carts.get_by_user_id(user_id)

    async def get_or_create_cart(self, user_id: str) -> CustomCart:
        return await self.uow.custom_carts.get_or_create(user_id)

    async def add_custom(self, user_id: str, custom_id: str, team_name: str | None = None) -> CustomCartItem:
        """Add custom to cart."""
        cart = await self.get_or_create_cart(user_id)

        # Verify custom exists and registration is open
        custom = await self.uow.customs.get(custom_id)
        if not custom:
            raise ValueError("کاستوم یافت نشد")
        if not custom.can_register:
            raise ValueError("ثبت‌نام این کاستوم فعال نیست یا ظرفیت پر شده است")

        # Prevent duplicates
        existing = await self.get_items(user_id)
        for item in existing:
            if item.custom_id == custom_id:
                raise ValueError("این کاستوم قبلاً در سبد کاستوم شما است")

        item = await self.uow.custom_carts.add_item(
            cart_id=cart.id,
            custom_id=custom_id,
            team_name=team_name,
        )
        await self.uow.flush()
        return item

    async def remove_item(self, user_id: str, item_id: str) -> bool:
        cart = await self.get_cart(user_id)
        if not cart:
            raise ValueError("سبد کاستوم یافت نشد")
        return await self.uow.custom_carts.remove_item(item_id)

    async def clear_cart(self, user_id: str) -> int:
        cart = await self.get_cart(user_id)
        if not cart:
            return 0
        return await self.uow.custom_carts.clear_cart(cart.id)

    async def get_items(self, user_id: str) -> Sequence[CustomCartItem]:
        cart = await self.get_cart(user_id)
        if not cart:
            return []
        return await self.uow.custom_carts.get_items(cart.id)

    async def get_cart_summary(self, user_id: str) -> dict:
        cart = await self.get_cart(user_id)
        if not cart:
            return {"items": [], "total_items": 0, "total_price": 0}

        items = await self.uow.custom_carts.get_items(cart.id)
        total_price = 0
        for item in items:
            if item.custom and item.custom.type == "paid":
                total_price += item.custom.entry_fee

        return {
            "items": items,
            "total_items": len(items),
            "total_price": total_price,
        }