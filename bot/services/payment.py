"""Payment service."""

from typing import Sequence

from bot.models.payment import Payment, PaymentStatus, PaymentMethod
from bot.models.order import OrderStatus
from bot.models.custom import CustomRegistration
from bot.services.base import BaseService
from bot.database.uow import UnitOfWork


def os_transitionable(order) -> bool:
    """True if the order can still be driven toward APPROVED.

    NOTE: this helper used to sit *inside* the class body, which dedented every
    method defined after it out of the class — PaymentService silently lost
    reject_payment/get_pending_payments/get_all_for_admin/... and the whole
    admin payment section raised AttributeError at runtime.
    """
    from bot.models.order import OrderStatus

    return order.status in (
        OrderStatus.WAITING_PAYMENT,
        OrderStatus.PAYMENT_UPLOADED,
        OrderStatus.PAYMENT_REVIEWING,
    )


class PaymentService(BaseService):
    """Payment service for payment management."""

    def __init__(self, uow: UnitOfWork) -> None:
        super().__init__(uow)

    async def create_payment(
        self,
        user_id: str,
        amount: int,
        method: PaymentMethod = PaymentMethod.CARD,
        order_id: str | None = None,
        custom_registration_id: str | None = None,
        receipt_url: str | None = None,
        card_number: str | None = None,
        card_holder: str | None = None,
        bank_name: str | None = None,
    ) -> Payment:
        """Create a new payment."""
        payment = await self.uow.payments.create(
            user_id=user_id,
            amount=amount,
            method=method,
            status=PaymentStatus.PENDING,
            order_id=order_id,
            custom_registration_id=custom_registration_id,
            receipt_url=receipt_url,
            card_number=card_number,
            card_holder=card_holder,
            bank_name=bank_name,
        )
        await self.uow.flush()
        return payment

    async def get_payment(self, payment_id: str) -> Payment | None:
        return await self.uow.payments.get_payment_with_details(payment_id)

    async def get_user_payments(
        self,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        status: PaymentStatus | None = None,
    ) -> Sequence[Payment]:
        return await self.uow.payments.get_by_user(user_id, offset=offset, limit=limit, status=status)

    async def approve_payment(self, payment_id: str, admin_id: str) -> Payment | None:
        """Approve payment, mark linked order paid and custom registration confirmed."""
        payment = await self.uow.payments.get_payment_with_details(payment_id)
        if not payment:
            return None
        if payment.status != PaymentStatus.PENDING:
            raise ValueError("پرداخت قبلاً بررسی شده است")

        payment = await self.uow.payments.approve_payment(payment_id, admin_id)

        # Advance the linked order to APPROVED via the order service
        # (records status events + timestamps + admin attribution + stock).
        from bot.services.order import OrderService
        if payment.order_id:
            order = await self.uow.orders.get_with_items(payment.order_id)
            admin = await self.uow.users.get(admin_id)
            if order and admin:
                os = OrderService(self.uow)
                # Only drive the order if it is not already past approval.
                from bot.models.order import OrderStatus
                if os_transitionable(order):
                    await os.approve_payment(order, admin)

        # Mark linked custom registration as confirmed
        if payment.custom_registration_id:
            reg = await self.uow.custom_registrations.get(payment.custom_registration_id)
            if reg:
                await self.uow.custom_registrations.update_registration_status(
                    reg.id, "confirmed", admin_id=admin_id
                )

        await self.uow.flush()
        return payment

    async def reject_payment(
        self, payment_id: str, admin_id: str, reason: str = ""
    ) -> Payment | None:
        """Reject payment."""
        payment = await self.uow.payments.get(payment_id)
        if not payment:
            return None
        if payment.status != PaymentStatus.PENDING:
            raise ValueError("پرداخت قبلاً بررسی شده است")

        payment = await self.uow.payments.reject_payment(payment_id, admin_id, reason)

        # Cancel linked order if rejected
        if payment.order_id:
            order = await self.uow.orders.get(payment.order_id)
            if order and order.status in (OrderStatus.PENDING, OrderStatus.WAITING_PAYMENT,
                                          OrderStatus.PAYMENT_UPLOADED, OrderStatus.PAYMENT_REVIEWING):
                await self.uow.orders.transition(
                    order, OrderStatus.CANCELLED, changed_by_id=admin_id, note="رد پرداخت"
                )

        # Mark custom registration as rejected
        if payment.custom_registration_id:
            reg = await self.uow.custom_registrations.get(payment.custom_registration_id)
            if reg:
                await self.uow.custom_registrations.update_registration_status(
                    reg.id, "rejected", admin_id=admin_id
                )

        await self.uow.flush()
        return payment

    async def request_receipt_again(self, payment_id: str, admin_id: str) -> Payment | None:
        """Request user to submit receipt again."""
        payment = await self.uow.payments.get(payment_id)
        if not payment:
            return None
        return await self.uow.payments.update(
            payment_id,
            status=PaymentStatus.PENDING,
            reject_reason=None,
            reviewed_by=None,
            reviewed_at=None,
        )

    async def get_pending_payments(self, offset: int = 0, limit: int = 50) -> Sequence[Payment]:
        return await self.uow.payments.get_pending_payments(offset=offset, limit=limit)

    async def get_all_for_admin(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: PaymentStatus | None = None,
        user_id: str | None = None,
        method: PaymentMethod | None = None,
    ) -> Sequence[Payment]:
        return await self.uow.payments.get_all_for_admin(
            offset=offset, limit=limit, status=status, user_id=user_id, method=method
        )

    async def count_for_admin(
        self,
        status: PaymentStatus | None = None,
        user_id: str | None = None,
        method: PaymentMethod | None = None,
    ) -> int:
        return await self.uow.payments.count_for_admin(
            status=status, user_id=user_id, method=method
        )

    async def get_stats(self) -> dict:
        return await self.uow.payments.get_payment_stats()

    async def update_receipt(self, payment_id: str, receipt_url: str) -> Payment | None:
        return await self.uow.payments.update(payment_id, receipt_url=receipt_url)

    async def attach_custom_registration(self, payment_id: str, registration_id: str) -> Payment | None:
        return await self.uow.payments.update(
            payment_id, custom_registration_id=registration_id
        )