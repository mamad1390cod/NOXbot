"""Ticket service."""

from typing import Sequence

from bot.models.ticket import Ticket, TicketCategory, TicketStatus, TicketPriority, TicketMessage
from bot.services.base import BaseService
from bot.database.uow import UnitOfWork


class TicketService(BaseService):
    """Ticket service for support ticket management."""

    def __init__(self, uow: UnitOfWork) -> None:
        super().__init__(uow)

    # Ticket Category methods
    async def get_active_categories(self) -> Sequence[TicketCategory]:
        """Get active ticket categories for users."""
        return await self.uow.ticket_categories.get_active_categories()

    async def get_category(self, category_id: str) -> TicketCategory | None:
        """Get ticket category by ID."""
        return await self.uow.ticket_categories.get(category_id)

    async def create_category(
        self,
        name: str,
        name_en: str | None = None,
        description: str | None = None,
        emoji: str | None = None,
        color: str | None = None,
        sort_order: int = 0,
    ) -> TicketCategory:
        """Create new ticket category."""
        category = await self.uow.ticket_categories.create(
            name=name,
            name_en=name_en,
            description=description,
            emoji=emoji,
            color=color,
            sort_order=sort_order,
            is_active=True,
        )
        await self.uow.flush()
        return category

    async def update_category(self, category_id: str, **kwargs) -> TicketCategory | None:
        """Update ticket category."""
        return await self.uow.ticket_categories.update(category_id, **kwargs)

    async def delete_category(self, category_id: str) -> bool:
        """Delete ticket category."""
        return await self.uow.ticket_categories.delete(category_id)

    async def toggle_category_active(self, category_id: str) -> TicketCategory | None:
        """Toggle category active status."""
        category = await self.uow.ticket_categories.get(category_id)
        if category:
            return await self.uow.ticket_categories.update(category_id, is_active=not category.is_active)
        return None

    async def get_all_categories_for_admin(
        self,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[TicketCategory]:
        """Get all categories for admin."""
        return await self.uow.ticket_categories.get_all_for_admin(offset=offset, limit=limit)

    # Ticket methods
    async def create_ticket(
        self,
        user_id: str,
        category_id: str,
        subject: str,
        message: str,
        priority: TicketPriority = TicketPriority.NORMAL,
    ) -> Ticket:
        """Create new ticket."""
        ticket = await self.uow.tickets.create(
            user_id=user_id,
            ticket_category_id=category_id,
            subject=subject,
            message=message,
            priority=priority,
            status=TicketStatus.OPEN,
        )
        await self.uow.flush()

        # Add initial message
        await self.uow.tickets.add_message(
            ticket_id=ticket.id,
            user_id=user_id,
            message=message,
            is_admin=False,
        )

        return ticket

    async def get_ticket(self, ticket_id: str) -> Ticket | None:
        """Get ticket with details."""
        return await self.uow.tickets.get_ticket_with_details(ticket_id)

    async def get_user_tickets(
        self,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        status: TicketStatus | None = None,
    ) -> Sequence[Ticket]:
        """Get user's tickets."""
        return await self.uow.tickets.get_by_user(user_id, offset=offset, limit=limit, status=status)

    async def get_open_tickets(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        category_id: str | None = None,
    ) -> Sequence[Ticket]:
        """Get open tickets for admin."""
        return await self.uow.tickets.get_open_tickets(offset=offset, limit=limit, category_id=category_id)

    async def get_closed_tickets(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[Ticket]:
        """Get closed tickets for admin."""
        return await self.uow.tickets.get_closed_tickets(offset=offset, limit=limit)

    async def count_open_tickets(self, category_id: str | None = None) -> int:
        """Count open tickets."""
        return await self.uow.tickets.count_open_tickets(category_id)

    async def count_closed_tickets(self) -> int:
        """Count closed tickets."""
        return await self.uow.tickets.count_closed_tickets()

    async def reply_to_ticket(
        self,
        ticket_id: str,
        user_id: str,
        message: str,
        is_admin: bool = False,
        attachment_url: str | None = None,
    ) -> TicketMessage:
        """Reply to ticket."""
        return await self.uow.tickets.add_message(
            ticket_id=ticket_id,
            user_id=user_id,
            message=message,
            is_admin=is_admin,
            attachment_url=attachment_url,
        )

    async def update_ticket_status(self, ticket_id: str, status: TicketStatus) -> Ticket | None:
        """Update ticket status."""
        return await self.uow.tickets.update_status(ticket_id, status)

    async def close_ticket(self, ticket_id: str, admin_id: str, reason: str | None = None) -> Ticket | None:
        """Close ticket."""
        return await self.uow.tickets.update(
            ticket_id,
            status=TicketStatus.CLOSED,
            closed_by=admin_id,
            close_reason=reason,
        )

    async def assign_ticket(self, ticket_id: str, admin_id: str) -> Ticket | None:
        """Assign ticket to admin."""
        return await self.uow.tickets.assign_admin(ticket_id, admin_id)

    async def search_tickets(
        self,
        query: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[Ticket]:
        """Search tickets."""
        return await self.uow.tickets.search_tickets(query, offset=offset, limit=limit)

    async def get_all_for_admin(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: TicketStatus | None = None,
        category_id: str | None = None,
    ) -> Sequence[Ticket]:
        """Get all tickets for admin."""
        return await self.uow.tickets.get_all_for_admin(
            offset=offset,
            limit=limit,
            status=status,
            category_id=category_id,
        )

    async def count_for_admin(
        self,
        status: TicketStatus | None = None,
        category_id: str | None = None,
    ) -> int:
        """Count tickets for admin."""
        return await self.uow.tickets.count_for_admin(status=status, category_id=category_id)

    async def delete_ticket(self, ticket_id: str) -> bool:
        """Delete ticket (admin only)."""
        return await self.uow.tickets.delete(ticket_id)