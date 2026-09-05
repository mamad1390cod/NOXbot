"""Cart repository."""

from typing import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models.cart import Cart, CartItem
from bot.repositories.base import BaseRepository


class CartRepository(BaseRepository[Cart]):
    """Cart repository with specialized queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Cart)

    async def get_by_user_id(self, user_id: str) -> Cart | None:
        """Get cart by user ID with items loaded."""
        stmt = select(Cart).where(Cart.user_id == user_id).options(
            selectinload(Cart.items).selectinload(CartItem.product),
            selectinload(Cart.items).selectinload(CartItem.config_product),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: str) -> Cart:
        """Get existing cart or create new one."""
        cart = await self.get_by_user_id(user_id)
        if cart is None:
            cart = await self.create(user_id=user_id)
        return cart

    async def add_item(
        self,
        cart_id: str,
        product_id: str | None = None,
        config_product_id: str | None = None,
        quantity: int = 1,
        account_data: str | None = None,
    ) -> CartItem:
        """Add item to cart or update quantity if exists."""
        from bot.models.cart import CartItem
        from bot.models.product import Product
        from bot.models.config_shop import ConfigProduct

        # Check if item already exists
        stmt = select(CartItem).where(CartItem.cart_id == cart_id)
        if product_id:
            stmt = stmt.where(CartItem.product_id == product_id)
        elif config_product_id:
            stmt = stmt.where(CartItem.config_product_id == config_product_id)
        result = await self.session.execute(stmt)
        existing_item = result.scalar_one_or_none()

        if existing_item:
            existing_item.quantity += quantity
            if account_data:
                existing_item.account_data = account_data
            await self.session.flush()
            await self.session.refresh(existing_item)
            return existing_item

        # Create new item
        item = CartItem(
            cart_id=cart_id,
            product_id=product_id,
            config_product_id=config_product_id,
            quantity=quantity,
            account_data=account_data,
        )
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def update_quantity(self, item_id: str, quantity: int) -> CartItem | None:
        """Update item quantity. If quantity <= 0, remove item."""
        if quantity <= 0:
            await self.remove_item(item_id)
            return None
        item = await self.session.get(CartItem, item_id)
        if item:
            item.quantity = quantity
            await self.session.flush()
            await self.session.refresh(item)
        return item

    async def remove_item(self, item_id: str) -> bool:
        """Remove item from cart."""
        item = await self.session.get(CartItem, item_id)
        if item:
            await self.session.delete(item)
            await self.session.flush()
            return True
        return False

    async def clear_cart(self, cart_id: str) -> int:
        """Clear all items from cart. Returns number of removed items."""
        stmt = select(CartItem).where(CartItem.cart_id == cart_id)
        result = await self.session.execute(stmt)
        items = result.scalars().all()
        count = len(items)
        for item in items:
            await self.session.delete(item)
        await self.session.flush()
        return count

    async def get_cart_items(self, cart_id: str) -> Sequence[CartItem]:
        """Get all cart items with products loaded."""
        stmt = select(CartItem).where(CartItem.cart_id == cart_id).options(
            selectinload(CartItem.product),
            selectinload(CartItem.config_product),
        ).order_by(CartItem.created_at)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_item(self, item_id: str) -> CartItem | None:
        """Get cart item by ID with relations."""
        stmt = select(CartItem).where(CartItem.id == item_id).options(
            selectinload(CartItem.product),
            selectinload(CartItem.config_product),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()