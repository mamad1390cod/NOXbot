"""Top-up repositories — TopUpRequestRepository, TopUpAmountRepository, TopUpReceiptRepository."""

from typing import Sequence

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models.topup import TopUpAmount, TopUpReceipt, TopUpRequest, TopUpStatus
from bot.models.user import User
from bot.repositories.base import BaseRepository


class TopUpAmountRepository(BaseRepository[TopUpAmount]):
    """Repository for admin-configurable top-up amounts."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TopUpAmount)

    async def get_active_amounts(self) -> Sequence[TopUpAmount]:
        """Get active amounts ordered by display_order."""
        stmt = (
            select(TopUpAmount)
            .where(TopUpAmount.is_active == True)
            .order_by(asc(TopUpAmount.display_order))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_amounts(self) -> Sequence[TopUpAmount]:
        """Get all amounts (including inactive) ordered by display_order."""
        stmt = select(TopUpAmount).order_by(asc(TopUpAmount.display_order))
        result = await self.session.execute(stmt)
        return result.scalars().all()


class TopUpReceiptRepository(BaseRepository[TopUpReceipt]):
    """Repository for top-up receipts."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TopUpReceipt)

    async def get_by_request(self, request_id: str) -> Sequence[TopUpReceipt]:
        """Get all receipts for a request, ordered by submission."""
        stmt = (
            select(TopUpReceipt)
            .where(TopUpReceipt.topup_request_id == request_id)
            .order_by(asc(TopUpReceipt.submission_number))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_for_request(self, request_id: str) -> int:
        """Count receipts for a request."""
        stmt = (
            select(func.count())
            .select_from(TopUpReceipt)
            .where(TopUpReceipt.topup_request_id == request_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()


class TopUpRequestRepository(BaseRepository[TopUpRequest]):
    """Repository for top-up requests."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TopUpRequest)

    async def get_by_tracking_code(self, code: str) -> TopUpRequest | None:
        """Get a request by its tracking code."""
        stmt = (
            select(TopUpRequest)
            .where(TopUpRequest.tracking_code == code)
            .options(
                selectinload(TopUpRequest.user),
                selectinload(TopUpRequest.reviewed_by),
                selectinload(TopUpRequest.receipts),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_details(self, request_id: str) -> TopUpRequest | None:
        """Get a request with all relationships loaded."""
        stmt = (
            select(TopUpRequest)
            .where(TopUpRequest.id == request_id)
            .options(
                selectinload(TopUpRequest.user),
                selectinload(TopUpRequest.reviewed_by),
                selectinload(TopUpRequest.receipts),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_for_admin(
        self, *, offset: int = 0, limit: int = 50
    ) -> Sequence[TopUpRequest]:
        """Get requests pending admin review."""
        stmt = (
            select(TopUpRequest)
            .where(
                TopUpRequest.status.in_([
                    TopUpStatus.UNDER_REVIEW,
                    TopUpStatus.WAITING_FOR_NEW_RECEIPT,
                ])
            )
            .options(
                selectinload(TopUpRequest.user),
                selectinload(TopUpRequest.receipts),
            )
            .order_by(asc(TopUpRequest.created_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_for_admin(
        self,
        *,
        status: TopUpStatus | None = None,
        user_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[TopUpRequest]:
        """Get all requests for admin panel with optional filters."""
        stmt = (
            select(TopUpRequest)
            .options(
                selectinload(TopUpRequest.user),
                selectinload(TopUpRequest.receipts),
            )
            .order_by(desc(TopUpRequest.created_at))
        )
        if status:
            stmt = stmt.where(TopUpRequest.status == status)
        if user_id:
            stmt = stmt.where(TopUpRequest.user_id == user_id)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_status(self, status: TopUpStatus) -> int:
        """Count requests by status."""
        return await self.count(status=status)

    async def get_by_user(
        self, user_id: str, *, limit: int = 20
    ) -> Sequence[TopUpRequest]:
        """Get top-up requests for a user."""
        stmt = (
            select(TopUpRequest)
            .where(TopUpRequest.user_id == user_id)
            .options(selectinload(TopUpRequest.receipts))
            .order_by(desc(TopUpRequest.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def search_by_tracking(self, code: str) -> TopUpRequest | None:
        """Search by tracking code (partial match)."""
        stmt = (
            select(TopUpRequest)
            .where(TopUpRequest.tracking_code.ilike(f"%{code}%"))
            .options(
                selectinload(TopUpRequest.user),
                selectinload(TopUpRequest.receipts),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_stats(self) -> dict:
        """Get top-up statistics."""
        pending = await self.count_by_status(TopUpStatus.UNDER_REVIEW)
        waiting_receipt = await self.count_by_status(TopUpStatus.WAITING_FOR_NEW_RECEIPT)
        approved = await self.count_by_status(TopUpStatus.APPROVED)
        rejected = await self.count_by_status(TopUpStatus.REJECTED)

        # Total approved amount
        stmt = select(func.sum(TopUpRequest.amount)).where(
            TopUpRequest.status == TopUpStatus.APPROVED
        )
        result = await self.session.execute(stmt)
        total_approved = result.scalar_one() or 0

        return {
            "pending": pending,
            "waiting_receipt": waiting_receipt,
            "approved": approved,
            "rejected": rejected,
            "total_approved_amount": total_approved,
        }
