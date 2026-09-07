"""Product repository."""

from typing import Sequence

from sqlalchemy import BigInteger, Select, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.product import Product, ProductStatus, ProductType
from bot.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    """Product repository with specialized queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Product)

    async def get_by_category(
        self,
        category_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        visible_only: bool = True,
        status: ProductStatus | None = None,
    ) -> Sequence[Product]:
        """Get products by category with pagination."""
        stmt = select(Product).where(Product.category_id == category_id)
        if visible_only:
            stmt = stmt.where(Product.is_visible == True)
        if status:
            stmt = stmt.where(Product.status == status)
        else:
            stmt = stmt.where(Product.status != ProductStatus.HIDDEN)
        stmt = stmt.order_by(Product.sort_order, desc(Product.created_at))
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_category(self, category_id: str, visible_only: bool = True) -> int:
        """Count products in category."""
        stmt = select(func.count()).select_from(Product).where(Product.category_id == category_id)
        if visible_only:
            stmt = stmt.where(Product.is_visible == True)
        stmt = stmt.where(Product.status != ProductStatus.HIDDEN)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def search_products(
        self,
        query: str,
        *,
        offset: int = 0,
        limit: int = 20,
        category_id: str | None = None,
    ) -> Sequence[Product]:
        """Search products by title or description."""
        stmt = select(Product).where(
            or_(
                Product.title.ilike(f"%{query}%"),
                Product.description.ilike(f"%{query}%"),
            )
        ).where(Product.is_visible == True, Product.status == ProductStatus.ACTIVE)
        if category_id:
            stmt = stmt.where(Product.category_id == category_id)
        stmt = stmt.order_by(desc(Product.created_at)).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_search(self, query: str, category_id: str | None = None) -> int:
        """Count products matching search."""
        stmt = select(func.count()).select_from(Product).where(
            or_(
                Product.title.ilike(f"%{query}%"),
                Product.description.ilike(f"%{query}%"),
            )
        ).where(Product.is_visible == True, Product.status == ProductStatus.ACTIVE)
        if category_id:
            stmt = stmt.where(Product.category_id == category_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_featured_products(self, limit: int = 10) -> Sequence[Product]:
        """Get featured products (highest purchase count)."""
        stmt = select(Product).where(
            Product.is_visible == True,
            Product.status == ProductStatus.ACTIVE,
        ).order_by(desc(Product.purchase_count), desc(Product.view_count)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_latest_products(self, limit: int = 10) -> Sequence[Product]:
        """Get latest products."""
        stmt = select(Product).where(
            Product.is_visible == True,
            Product.status == ProductStatus.ACTIVE,
        ).order_by(desc(Product.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_products_by_type(
        self,
        product_type: ProductType,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[Product]:
        """Get products by type."""
        stmt = select(Product).where(
            Product.type == product_type,
            Product.is_visible == True,
            Product.status == ProductStatus.ACTIVE,
        ).order_by(desc(Product.created_at)).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def increment_view_count(self, product_id: str) -> None:
        """Increment product view count."""
        product = await self.get(product_id)
        if product:
            product.view_count += 1
            await self.session.flush()

    async def increment_purchase_count(self, product_id: str) -> None:
        """Increment product purchase count."""
        product = await self.get(product_id)
        if product:
            product.purchase_count += 1
            await self.session.flush()

    async def decrease_stock(self, product_id: str, quantity: int = 1) -> bool:
        """Decrease product stock. Returns False if not enough stock."""
        product = await self.get(product_id)
        if not product or product.unlimited_stock:
            return True
        if product.stock < quantity:
            return False
        product.stock -= quantity
        if product.stock == 0:
            product.status = ProductStatus.OUT_OF_STOCK
        await self.session.flush()
        return True

    async def increase_stock(self, product_id: str, quantity: int = 1) -> None:
        """Increase product stock."""
        product = await self.get(product_id)
        if product and not product.unlimited_stock:
            product.stock += quantity
            if product.stock > 0 and product.status == ProductStatus.OUT_OF_STOCK:
                product.status = ProductStatus.ACTIVE
            await self.session.flush()

    async def get_all_for_admin(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        category_id: str | None = None,
        status: ProductStatus | None = None,
        product_type: ProductType | None = None,
    ) -> Sequence[Product]:
        """Get all products for admin with filters."""
        stmt = select(Product).order_by(desc(Product.created_at))
        if category_id:
            stmt = stmt.where(Product.category_id == category_id)
        if status:
            stmt = stmt.where(Product.status == status)
        if product_type:
            stmt = stmt.where(Product.type == product_type)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_for_admin(
        self,
        category_id: str | None = None,
        status: ProductStatus | None = None,
        product_type: ProductType | None = None,
    ) -> int:
        """Count products for admin with filters."""
        stmt = select(func.count()).select_from(Product)
        if category_id:
            stmt = stmt.where(Product.category_id == category_id)
        if status:
            stmt = stmt.where(Product.status == status)
        if product_type:
            stmt = stmt.where(Product.type == product_type)
        result = await self.session.execute(stmt)
        return result.scalar_one()