"""Product service."""

from typing import Sequence

from bot.models.product import Product, ProductStatus, ProductType
from bot.services.base import BaseService
from bot.database.uow import UnitOfWork


class ProductService(BaseService):
    """Product service for product management."""

    def __init__(self, uow: UnitOfWork) -> None:
        super().__init__(uow)

    async def get_product(self, product_id: str) -> Product | None:
        """Get product by ID."""
        return await self.uow.products.get(product_id)

    async def get_by_category(
        self,
        category_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        visible_only: bool = True,
        status: ProductStatus | None = None,
    ) -> Sequence[Product]:
        """Get products by category."""
        return await self.uow.products.get_by_category(
            category_id,
            offset=offset,
            limit=limit,
            visible_only=visible_only,
            status=status,
        )

    async def count_by_category(self, category_id: str, visible_only: bool = True) -> int:
        """Count products in category."""
        return await self.uow.products.count_by_category(category_id, visible_only)

    async def search_products(
        self,
        query: str,
        *,
        offset: int = 0,
        limit: int = 20,
        category_id: str | None = None,
    ) -> Sequence[Product]:
        """Search products."""
        return await self.uow.products.search_products(query, offset=offset, limit=limit, category_id=category_id)

    async def count_search(self, query: str, category_id: str | None = None) -> int:
        """Count search results."""
        return await self.uow.products.count_search(query, category_id)

    async def get_featured(self, limit: int = 10) -> Sequence[Product]:
        """Get featured products."""
        return await self.uow.products.get_featured_products(limit)

    async def get_latest(self, limit: int = 10) -> Sequence[Product]:
        """Get latest products."""
        return await self.uow.products.get_latest_products(limit)

    async def get_by_type(
        self,
        product_type: ProductType,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[Product]:
        """Get products by type."""
        return await self.uow.products.get_products_by_type(product_type, offset=offset, limit=limit)

    async def create_product(
        self,
        title: str,
        category_id: str | None,
        price: int,
        title_en: str | None = None,
        description: str | None = None,
        short_description: str | None = None,
        product_type: ProductType = ProductType.DIGITAL,
        original_price: int | None = None,
        stock: int = 0,
        unlimited_stock: bool = False,
        min_order: int = 1,
        max_order: int | None = None,
        is_visible: bool = True,
        requires_account_info: bool = False,
        account_fields: str | None = None,
        image_url: str | None = None,
        gallery: str | None = None,
        sort_order: int = 0,
    ) -> Product:
        """Create new product."""
        product = await self.uow.products.create(
            title=title,
            title_en=title_en,
            description=description,
            short_description=short_description,
            type=product_type,
            price=price,
            original_price=original_price,
            stock=stock,
            unlimited_stock=unlimited_stock,
            min_order=min_order,
            max_order=max_order,
            is_visible=is_visible,
            requires_account_info=requires_account_info,
            account_fields=account_fields,
            image_url=image_url,
            gallery=gallery,
            sort_order=sort_order,
            category_id=category_id,
            status=ProductStatus.ACTIVE if (unlimited_stock or stock > 0) else ProductStatus.OUT_OF_STOCK,
        )
        await self.uow.flush()
        return product

    async def update_product(self, product_id: str, **kwargs) -> Product | None:
        """Update product."""
        # Handle stock changes
        if "stock" in kwargs and "unlimited_stock" not in kwargs:
            product = await self.uow.products.get(product_id)
            if product and not product.unlimited_stock:
                new_stock = kwargs["stock"]
                if new_stock == 0:
                    kwargs["status"] = ProductStatus.OUT_OF_STOCK
                elif product.status == ProductStatus.OUT_OF_STOCK and new_stock > 0:
                    kwargs["status"] = ProductStatus.ACTIVE
        return await self.uow.products.update(product_id, **kwargs)

    async def delete_product(self, product_id: str) -> bool:
        """Delete product."""
        return await self.uow.products.delete(product_id)

    async def duplicate_product(self, product_id: str, new_title: str | None = None) -> Product | None:
        """Duplicate product."""
        product = await self.uow.products.get(product_id)
        if not product:
            return None

        new_product = await self.uow.products.create(
            title=new_title or f"{product.title} (کپی)",
            title_en=product.title_en,
            description=product.description,
            short_description=product.short_description,
            type=product.type,
            price=product.price,
            original_price=product.original_price,
            stock=0,  # New product starts with 0 stock
            unlimited_stock=product.unlimited_stock,
            min_order=product.min_order,
            max_order=product.max_order,
            is_visible=False,  # Hidden by default
            requires_account_info=product.requires_account_info,
            account_fields=product.account_fields,
            image_url=product.image_url,
            gallery=product.gallery,
            sort_order=product.sort_order + 1,
            category_id=product.category_id,
            status=ProductStatus.INACTIVE,
        )
        await self.uow.flush()
        return new_product

    async def toggle_visibility(self, product_id: str) -> Product | None:
        """Toggle product visibility."""
        product = await self.uow.products.get(product_id)
        if product:
            return await self.uow.products.update(product_id, is_visible=not product.is_visible)
        return None

    async def toggle_status(self, product_id: str) -> Product | None:
        """Toggle product active status."""
        product = await self.uow.products.get(product_id)
        if product:
            new_status = ProductStatus.INACTIVE if product.status == ProductStatus.ACTIVE else ProductStatus.ACTIVE
            return await self.uow.products.update(product_id, status=new_status)
        return None

    async def move_product(self, product_id: str, new_category_id: str | None) -> Product | None:
        """Move product to different category."""
        return await self.uow.products.update(product_id, category_id=new_category_id)

    async def increment_view(self, product_id: str) -> None:
        """Increment view count."""
        await self.uow.products.increment_view_count(product_id)

    async def process_purchase(self, product_id: str, quantity: int = 1) -> bool:
        """Process product purchase (decrease stock, increment purchase count)."""
        success = await self.uow.products.decrease_stock(product_id, quantity)
        if success:
            await self.uow.products.increment_purchase_count(product_id)
        return success

    async def get_all_for_admin(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        category_id: str | None = None,
        status: ProductStatus | None = None,
        product_type: ProductType | None = None,
    ) -> Sequence[Product]:
        """Get all products for admin."""
        return await self.uow.products.get_all_for_admin(
            offset=offset,
            limit=limit,
            category_id=category_id,
            status=status,
            product_type=product_type,
        )

    async def count_for_admin(
        self,
        category_id: str | None = None,
        status: ProductStatus | None = None,
        product_type: ProductType | None = None,
    ) -> int:
        """Count products for admin."""
        return await self.uow.products.count_for_admin(
            category_id=category_id,
            status=status,
            product_type=product_type,
        )