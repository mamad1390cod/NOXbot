"""Wallet top-up service — atomic wallet operations with full audit trail."""

import logging
import secrets
from datetime import datetime, timezone
from typing import Sequence

from bot.database.uow import UnitOfWork
from bot.models.topup import (
    TopUpAmount,
    TopUpPaymentMethod,
    TopUpReceipt,
    TopUpRequest,
    TopUpStatus,
)
from bot.models.user import User
from bot.models.user_dashboard import TransactionType
from bot.services.base import BaseService
from bot.services.notification import NotificationService

logger = logging.getLogger(__name__)


def _generate_tracking_code() -> str:
    """Generate a unique tracking code like TOPUP-A3F9B2."""
    return f"TOPUP-{secrets.token_hex(3).upper()}"


class TopUpService(BaseService):
    """Service for wallet top-up operations."""

    def __init__(self, uow: UnitOfWork) -> None:
        super().__init__(uow)

    # ── Top-Up Amounts (admin-configurable) ────────────────────────────── #

    async def get_active_amounts(self) -> Sequence[TopUpAmount]:
        return await self.uow.topup_amounts.get_active_amounts()

    async def get_all_amounts(self) -> Sequence[TopUpAmount]:
        return await self.uow.topup_amounts.get_all_amounts()

    async def create_amount(
        self, amount: int, currency: str = "IRR", label: str | None = None
    ) -> TopUpAmount:
        # Get max display_order
        all_amounts = await self.uow.topup_amounts.get_all_amounts()
        max_order = max((a.display_order for a in all_amounts), default=0)
        obj = await self.uow.topup_amounts.create(
            amount=amount,
            currency=currency,
            label=label,
            is_active=True,
            display_order=max_order + 1,
        )
        await self.uow.flush()
        return obj

    async def update_amount(self, amount_id: str, **kwargs) -> TopUpAmount | None:
        obj = await self.uow.topup_amounts.update(amount_id, **kwargs)
        await self.uow.flush()
        return obj

    async def delete_amount(self, amount_id: str) -> bool:
        obj = await self.uow.topup_amounts.get(amount_id)
        if not obj:
            return False
        await self.uow.topup_amounts.delete(amount_id)
        await self.uow.flush()
        return True

    async def toggle_amount(self, amount_id: str) -> TopUpAmount | None:
        obj = await self.uow.topup_amounts.get(amount_id)
        if not obj:
            return None
        return await self.update_amount(amount_id, is_active=not obj.is_active)

    # ── Top-Up Request Lifecycle ───────────────────────────────────────── #

    async def create_request(
        self,
        user_id: str,
        amount: int,
        payment_method: TopUpPaymentMethod = TopUpPaymentMethod.CARD,
        currency: str = "IRR",
    ) -> TopUpRequest:
        """Create a new top-up request with a unique tracking code."""
        tracking_code = _generate_tracking_code()
        # Ensure uniqueness
        while await self.uow.topup_requests.get_by_tracking_code(tracking_code):
            tracking_code = _generate_tracking_code()

        req = await self.uow.topup_requests.create(
            user_id=user_id,
            amount=amount,
            currency=currency,
            payment_method=payment_method,
            status=TopUpStatus.WAITING_FOR_RECEIPT,
            tracking_code=tracking_code,
        )
        await self.uow.flush()
        return req

    async def get_request(self, request_id: str) -> TopUpRequest | None:
        return await self.uow.topup_requests.get_with_details(request_id)

    async def get_request_by_tracking(self, code: str) -> TopUpRequest | None:
        return await self.uow.topup_requests.get_by_tracking_code(code)

    async def submit_receipt(
        self, request_id: str, file_id: str, user_id: str, file_type: str = "photo"
    ) -> TopUpReceipt:
        """Submit a receipt for a top-up request."""
        req = await self.uow.topup_requests.get_with_details(request_id)
        if not req:
            raise ValueError("درخواست یافت نشد")

        # Count existing receipts for submission_number
        count = await self.uow.topup_receipts.count_for_request(request_id)

        receipt = await self.uow.topup_receipts.create(
            topup_request_id=request_id,
            file_id=file_id,
            file_type=file_type,
            submission_number=count + 1,
            submitted_by_id=user_id,
        )

        # Update status to UNDER_REVIEW
        await self.uow.topup_requests.update(
            request_id,
            status=TopUpStatus.UNDER_REVIEW,
            reject_reason=None,
        )
        await self.uow.flush()
        return receipt

    async def approve_request(
        self, request_id: str, admin_id: str
    ) -> TopUpRequest | None:
        """Approve a top-up request: credit wallet atomically."""
        req = await self.uow.topup_requests.get_with_details(request_id)
        if not req:
            return None
        if req.status == TopUpStatus.APPROVED:
            raise ValueError("این درخواست قبلاً تأیید شده است")
        if req.status == TopUpStatus.REJECTED:
            raise ValueError("این درخواست رد شده است")

        # Atomic: credit wallet + create transaction + update request status
        user = await self.uow.users.get(req.user_id)
        if not user:
            raise ValueError("کاربر یافت نشد")

        balance_before = user.wallet_balance or 0
        user.wallet_balance = balance_before + req.amount

        # Create ledger transaction
        txn = await self.uow.transactions.add(
            user_id=user.id,
            type_=TransactionType.TOPUP,
            amount=req.amount,
            balance_before=balance_before,
            balance_after=user.wallet_balance,
            ref_id=req.tracking_code,
            note=f"شارژ کیف پول — {req.payment_method.label}",
            admin_id=admin_id,
        )

        # Update request
        now = datetime.now(timezone.utc)
        await self.uow.topup_requests.update(
            request_id,
            status=TopUpStatus.APPROVED,
            reviewed_by_id=admin_id,
            reviewed_at=now,
            approved_at=now,
            transaction_id=txn.id,
        )

        await self.uow.flush()
        logger.info(
            "Top-up approved: tracking=%s user=%s amount=%d balance=%d->%d admin=%s",
            req.tracking_code, user.telegram_id, req.amount,
            balance_before, user.wallet_balance, admin_id,
        )

        # Re-fetch with details
        return await self.uow.topup_requests.get_with_details(request_id)

    async def reject_request(
        self, request_id: str, admin_id: str, reason: str = ""
    ) -> TopUpRequest | None:
        """Reject a top-up request: no wallet change."""
        req = await self.uow.topup_requests.get_with_details(request_id)
        if not req:
            return None
        if req.status == TopUpStatus.APPROVED:
            raise ValueError("این درخواست قبلاً تأیید شده و قابل رد نیست")

        now = datetime.now(timezone.utc)
        await self.uow.topup_requests.update(
            request_id,
            status=TopUpStatus.REJECTED,
            reviewed_by_id=admin_id,
            reviewed_at=now,
            reject_reason=reason or "بدون دلیل",
        )
        await self.uow.flush()

        logger.info(
            "Top-up rejected: tracking=%s reason=%s admin=%s",
            req.tracking_code, reason, admin_id,
        )
        return await self.uow.topup_requests.get_with_details(request_id)

    async def request_new_receipt(
        self, request_id: str, admin_id: str
    ) -> TopUpRequest | None:
        """Request user to resubmit receipt."""
        req = await self.uow.topup_requests.get_with_details(request_id)
        if not req:
            return None
        if req.is_finalized:
            raise ValueError("این درخواست قبلاً نهایی شده است")

        await self.uow.topup_requests.update(
            request_id,
            status=TopUpStatus.WAITING_FOR_NEW_RECEIPT,
            reviewed_by_id=admin_id,
            reviewed_at=datetime.now(timezone.utc),
            reject_reason=None,
        )
        await self.uow.flush()
        return await self.uow.topup_requests.get_with_details(request_id)

    # ── Admin: Manual Credit / Debit ───────────────────────────────────── #

    async def admin_credit(
        self,
        user_id: str,
        amount: int,
        admin_id: str,
        note: str = "",
    ) -> tuple[User, "Transaction"]:
        """Manually credit a user's wallet (admin operation)."""
        if amount <= 0:
            raise ValueError("مبلغ باید مثبت باشد")

        user = await self.uow.users.get(user_id)
        if not user:
            raise ValueError("کاربر یافت نشد")

        balance_before = user.wallet_balance or 0
        user.wallet_balance = balance_before + amount

        txn = await self.uow.transactions.add(
            user_id=user.id,
            type_=TransactionType.ADMIN_CREDIT,
            amount=amount,
            balance_before=balance_before,
            balance_after=user.wallet_balance,
            note=note or "شارژ دستی توسط ادمین",
            admin_id=admin_id,
        )
        await self.uow.flush()

        logger.info(
            "Admin credit: user=%s amount=%d balance=%d->%d admin=%s note=%s",
            user.telegram_id, amount, balance_before, user.wallet_balance, admin_id, note,
        )
        return user, txn

    async def admin_debit(
        self,
        user_id: str,
        amount: int,
        admin_id: str,
        note: str = "",
    ) -> tuple[User, "Transaction"]:
        """Manually debit a user's wallet (admin operation). Prevents negative balance."""
        if amount <= 0:
            raise ValueError("مبلغ باید مثبت باشد")

        user = await self.uow.users.get(user_id)
        if not user:
            raise ValueError("کاربر یافت نشد")

        balance_before = user.wallet_balance or 0
        if balance_before < amount:
            raise ValueError(
                f"موجودی کافی نیست. موجودی فعلی: {balance_before} تومان"
            )

        user.wallet_balance = balance_before - amount

        txn = await self.uow.transactions.add(
            user_id=user.id,
            type_=TransactionType.ADMIN_DEBIT,
            amount=-amount,
            balance_before=balance_before,
            balance_after=user.wallet_balance,
            note=note or "کسر دستی توسط ادمین",
            admin_id=admin_id,
        )
        await self.uow.flush()

        logger.info(
            "Admin debit: user=%s amount=%d balance=%d->%d admin=%s note=%s",
            user.telegram_id, amount, balance_before, user.wallet_balance, admin_id, note,
        )
        return user, txn

    # ── Admin: Listing & Search ────────────────────────────────────────── #

    async def get_pending_for_admin(
        self, *, offset: int = 0, limit: int = 50
    ) -> Sequence[TopUpRequest]:
        return await self.uow.topup_requests.get_pending_for_admin(
            offset=offset, limit=limit
        )

    async def get_all_for_admin(
        self,
        *,
        status: TopUpStatus | None = None,
        user_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[TopUpRequest]:
        return await self.uow.topup_requests.get_all_for_admin(
            status=status, user_id=user_id, offset=offset, limit=limit
        )

    async def search_by_tracking(self, code: str) -> TopUpRequest | None:
        return await self.uow.topup_requests.search_by_tracking(code)

    async def get_user_topups(
        self, user_id: str, *, limit: int = 20
    ) -> Sequence[TopUpRequest]:
        return await self.uow.topup_requests.get_by_user(user_id, limit=limit)

    async def get_stats(self) -> dict:
        return await self.uow.topup_requests.get_stats()

    # ── Receipts ───────────────────────────────────────────────────────── #

    async def get_receipts(self, request_id: str) -> Sequence[TopUpReceipt]:
        return await self.uow.topup_receipts.get_by_request(request_id)
