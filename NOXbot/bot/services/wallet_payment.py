"""Wallet payment service — atomic wallet deduction for purchases."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from bot.core.logging import log_wallet, log_payment, log_event
from bot.database.uow import UnitOfWork
from bot.models.payment import Payment, PaymentMethod, PaymentStatus
from bot.models.user import User
from bot.models.user_dashboard import TransactionType
from bot.services.base import BaseService
from bot.services.order import OrderService

logger = logging.getLogger(__name__)


class WalletPaymentError(Exception):
    """Base exception for wallet payment errors."""


class InsufficientBalanceError(WalletPaymentError):
    """Raised when wallet balance is insufficient."""

    def __init__(self, required: int, available: int):
        self.required = required
        self.available = available
        self.shortage = required - available
        super().__init__(
            f"Insufficient balance: required {required}, available {available}"
        )


class AlreadyPaidError(WalletPaymentError):
    """Raised when order is already paid via wallet."""


class WalletPaymentService(BaseService):
    """Service for wallet-based purchase payments."""

    def __init__(self, uow: UnitOfWork) -> None:
        super().__init__(uow)

    async def pay_order_with_wallet(
        self,
        user_id: str,
        order_id: str,
        amount: int,
    ) -> tuple[User, Payment]:
        """
        Atomically deduct from wallet and update/create payment record.

        Idempotency: 
        - Checks if order already has an approved wallet payment.
        - Checks if transaction with order_id as ref_id already exists.
        Atomicity: Uses SELECT FOR UPDATE to prevent race conditions.

        Returns: (updated_user, payment_record)
        Raises: InsufficientBalanceError, AlreadyPaidError
        """
        # Check if order already paid
        existing_payment = await self._get_approved_wallet_payment(order_id)
        if existing_payment:
            raise AlreadyPaidError(
                f"Order {order_id} already paid via wallet (payment_id={existing_payment.id})"
            )
        
        # Idempotency: Check if transaction already exists for this order
        existing_txn = await self._get_transaction_by_ref_id(order_id)
        if existing_txn:
            # Transaction exists but payment not approved? This shouldn't happen
            # but let's handle it gracefully
            user = await self.uow.users.get(user_id)
            payment = await self._get_payment_by_order_id(order_id)
            if payment:
                return user, payment

        # Check for existing PENDING payment and update it
        from sqlalchemy import select as sa_select
        pending_stmt = (
            sa_select(Payment)
            .where(
                Payment.order_id == order_id,
                Payment.status == PaymentStatus.PENDING,
            )
            .limit(1)
        )
        pending_result = await self.uow.session.execute(pending_stmt)
        pending_payment = pending_result.scalar_one_or_none()

        # Lock user row for atomic update
        stmt = (
            select(User)
            .where(User.id == user_id)
            .with_for_update(skip_locked=False)
        )
        result = await self.uow.session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User {user_id} not found")

        # Check balance
        current_balance = user.wallet_balance or 0
        if current_balance < amount:
            raise InsufficientBalanceError(required=amount, available=current_balance)

        # Atomic deduction
        balance_before = current_balance
        balance_after = current_balance - amount
        user.wallet_balance = balance_after

        # Update existing payment or create new one
        if pending_payment:
            pending_payment.method = PaymentMethod.BALANCE
            pending_payment.status = PaymentStatus.APPROVED
            pending_payment.reviewed_at = datetime.now(timezone.utc)
            pending_payment.notes = "Wallet payment"
            payment = pending_payment
        else:
            payment = Payment(
                user_id=user_id,
                order_id=order_id,
                amount=amount,
                method=PaymentMethod.BALANCE,
                status=PaymentStatus.APPROVED,
                reviewed_at=datetime.now(timezone.utc),
                notes="Wallet payment",
            )
            self.uow.session.add(payment)

        await self.uow.flush()

        # Create transaction record
        from bot.models.order import Order
        order = await self.uow.session.get(Order, order_id)
        order_number = order.order_number if order else order_id[:8]

        txn = await self.uow.transactions.add(
            user_id=user_id,
            type_=TransactionType.PURCHASE,
            amount=-amount,  # Negative for deduction
            balance_before=balance_before,
            balance_after=balance_after,
            ref_id=order_id,
            note=f"خرید سفارش {order_number}",
        )
        await self.uow.flush()

        logger.info(
            "Wallet payment: user=%s order=%s amount=%d balance=%d->%d txn=%s",
            user.telegram_id, order_number, amount,
            balance_before, balance_after, txn.id,
        )

        return user, payment

    async def _get_approved_wallet_payment(self, order_id: str) -> Payment | None:
        """Check if order already has an approved wallet payment."""
        stmt = (
            select(Payment)
            .where(
                Payment.order_id == order_id,
                Payment.method == PaymentMethod.BALANCE,
                Payment.status == PaymentStatus.APPROVED,
            )
            .limit(1)
        )
        result = await self.uow.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_payment_by_order_id(self, order_id: str) -> Payment | None:
        """Get payment record for an order."""
        stmt = (
            select(Payment)
            .where(Payment.order_id == order_id)
            .limit(1)
        )
        result = await self.uow.session.execute(stmt)
        return result.scalar_one_or_none()

    async def check_balance(self, user_id: str) -> int:
        """Get current wallet balance."""
        user = await self.uow.users.get(user_id)
        return user.wallet_balance if user else 0

    async def deduct_wallet(
        self,
        user_id: str,
        amount: int,
        ref_id: str,
        notes: str | None = None,
        transaction_type: TransactionType = TransactionType.SPEND,
    ) -> tuple[User, "Transaction"]:
        """
        Atomically deduct from wallet for non-order payments (e.g., custom registrations).
        
        Idempotency: If a transaction with the same ref_id already exists, return it.
        Atomicity: Uses SELECT FOR UPDATE to prevent race conditions.
        
        Returns: (updated_user, transaction_record)
        Raises: InsufficientBalanceError
        """
        log_wallet(
            'wallet_debit_started',
            user_id=user_id,
            amount=amount,
            operation_type=transaction_type.value,
            ref_id=ref_id,
        )
        
        # Idempotency check: if transaction with this ref_id already exists, return it
        existing_txn = await self._get_transaction_by_ref_id(ref_id)
        if existing_txn:
            user = await self.uow.users.get(user_id)
            log_wallet(
                'wallet_debit_duplicate',
                user_id=user_id,
                transaction_id=existing_txn.id,
                ref_id=ref_id,
            )
            return user, existing_txn
        
        # Lock user row for atomic update
        stmt = (
            select(User)
            .where(User.id == user_id)
            .with_for_update(skip_locked=False)
        )
        result = await self.uow.session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            log_wallet(
                'wallet_debit_failed',
                user_id=user_id,
                reason='user_not_found',
            )
            raise ValueError(f"User {user_id} not found")

        # Check balance
        current_balance = user.wallet_balance or 0
        if current_balance < amount:
            log_wallet(
                'wallet_insufficient_balance',
                user_id=user_id,
                amount=amount,
                balance_before=current_balance,
                shortage=amount - current_balance,
            )
            raise InsufficientBalanceError(required=amount, available=current_balance)

        # Atomic deduction
        balance_before = current_balance
        balance_after = current_balance - amount
        user.wallet_balance = balance_after
        await self.uow.flush()

        # Create transaction record
        txn = await self.uow.transactions.add(
            user_id=user_id,
            type_=transaction_type,
            amount=-amount,  # Negative for deduction
            balance_before=balance_before,
            balance_after=balance_after,
            ref_id=ref_id,
            note=notes or "کسر از کیف پول",
        )
        await self.uow.flush()

        log_wallet(
            'wallet_debit_completed',
            user_id=user_id,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            transaction_id=txn.id,
            operation_type=transaction_type.value,
            ref_id=ref_id,
        )

        return user, txn
    
    async def _get_transaction_by_ref_id(self, ref_id: str) -> "Transaction | None":
        """Check if a transaction with this ref_id already exists (for idempotency)."""
        from bot.models.user_dashboard import Transaction
        stmt = (
            select(Transaction)
            .where(Transaction.ref_id == ref_id)
            .limit(1)
        )
        result = await self.uow.session.execute(stmt)
        return result.scalar_one_or_none()
