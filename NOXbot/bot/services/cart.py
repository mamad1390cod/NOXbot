"""Cart service."""

from typing import Sequence

from bot.models.cart import Cart, CartItem
from bot.models.product import Product
from bot.models.config_shop import ConfigProduct
from bot.services.base import BaseService
from bot.database.uow import UnitOfWork


class CartService(BaseService):
    """Cart service for shopping cart management."""

    def __init__(self, uow: UnitOfWork) -> None:
        super().__init__(uow)

    async def get_cart(self, user_id: str) -> Cart | None:
        """Get user's cart with items."""
        return await self.uow.carts.get_by_user_id(user_id)

    async def get_or_create_cart(self, user_id: str) -> Cart:
        """Get or create user's cart."""
        return await self.uow.carts.get_or_create(user_id)

    async def add_product(
        self,
        user_id: str,
        product_id: str,
        quantity: int = 1,
        account_data: str | None = None,
    ) -> CartItem:
        """Add product to cart."""
        cart = await self.get_or_create_cart(user_id)

        # Verify product exists and is available
        product = await self.uow.products.get(product_id)
        if not product:
            raise ValueError("محصول یافت نشد")
        if not product.is_visible:
            raise ValueError("محصول در دسترس نیست")
        if product.status != Product.__dict__["status"].type.python_type.ACTIVE and not product.unlimited_stock and product.stock == 0:
            raise ValueError("موجودی محصول تمام شده است")

        # Check stock
        if not product.unlimited_stock and product.stock < quantity:
            raise ValueError("موجودی کافی نیست")

        return await self.uow.carts.add_item(
            cart_id=cart.id,
            product_id=product_id,
            quantity=quantity,
            account_data=account_data,
        )

    async def add_config(
        self,
        user_id: str,
        config_product_id: str,
        quantity: int = 1,
    ) -> CartItem:
        """Add config product to cart."""
        cart = await self.get_or_create_cart(user_id)

        # Verify config product exists
        config = await self.uow.config_products.get(config_product_id)
        if not config:
            raise ValueError("کانفیگ یافت نشد")
        if not config.is_visible:
            raise ValueError("کانفیگ در دسترس نیست")
        if not config.is_in_stock:
            raise ValueError("موجودی کانفیگ تمام شده است")

        if not config.unlimited_stock and config.stock < quantity:
            raise ValueError("موجودی کافی نیست")

        return await self.uow.carts.add_item(
            cart_id=cart.id,
            config_product_id=config_product_id,
            quantity=quantity,
        )

    async def update_quantity(self, user_id: str, item_id: str, quantity: int) -> CartItem | None:
        """Update item quantity in cart."""
        cart = await self.get_cart(user_id)
        if not cart:
            raise ValueError("سبد خرید یافت نشد")

        item = await self.uow.carts.get_item(item_id)
        if not item or item.cart_id != cart.id:
            raise ValueError("آیتم در سبد خرید یافت نشد")

        # Check stock for products
        if item.product_id:
            product = await self.uow.products.get(item.product_id)
            if product and not product.unlimited_stock and product.stock < quantity:
                raise ValueError("موجودی کافی نیست")
        elif item.config_product_id:
            config = await self.uow.config_products.get(item.config_product_id)
            if config and not config.unlimited_stock and config.stock < quantity:
                raise ValueError("موجودی کافی نیست")

        return await self.uow.carts.update_quantity(item_id, quantity)

    async def remove_item(self, user_id: str, item_id: str) -> bool:
        """Remove item from cart."""
        cart = await self.get_cart(user_id)
        if not cart:
            raise ValueError("سبد خرید یافت نشد")

        item = await self.uow.carts.get_item(item_id)
        if not item or item.cart_id != cart.id:
            raise ValueError("آیتم در سبد خرید یافت نشد")

        return await self.uow.carts.remove_item(item_id)

    async def clear_cart(self, user_id: str) -> int:
        """Clear all items from cart."""
        cart = await self.get_cart(user_id)
        if not cart:
            return 0
        return await self.uow.carts.clear_cart(cart.id)

    async def get_cart_items(self, user_id: str) -> Sequence[CartItem]:
        """Get all cart items with products loaded."""
        cart = await self.get_cart(user_id)
        if not cart:
            return []
        return await self.uow.carts.get_cart_items(cart.id)

    async def get_cart_summary(self, user_id: str) -> dict:
        """Get cart summary with totals."""
        cart = await self.get_cart(user_id)
        if not cart:
            return {
                "items": [],
                "total_items": 0,
                "total_price": 0,
                "products_count": 0,
                "configs_count": 0,
            }

        items = await self.uow.carts.get_cart_items(cart.id)

        products_count = sum(1 for item in items if item.product_id)
        configs_count = sum(1 for item in items if item.config_product_id)

        return {
            "items": items,
            "total_items": cart.total_items,
            "total_price": cart.total_price,
            "products_count": products_count,
            "configs_count": configs_count,
        }

    async def prepare_order_items(self, user_id: str) -> list[dict]:
        """Prepare cart items for order creation."""
        cart = await self.get_cart(user_id)
        if not cart:
            return []

        items = await self.uow.carts.get_cart_items(cart.id)
        order_items = []

        for item in items:
            if item.product_id:
                product = item.product
                if not product:
                    continue
                order_items.append({
                    "product_id": product.id,
                    "config_product_id": None,
                    "quantity": item.quantity,
                    "unit_price": product.discounted_price,
                    "total_price": product.discounted_price * item.quantity,
                    "title": product.title,
                    "product_type": "product",
                })
            elif item.config_product_id:
                config = item.config_product
                if not config:
                    continue
                order_items.append({
                    "product_id": None,
                    "config_product_id": config.id,
                    "quantity": item.quantity,
                    "unit_price": config.price,
                    "total_price": config.price * item.quantity,
                    "title": config.title,
                    "product_type": "config",
                })

        return order_items