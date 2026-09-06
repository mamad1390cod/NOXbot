"""Broadcast repository."""

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.broadcast import Broadcast, BroadcastStatus, BroadcastTemplate
from bot.repositories.base import BaseRepository


class BroadcastRepository(BaseRepository[Broadcast]):
    """Repository for broadcast jobs."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Broadcast)

    async def due(self) -> Sequence[Broadcast]:
        """Broadcasts scheduled at or before now and pending."""
        stmt = select(Broadcast).where(
            Broadcast.status == BroadcastStatus.PENDING,
            Broadcast.scheduled_at <= datetime.now(timezone.utc),
        ).order_by(Broadcast.scheduled_at)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def by_status(self, status: BroadcastStatus, limit: int = 50) -> Sequence[Broadcast]:
        stmt = select(Broadcast).where(Broadcast.status == status).order_by(Broadcast.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def recent(self, limit: int = 20) -> Sequence[Broadcast]:
        stmt = select(Broadcast).order_by(Broadcast.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class BroadcastTemplateRepository(BaseRepository[BroadcastTemplate]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, BroadcastTemplate)

    async def list_templates(self, limit: int = 50) -> Sequence[BroadcastTemplate]:
        stmt = select(BroadcastTemplate).order_by(BroadcastTemplate.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()