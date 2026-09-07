"""Anti-abuse repository — events and auto-actions."""

from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models.abuse import AbuseEvent, AbuseType, AutoAction, AutoActionType, Severity
from bot.repositories.base import BaseRepository


class AbuseRepository(BaseRepository[AbuseEvent]):
    """Repository for abuse events and auto-actions."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AbuseEvent)

    # --- Events ----------------------------------------------------------- #
    async def add_event(
        self,
        user_id: str | None,
        type_: AbuseType,
        severity: Severity = Severity.MEDIUM,
        event_data: str | None = None,
        source: str | None = None,
        ip_address: str | None = None,
    ) -> AbuseEvent:
        ev = AbuseEvent(
            user_id=user_id,
            type=type_,
            severity=severity,
            event_data=event_data,
            source=source,
            ip_address=ip_address,
        )
        self.session.add(ev)
        await self.session.flush()
        await self.session.refresh(ev)
        return ev

    async def recent_events(
        self, user_id: str | None = None, limit: int = 50
    ) -> Sequence[AbuseEvent]:
        stmt = (
            select(AbuseEvent)
            .options(selectinload(AbuseEvent.user))
            if not user_id else
            select(AbuseEvent)
            .where(AbuseEvent.user_id == user_id)
            .options(selectinload(AbuseEvent.user))
        )
        stmt = stmt.order_by(desc(AbuseEvent.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_for_user(self, user_id: str, type_: AbuseType, minutes: int = 60) -> int:
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        stmt = select(func.count()).select_from(AbuseEvent).where(
            AbuseEvent.user_id == user_id,
            AbuseEvent.type == type_,
            AbuseEvent.created_at >= since,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def violation_summary(self) -> dict:
        stmt = select(AbuseEvent.type, func.count(AbuseEvent.id)).group_by(AbuseEvent.type)
        result = await self.session.execute(stmt)
        summary = {}
        for t, c in result.all():
            summary[AbuseType(t).value] = c
        return summary

    # --- Auto-actions ----------------------------------------------------- #
    async def active_action(
        self, user_id: str, action: AutoActionType | None = None
    ) -> AutoAction | None:
        stmt = select(AutoAction).where(
            AutoAction.user_id == user_id,
            AutoAction.active == True,
        )
        if action is not None:
            stmt = stmt.where(AutoAction.action == action)
        stmt = stmt.order_by(desc(AutoAction.applied_at)).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_action(
        self,
        user_id: str,
        action: AutoActionType,
        reason: str | None = None,
        duration_seconds: int | None = None,
        is_manual: bool = False,
        applied_by: str | None = None,
    ) -> AutoAction:
        applied_at = datetime.now(timezone.utc)
        expires_at = (applied_at + timedelta(seconds=duration_seconds)) if duration_seconds else None
        ac = AutoAction(
            user_id=user_id,
            action=action,
            reason=reason,
            duration_seconds=duration_seconds,
            applied_at=applied_at,
            expires_at=expires_at,
            active=True,
            is_manual=is_manual,
            admin_applied_by=applied_by,
        )
        self.session.add(ac)
        await self.session.flush()
        await self.session.refresh(ac)
        return ac

    async def lift_active(self, user_id: str) -> int:
        stmt = select(AutoAction).where(
            AutoAction.user_id == user_id,
            AutoAction.active == True,
        )
        result = await self.session.execute(stmt)
        actions = result.scalars().all()
        for a in actions:
            a.active = False
            a.lifted_at = datetime.now(timezone.utc)
        await self.session.flush()
        return len(actions)