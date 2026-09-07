"""Ticket repository."""

from typing import Sequence

from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models.ticket import Ticket, TicketCategory, TicketMessage, TicketStatus, TicketPriority
from bot.repositories.base import BaseRepository


class TicketCategoryRepository(BaseRepository[TicketCategory]):
    """Ticket category repository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TicketCategory)

    async def get_active_categories(self) -> Sequence[TicketCategory]:
        """Get all active ticket categories."""
        stmt = select(TicketCategory).where(
            TicketCategory.is_active == True
        ).order_by(TicketCategory.sort_order, TicketCategory.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_for_admin(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[TicketCategory]:
        """Get all ticket categories for admin."""
        stmt = select(TicketCategory).order_by(
            TicketCategory.sort_order, TicketCategory.name
        ).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class TicketRepository(BaseRepository[Ticket]):
    """Ticket repository with specialized queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Ticket)

    async def get_by_user(
        self,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        status: TicketStatus | None = None,
    ) -> Sequence[Ticket]:
        """Get tickets by user."""
        stmt = select(Ticket).where(Ticket.user_id == user_id).options(
            selectinload(Ticket.ticket_category),
            selectinload(Ticket.messages),
        )
        if status:
            stmt = stmt.where(Ticket.status == status)
        stmt = stmt.order_by(desc(Ticket.created_at)).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_open_tickets(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        category_id: str | None = None,
    ) -> Sequence[Ticket]:
        """Get open tickets for admin."""
        stmt = select(Ticket).where(
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_USER])
        ).options(
            selectinload(Ticket.user),
            selectinload(Ticket.ticket_category),
        )
        if category_id:
            stmt = stmt.where(Ticket.ticket_category_id == category_id)
        stmt = stmt.order_by(Ticket.created_at).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_closed_tickets(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[Ticket]:
        """Get closed tickets for admin."""
        stmt = select(Ticket).where(Ticket.status == TicketStatus.CLOSED).options(
            selectinload(Ticket.user),
            selectinload(Ticket.ticket_category),
            selectinload(Ticket.closed_by_user),
        ).order_by(desc(Ticket.closed_at)).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_ticket_with_details(self, ticket_id: str) -> Ticket | None:
        """Get ticket with all relations loaded."""
        stmt = select(Ticket).where(Ticket.id == ticket_id).options(
            selectinload(Ticket.user),
            selectinload(Ticket.ticket_category),
            selectinload(Ticket.assigned_admin),
            selectinload(Ticket.closed_by_user),
            selectinload(Ticket.messages).selectinload(TicketMessage.user),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_open_tickets(self, category_id: str | None = None) -> int:
        """Count open tickets."""
        stmt = select(func.count()).select_from(Ticket).where(
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_USER])
        )
        if category_id:
            stmt = stmt.where(Ticket.ticket_category_id == category_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_closed_tickets(self) -> int:
        """Count closed tickets."""
        return await self.count(status=TicketStatus.CLOSED)

    async def update_status(self, ticket_id: str, status: TicketStatus) -> Ticket | None:
        """Update ticket status."""
        from datetime import datetime, timezone
        updates = {"status": status}
        if status == TicketStatus.CLOSED:
            updates["closed_at"] = datetime.now(timezone.utc)
        return await self.update(ticket_id, **updates)

    async def assign_admin(self, ticket_id: str, admin_id: str) -> Ticket | None:
        """Assign ticket to admin."""
        return await self.update(ticket_id, assigned_admin_id=admin_id, status=TicketStatus.IN_PROGRESS)

    async def add_message(
        self,
        ticket_id: str,
        user_id: str,
        message: str,
        is_admin: bool = False,
        is_system: bool = False,
        attachment_url: str | None = None,
    ) -> "TicketMessage":
        """Add message to ticket."""
        from bot.models.ticket import TicketMessage
        msg = TicketMessage(
            ticket_id=ticket_id,
            user_id=user_id,
            message=message,
            is_admin=is_admin,
            is_system=is_system,
            attachment_url=attachment_url,
        )
        self.session.add(msg)

        # Update ticket status if user replies
        if not is_admin:
            await self.update(ticket_id, status=TicketStatus.WAITING_USER)
        elif is_admin:
            await self.update(ticket_id, status=TicketStatus.IN_PROGRESS)

        await self.session.flush()
        await self.session.refresh(msg)
        return msg

    async def search_tickets(
        self,
        query: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[Ticket]:
        """Search tickets by subject or user info."""
        stmt = select(Ticket).where(
            Ticket.subject.ilike(f"%{query}%")
        ).options(
            selectinload(Ticket.user),
            selectinload(Ticket.ticket_category),
        ).order_by(desc(Ticket.created_at)).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_for_admin(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: TicketStatus | None = None,
        category_id: str | None = None,
    ) -> Sequence[Ticket]:
        """Get all tickets for admin with filters."""
        stmt = select(Ticket).options(
            selectinload(Ticket.user),
            selectinload(Ticket.ticket_category),
        ).order_by(desc(Ticket.created_at))
        if status:
            stmt = stmt.where(Ticket.status == status)
        if category_id:
            stmt = stmt.where(Ticket.ticket_category_id == category_id)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_for_admin(
        self,
        status: TicketStatus | None = None,
        category_id: str | None = None,
    ) -> int:
        """Count tickets for admin with filters."""
        stmt = select(func.count()).select_from(Ticket)
        if status:
            stmt = stmt.where(Ticket.status == status)
        if category_id:
            stmt = stmt.where(Ticket.ticket_category_id == category_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()