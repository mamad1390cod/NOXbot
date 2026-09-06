"""Config product repository."""

from typing import Sequence

from sqlalchemy import Select, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.config_shop import ConfigProduct, ConfigProductStatus
from bot.repositories.base import BaseRepository


class ConfigProductRepository(BaseRepository[ConfigProduct]):
    """Config product repository with specialized queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ConfigProduct)

    async def get_by_category(
        self,
        category_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        visible_only: bool = True,
        status: ConfigProductStatus | None = None,
    ) -> Sequence[ConfigProduct]:
        """Get config products by category with pagination."""
        stmt = select(ConfigProduct).where(ConfigProduct.category_id == category_id)
        if visible_only:
            stmt = stmt.where(ConfigProduct.is_visible == True)
        if status:
            stmt = stmt.where(ConfigProduct.status == status)
        else:
            stmt = stmt.where(ConfigProduct.status != ConfigProductStatus.HIDDEN)
        stmt = stmt.order_by(ConfigProduct.sort_order, desc(ConfigProduct.created_at))
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_category(self, category_id: str, visible_only: bool = True) -> int:
        """Count config products in category."""
        stmt = select(func.count()).select_from(ConfigProduct).where(ConfigProduct.category_id == category_id)
        if visible_only:
            stmt = stmt.where(ConfigProduct.is_visible == True)
        stmt = stmt.where(ConfigProduct.status != ConfigProductStatus.HIDDEN)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def search_products(
        self,
        query: str,
        *,
        offset: int = 0,
        limit: int = 20,
        category_id: str | None = None,
    ) -> Sequence[ConfigProduct]:
        """Search config products by title or description."""
        stmt = select(ConfigProduct).where(
            or_(
                ConfigProduct.title.ilike(f"%{query}%"),
                ConfigProduct.description.ilike(f"%{query}%"),
            )
        ).where(ConfigProduct.is_visible == True, ConfigProduct.status == ConfigProductStatus.ACTIVE)
        if category_id:
            stmt = stmt.where(ConfigProduct.category_id == category_id)
        stmt = stmt.order_by(desc(ConfigProduct.created_at)).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_search(self, query: str, category_id: str | None = None) -> int:
        """Count config products matching search."""
        stmt = select(func.count()).select_from(ConfigProduct).where(
            or_(
                ConfigProduct.title.ilike(f"%{query}%"),
                ConfigProduct.description.ilike(f"%{query}%"),
            )
        ).where(ConfigProduct.is_visible == True, ConfigProduct.status == ConfigProductStatus.ACTIVE)
        if category_id:
            stmt = stmt.where(ConfigProduct.category_id == category_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_latest_products(self, limit: int = 10) -> Sequence[ConfigProduct]:
        """Get latest config products."""
        stmt = select(ConfigProduct).where(
            ConfigProduct.is_visible == True,
            ConfigProduct.status == ConfigProductStatus.ACTIVE,
        ).order_by(desc(ConfigProduct.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def increment_view_count(self, product_id: str) -> None:
        """Increment config product view count."""
        product = await self.get(product_id)
        if product:
            product.view_count += 1
            await self.session.flush()

    async def increment_purchase_count(self, product_id: str) -> None:
        """Increment config product purchase count."""
        product = await self.get(product_id)
        if product:
            product.purchase_count += 1
            await self.session.flush()

    async def decrease_stock(self, product_id: str, quantity: int = 1) -> bool:
        """Decrease config product stock. Returns False if not enough stock."""
        product = await self.get(product_id)
        if not product or product.unlimited_stock:
            return True
        if product.stock < quantity:
            return False
        product.stock -= quantity
        if product.stock == 0:
            product.status = ConfigProductStatus.OUT_OF_STOCK
        await self.session.flush()
        return True

    async def get_all_for_admin(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        category_id: str | None = None,
        status: ConfigProductStatus | None = None,
    ) -> Sequence[ConfigProduct]:
        """Get all config products for admin with filters."""
        stmt = select(ConfigProduct).order_by(desc(ConfigProduct.created_at))
        if category_id:
            stmt = stmt.where(ConfigProduct.category_id == category_id)
        if status:
            stmt = stmt.where(ConfigProduct.status == status)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_for_admin(
        self,
        category_id: str | None = None,
        status: ConfigProductStatus | None = None,
    ) -> int:
        """Count config products for admin with filters."""
        stmt = select(func.count()).select_from(ConfigProduct)
        if category_id:
            stmt = stmt.where(ConfigProduct.category_id == category_id)
        if status:
            stmt = stmt.where(ConfigProduct.status == status)
        result = await self.session.execute(stmt)
        return result.scalar_one()