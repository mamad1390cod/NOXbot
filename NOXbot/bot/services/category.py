"""Category service."""

from typing import Sequence

from bot.models.category import Category
from bot.services.base import BaseService
from bot.database.uow import UnitOfWork


class CategoryService(BaseService):
    """Category service for category management."""

    def __init__(self, uow: UnitOfWork) -> None:
        super().__init__(uow)

    async def get_by_type(self, type: str, active_only: bool = True) -> Sequence[Category]:
        """Get categories by type."""
        return await self.uow.categories.get_by_type(type, active_only=active_only)

    async def get_root_categories(self, type: str) -> Sequence[Category]:
        """Get root categories by type."""
        return await self.uow.categories.get_root_categories(type)

    async def get_children(self, parent_id: str) -> Sequence[Category]:
        """Get child categories."""
        return await self.uow.categories.get_children(parent_id)

    async def get_visible_categories(self, type: str) -> Sequence[Category]:
        """Get visible categories by type."""
        return await self.uow.categories.get_visible_categories(type)

    async def get_category_tree(self, type: str) -> Sequence[Category]:
        """Get full category tree."""
        return await self.uow.categories.get_category_tree(type)

    async def create_category(
        self,
        name: str,
        type: str,
        name_en: str | None = None,
        description: str | None = None,
        parent_id: str | None = None,
        image_url: str | None = None,
        sort_order: int | None = None,
    ) -> Category:
        """Create new category."""
        if sort_order is None:
            sort_order = await self.uow.categories.get_max_sort_order(type, parent_id)

        category = await self.uow.categories.create(
            name=name,
            name_en=name_en,
            description=description,
            type=type,
            parent_id=parent_id,
            image_url=image_url,
            sort_order=sort_order,
        )
        await self.uow.flush()
        return category

    async def update_category(self, category_id: str, **kwargs) -> Category | None:
        """Update category."""
        return await self.uow.categories.update(category_id, **kwargs)

    async def delete_category(self, category_id: str) -> bool:
        """Delete category."""
        return await self.uow.categories.delete(category_id)

    async def move_category(self, category_id: str, new_parent_id: str | None, new_sort_order: int) -> Category | None:
        """Move category."""
        return await self.uow.categories.move_category(category_id, new_parent_id, new_sort_order)

    async def toggle_visibility(self, category_id: str) -> Category | None:
        """Toggle category visibility."""
        category = await self.uow.categories.get(category_id)
        if category:
            return await self.uow.categories.update(category_id, is_visible=not category.is_visible)
        return None

    async def toggle_active(self, category_id: str) -> Category | None:
        """Toggle category active status."""
        category = await self.uow.categories.get(category_id)
        if category:
            return await self.uow.categories.update(category_id, is_active=not category.is_active)
        return None

    async def get_all_for_admin(
        self,
        type: str,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[Category]:
        """Get all categories for admin."""
        return await self.uow.categories.get_all(
            offset=offset,
            limit=limit,
            type=type,
            order_by=Category.sort_order,
        )