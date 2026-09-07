"""Admin log repository."""

from typing import Sequence

from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models.log import AdminLog, LogAction
from bot.repositories.base import BaseRepository


class AdminLogRepository(BaseRepository[AdminLog]):
    """Admin log repository with specialized queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AdminLog)

    async def log_action(
        self,
        admin_id: str | None,
        action: LogAction,
        target_type: str | None = None,
        target_id: str | None = None,
        description: str | None = None,
        old_data: str | None = None,
        new_data: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
    ) -> AdminLog:
        """Create a new admin log entry."""
        log = AdminLog(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            description=description,
            old_data=old_data,
            new_data=new_data,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
        )
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def get_logs(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        admin_id: str | None = None,
        action: LogAction | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> Sequence[AdminLog]:
        """Get logs with filters."""
        stmt = select(AdminLog).options(
            selectinload(AdminLog.admin),
        ).order_by(desc(AdminLog.created_at))
        if admin_id:
            stmt = stmt.where(AdminLog.admin_id == admin_id)
        if action:
            stmt = stmt.where(AdminLog.action == action)
        if target_type:
            stmt = stmt.where(AdminLog.target_type == target_type)
        if target_id:
            stmt = stmt.where(AdminLog.target_id == target_id)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_logs(
        self,
        admin_id: str | None = None,
        action: LogAction | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> int:
        """Count logs with filters."""
        stmt = select(func.count()).select_from(AdminLog)
        if admin_id:
            stmt = stmt.where(AdminLog.admin_id == admin_id)
        if action:
            stmt = stmt.where(AdminLog.action == action)
        if target_type:
            stmt = stmt.where(AdminLog.target_type == target_type)
        if target_id:
            stmt = stmt.where(AdminLog.target_id == target_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_recent_logs(self, limit: int = 20) -> Sequence[AdminLog]:
        """Get recent admin logs."""
        stmt = select(AdminLog).options(
            selectinload(AdminLog.admin),
        ).order_by(desc(AdminLog.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_logs_by_target(self, target_type: str, target_id: str) -> Sequence[AdminLog]:
        """Get all logs for a specific target."""
        stmt = select(AdminLog).where(
            AdminLog.target_type == target_type,
            AdminLog.target_id == target_id,
        ).order_by(desc(AdminLog.created_at))
        result = await self.session.execute(stmt)
        return result.scalars().all()