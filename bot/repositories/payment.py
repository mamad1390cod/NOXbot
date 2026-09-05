"""Payment repository."""

from typing import Sequence

from sqlalchemy import BigInteger, Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models.payment import Payment, PaymentStatus, PaymentMethod
from bot.models.order import Order, OrderItem
from bot.models.custom import CustomRegistration
from bot.repositories.base import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    """Payment repository with specialized queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Payment)

    async def get_by_user(
        self,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        status: PaymentStatus | None = None,
    ) -> Sequence[Payment]:
        """Get payments by user."""
        stmt = select(Payment).where(Payment.user_id == user_id).options(
            selectinload(Payment.order),
            selectinload(Payment.custom_registration),
        )
        if status:
            stmt = stmt.where(Payment.status == status)
        stmt = stmt.order_by(desc(Payment.created_at)).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_pending_payments(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[Payment]:
        """Get pending payments for admin."""
        stmt = select(Payment).where(Payment.status == PaymentStatus.PENDING).options(
            selectinload(Payment.user),
            selectinload(Payment.order).selectinload(Order.items),
            selectinload(Payment.custom_registration).selectinload(CustomRegistration.custom),
        ).order_by(Payment.created_at).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_payment_with_details(self, payment_id: str) -> Payment | None:
        """Get payment with all relations loaded."""
        stmt = select(Payment).where(Payment.id == payment_id).options(
            selectinload(Payment.user),
            selectinload(Payment.order).selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Payment.order).selectinload(Order.items).selectinload(OrderItem.config_product),
            selectinload(Payment.custom_registration).selectinload(CustomRegistration.custom),
            selectinload(Payment.reviewed_by_user),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_pending_payments(self) -> int:
        """Count pending payments."""
        return await self.count(status=PaymentStatus.PENDING)

    async def count_by_status(self, status: PaymentStatus) -> int:
        """Count payments by status."""
        return await self.count(status=status)

    async def approve_payment(self, payment_id: str, admin_id: str) -> Payment | None:
        """Approve payment."""
        from datetime import datetime, timezone
        return await self.update(
            payment_id,
            status=PaymentStatus.APPROVED,
            reviewed_by=admin_id,
            reviewed_at=datetime.now(timezone.utc),
        )

    async def reject_payment(self, payment_id: str, admin_id: str, reason: str) -> Payment | None:
        """Reject payment."""
        from datetime import datetime, timezone
        return await self.update(
            payment_id,
            status=PaymentStatus.REJECTED,
            reviewed_by=admin_id,
            reviewed_at=datetime.now(timezone.utc),
            reject_reason=reason,
        )

    async def get_all_for_admin(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: PaymentStatus | None = None,
        user_id: str | None = None,
        method: PaymentMethod | None = None,
    ) -> Sequence[Payment]:
        """Get all payments for admin with filters."""
        stmt = select(Payment).options(
            selectinload(Payment.user),
            selectinload(Payment.order),
            selectinload(Payment.custom_registration),
        ).order_by(desc(Payment.created_at))
        if status:
            stmt = stmt.where(Payment.status == status)
        if user_id:
            stmt = stmt.where(Payment.user_id == user_id)
        if method:
            stmt = stmt.where(Payment.method == method)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_for_admin(
        self,
        status: PaymentStatus | None = None,
        user_id: str | None = None,
        method: PaymentMethod | None = None,
    ) -> int:
        """Count payments for admin with filters."""
        stmt = select(func.count()).select_from(Payment)
        if status:
            stmt = stmt.where(Payment.status == status)
        if user_id:
            stmt = stmt.where(Payment.user_id == user_id)
        if method:
            stmt = stmt.where(Payment.method == method)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_payment_stats(self) -> dict:
        """Get payment statistics."""
        # Pending
        pending = await self.count_by_status(PaymentStatus.PENDING)
        # Approved
        approved = await self.count_by_status(PaymentStatus.APPROVED)
        # Rejected
        rejected = await self.count_by_status(PaymentStatus.REJECTED)

        # Total approved amount
        stmt = select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.APPROVED)
        result = await self.session.execute(stmt)
        total_approved = result.scalar_one() or 0

        return {
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "total_approved_amount": total_approved,
        }