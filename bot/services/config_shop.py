"""Config shop service."""

from typing import Sequence

from bot.models.config_shop import ConfigProduct, ConfigProductStatus
from bot.services.base import BaseService
from bot.database.uow import UnitOfWork


class ConfigShopService(BaseService):
    """Config shop service for config product management."""

    def __init__(self, uow: UnitOfWork) -> None:
        super().__init__(uow)

    async def get_product(self, product_id: str) -> ConfigProduct | None:
        return await self.uow.config_products.get(product_id)

    async def get_by_category(
        self,
        category_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[ConfigProduct]:
        return await self.uow.config_products.get_by_category(
            category_id, offset=offset, limit=limit
        )

    async def count_by_category(self, category_id: str) -> int:
        return await self.uow.config_products.count_by_category(category_id)

    async def search_products(
        self,
        query: str,
        *,
        offset: int = 0,
        limit: int = 20,
        category_id: str | None = None,
    ) -> Sequence[ConfigProduct]:
        return await self.uow.config_products.search_products(
            query, offset=offset, limit=limit, category_id=category_id
        )

    async def get_latest(self, limit: int = 10) -> Sequence[ConfigProduct]:
        return await self.uow.config_products.get_latest_products(limit)

    async def create_product(
        self,
        title: str,
        price: int,
        category_id: str | None,
        title_en: str | None = None,
        description: str | None = None,
        short_description: str | None = None,
        original_price: int | None = None,
        stock: int = 0,
        unlimited_stock: bool = False,
        is_visible: bool = True,
        image_url: str | None = None,
        gallery: str | None = None,
        config_data: str | None = None,
        delivery_method: str = "manual",
        sort_order: int = 0,
    ) -> ConfigProduct:
        product = await self.uow.config_products.create(
            title=title,
            title_en=title_en,
            description=description,
            short_description=short_description,
            price=price,
            original_price=original_price,
            stock=stock,
            unlimited_stock=unlimited_stock,
            is_visible=is_visible,
            image_url=image_url,
            gallery=gallery,
            config_data=config_data,
            delivery_method=delivery_method,
            sort_order=sort_order,
            category_id=category_id,
            status=ConfigProductStatus.ACTIVE if (unlimited_stock or stock > 0) else ConfigProductStatus.OUT_OF_STOCK,
        )
        await self.uow.flush()
        return product

    async def update_product(self, product_id: str, **kwargs) -> ConfigProduct | None:
        if "stock" in kwargs and "unlimited_stock" not in kwargs:
            product = await self.uow.config_products.get(product_id)
            if product and not product.unlimited_stock:
                new_stock = kwargs["stock"]
                if new_stock == 0:
                    kwargs["status"] = ConfigProductStatus.OUT_OF_STOCK
                elif product.status == ConfigProductStatus.OUT_OF_STOCK and new_stock > 0:
                    kwargs["status"] = ConfigProductStatus.ACTIVE
        return await self.uow.config_products.update(product_id, **kwargs)

    async def delete_product(self, product_id: str) -> bool:
        return await self.uow.config_products.delete(product_id)

    async def toggle_visibility(self, product_id: str) -> ConfigProduct | None:
        product = await self.uow.config_products.get(product_id)
        if product:
            return await self.uow.config_products.update(product_id, is_visible=not product.is_visible)
        return None

    async def toggle_status(self, product_id: str) -> ConfigProduct | None:
        product = await self.uow.config_products.get(product_id)
        if product:
            new_status = ConfigProductStatus.INACTIVE if product.status == ConfigProductStatus.ACTIVE else ConfigProductStatus.ACTIVE
            return await self.uow.config_products.update(product_id, status=new_status)
        return None

    async def move_product(self, product_id: str, new_category_id: str | None) -> ConfigProduct | None:
        return await self.uow.config_products.update(product_id, category_id=new_category_id)

    async def increment_view(self, product_id: str) -> None:
        await self.uow.config_products.increment_view_count(product_id)

    async def process_purchase(self, product_id: str, quantity: int = 1) -> bool:
        success = await self.uow.config_products.decrease_stock(product_id, quantity)
        if success:
            await self.uow.config_products.increment_purchase_count(product_id)
        return success

    async def get_all_for_admin(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        category_id: str | None = None,
        status: ConfigProductStatus | None = None,
    ) -> Sequence[ConfigProduct]:
        return await self.uow.config_products.get_all_for_admin(
            offset=offset, limit=limit, category_id=category_id, status=status
        )

    async def count_for_admin(
        self,
        category_id: str | None = None,
        status: ConfigProductStatus | None = None,
    ) -> int:
        return await self.uow.config_products.count_for_admin(
            category_id=category_id, status=status
        )