"""Category repository."""

from typing import Sequence

from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.category import Category
from bot.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    """Category repository with specialized queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Category)

    async def get_by_type(self, type: str, *, active_only: bool = True) -> Sequence[Category]:
        """Get categories by type."""
        stmt = select(Category).where(Category.type == type)
        if active_only:
            stmt = stmt.where(Category.is_active == True)
        stmt = stmt.order_by(Category.sort_order, Category.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_root_categories(self, type: str) -> Sequence[Category]:
        """Get root categories (no parent) by type."""
        stmt = select(Category).where(
            Category.type == type,
            Category.parent_id.is_(None),
            Category.is_active == True,
        ).order_by(Category.sort_order, Category.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_children(self, parent_id: str) -> Sequence[Category]:
        """Get child categories."""
        stmt = select(Category).where(
            Category.parent_id == parent_id,
            Category.is_active == True,
        ).order_by(Category.sort_order, Category.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_visible_categories(self, type: str) -> Sequence[Category]:
        """Get visible categories by type."""
        stmt = select(Category).where(
            Category.type == type,
            Category.is_active == True,
            Category.is_visible == True,
        ).order_by(Category.sort_order, Category.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_category_tree(self, type: str) -> Sequence[Category]:
        """Get full category tree for a type."""
        stmt = select(Category).where(
            Category.type == type,
            Category.is_active == True,
        ).order_by(Category.sort_order, Category.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def move_category(self, category_id: str, new_parent_id: str | None, new_sort_order: int) -> Category | None:
        """Move category to new parent with new sort order."""
        return await self.update(
            category_id,
            parent_id=new_parent_id,
            sort_order=new_sort_order,
        )

    async def get_max_sort_order(self, type: str, parent_id: str | None = None) -> int:
        """Get maximum sort order for a category type/parent."""
        stmt = select(func.max(Category.sort_order)).where(Category.type == type)
        if parent_id:
            stmt = stmt.where(Category.parent_id == parent_id)
        else:
            stmt = stmt.where(Category.parent_id.is_(None))
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) + 1