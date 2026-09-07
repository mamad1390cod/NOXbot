"""Base repository with common CRUD operations."""

from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from bot.models.base import Base, UUIDMixin

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository with common database operations."""

    def __init__(self, session: AsyncSession, model: Type[ModelType]) -> None:
        self.session = session
        self.model = model

    async def get(self, id: str) -> ModelType | None:
        """Get entity by ID."""
        return await self.session.get(self.model, id)

    async def get_by(self, **kwargs: Any) -> ModelType | None:
        """Get single entity by filters."""
        stmt = select(self.model).filter_by(**kwargs)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        order_by: InstrumentedAttribute | None = None,
        **filters: Any,
    ) -> Sequence[ModelType]:
        """Get multiple entities with pagination and filters."""
        stmt = select(self.model).filter_by(**filters)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self, **filters: Any) -> int:
        """Count entities matching filters."""
        stmt = select(func.count()).select_from(self.model).filter_by(**filters)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def exists(self, **filters: Any) -> bool:
        """Check if entity exists."""
        return await self.count(**filters) > 0

    async def create(self, **kwargs: Any) -> ModelType:
        """Create new entity."""
        entity = self.model(**kwargs)
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(self, id: str, **kwargs: Any) -> ModelType | None:
        """Update entity by ID."""
        entity = await self.get(id)
        if entity is None:
            return None
        for key, value in kwargs.items():
            setattr(entity, key, value)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def delete(self, id: str) -> bool:
        """Delete entity by ID."""
        entity = await self.get(id)
        if entity is None:
            return False
        await self.session.delete(entity)
        await self.session.flush()
        return True

    async def execute(self, stmt: Select) -> Any:
        """Execute a custom select statement."""
        result = await self.session.execute(stmt)
        return result

    async def scalar(self, stmt: Select) -> Any:
        """Execute and return scalar."""
        result = await self.session.execute(stmt)
        return result.scalar()

    async def scalars(self, stmt: Select) -> Sequence[ModelType]:
        """Execute and return scalars."""
        result = await self.session.execute(stmt)
        return result.scalars().all()