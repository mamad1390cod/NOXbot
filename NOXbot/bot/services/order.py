"""Order service — full lifecycle management.

Each lifecycle method:
- validates the transition (state-machine rules),
- applies the new status + timestamps + admin attribution via the repository,
- records a status event,
- notifies the customer and (where relevant) the admins.

NotificationService is injected by the caller (handlers) so this service
stays decoupled from aiogram.
"""

from datetime import datetime, timezone
from typing import Sequence

from bot.models.order import Order, OrderItem, OrderStatus, PaymentMethod
from bot.models.payment import Payment, PaymentMethod as PaymentMethodEnum, PaymentStatus
from bot.models.user import User
from bot.services.base import BaseService
from bot.database.uow import UnitOfWork

# Legal transitions per status.
TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.WAITING_PAYMENT, OrderStatus.CANCELLED},
    OrderStatus.WAITING_PAYMENT: {
        OrderStatus.PAYMENT_UPLOADED, OrderStatus.CANCELLED, OrderStatus.REJECTED,
    },
    OrderStatus.PAYMENT_UPLOADED: {
        OrderStatus.PAYMENT_REVIEWING, OrderStatus.CANCELLED, OrderStatus.REJECTED,
    },
    OrderStatus.PAYMENT_REVIEWING: {
        OrderStatus.APPROVED, OrderStatus.REJECTED, OrderStatus.CANCELLED,
    },
    OrderStatus.APPROVED: {OrderStatus.PREPARING, OrderStatus.REFUNDED},
    OrderStatus.PREPARING: {OrderStatus.DELIVERED, OrderStatus.REFUNDED},
    OrderStatus.DELIVERED: {OrderStatus.COMPLETED, OrderStatus.REFUNDED},
    OrderStatus.COMPLETED: {OrderStatus.REFUNDED},
    OrderStatus.CANCELLED: set(),
    OrderStatus.REFUNDED: set(),
    OrderStatus.REJECTED: set(),
}

# Status changes that should notify admins too.
ADMIN_ALERT_STATUSES = {
    OrderStatus.PAYMENT_UPLOADED,
    OrderStatus.REJECTED,
    OrderStatus.CANCELLED,
    OrderStatus.REFUNDED,
}


class OrderStatusError(Exception):
    """Raised when an illegal status transition is attempted."""


class OrderService(BaseService):
    """Order service for full lifecycle management."""

    def __init__(self, uow: UnitOfWork, notifier=None) -> None:
        super().__init__(uow)
        self.notifier = notifier  # NotificationService or None (tests)

    # --- Query ------------------------------------------------------------- #
    async def get_order(self, order_id: str) -> Order | None:
        return await self.uow.orders.get_with_items(order_id)

    async def get_order_by_number(self, order_number: str) -> Order | None:
        return await self.uow.orders.get_by_number(order_number)

    async def get_user_orders(
        self,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        status: OrderStatus | None = None,
    ) -> Sequence[Order]:
        return await self.uow.orders.get_by_user(user_id, offset=offset, limit=limit, status=status)

    async def count_user_orders(self, user_id: str, status: OrderStatus | None = None) -> int:
        return await self.uow.orders.count_by_user(user_id, status)

    # --- Create ------------------------------------------------------------ #
    async def create_order_from_cart(
        self,
        user_id: str,
        payment_method: PaymentMethod | None = None,
        coupon_code: str | None = None,
        discount_amount: int = 0,
        customer_notes: str | None = None,
    ) -> Order:
        """Create an order from the user's cart."""
        cart = await self.uow.carts.get_by_user_id(user_id)
        if cart is None:
            raise ValueError("سبد خرید خالی است")
        cart_items = await self.uow.carts.get_cart_items(cart.id)
        if not cart_items:
            raise ValueError("سبد خرید خالی است")

        items = []
        for item in cart_items:
            if item.product_id:
                product = item.product
                if not product:
                    continue
                items.append({
                    "product_id": product.id,
                    "config_product_id": None,
                    "quantity": item.quantity,
                    "unit_price": product.discounted_price,
                    "total_price": product.discounted_price * item.quantity,
                    "title": product.title,
                    "product_type": "product",
                })
            elif item.config_product_id:
                config = item.config_product
                if not config:
                    continue
                items.append({
                    "product_id": None,
                    "config_product_id": config.id,
                    "quantity": item.quantity,
                    "unit_price": config.price,
                    "total_price": config.price * item.quantity,
                    "title": config.title,
                    "product_type": "config",
                })

        if not items:
            raise ValueError("سبد خرید خالی است")

        order_number = await self.uow.orders.next_order_number()
        order = await self.uow.orders.create_order(
            user_id=user_id,
            items=items,
            order_number=order_number,
            payment_method=payment_method,
            coupon_code=coupon_code,
            discount_amount=discount_amount,
            customer_notes=customer_notes,
        )

        # Create the pending payment record.
        payment = Payment(
            user_id=user_id,
            order_id=order.id,
            amount=order.final_amount,
            method=PaymentMethodEnum(payment_method.value) if payment_method else PaymentMethodEnum.CARD,
            status=PaymentStatus.PENDING,
        )
        self.uow.session.add(payment)

        # Clear cart.
        await self.uow.carts.clear_cart(cart.id)

        await self.uow.flush()
        return order

    # --- Lifecycle transitions --------------------------------------------- #
    async def transition_to(
        self,
        order: Order,
        to_status: OrderStatus,
        admin: User | None = None,
        note: str | None = None,
        is_system: bool = False,
    ) -> Order:
        """Apply a status transition with validation, timestamps, events and
        notifications. Returns the updated order."""
        allowed = TRANSITIONS.get(order.status, set())
        if to_status not in allowed:
            raise OrderStatusError(
                f"انتقال غیرمجاز از {order.status.value} به {to_status.value}"
            )

        admin_id = admin.id if admin else None
        await self.uow.orders.transition(
            order,
            to_status,
            changed_by_id=admin_id,
            note=note,
            is_system=is_system,
        )
        await self.uow.flush()

        # Re-fetch with all relations (payments/items) eagerly loaded so the
        # caller's subsequent reads do not trigger lazy IO in an async context.
        updated = await self.uow.orders.get_with_items(order.id)

        # Customer notification (if notifier provided).
        if self.notifier and updated and updated.user:
            await self.notifier.notify_user(
                updated.user.telegram_id,
                status_message(updated, to_status),
            )

        return updated

    async def submit_payment(
        self,
        order: Order,
        receipt_file_id: str,
        is_system: bool = False,
    ) -> Order:
        """User uploads a payment receipt → PAYMENT_UPLOADED."""
        order = await self.transition_to(
            order, OrderStatus.PAYMENT_UPLOADED, is_system=is_system,
            note="رسید پرداخت ارسال شد",
        )
        # Update the payment record.
        payment = self._get_pending_payment(order)
        if payment:
            payment.receipt_url = receipt_file_id
            payment.status = PaymentStatus.PENDING
            await self.uow.flush()
        return order

    async def begin_review(self, order: Order, admin: User | None = None) -> Order:
        """Admin begins reviewing → PAYMENT_REVIEWING."""
        return await self.transition_to(
            order, OrderStatus.PAYMENT_REVIEWING, admin=admin,
            note="بررسی رسید توسط ادمین",
        )

    async def approve_payment(
        self,
        order: Order,
        admin: User,
        note: str | None = None,
    ) -> Order:
        """Approve the payment → APPROVED.

        Advances the order through the legal payment path from its current
        state up to APPROVED (e.g. from WAITING_PAYMENT: uploaded → reviewing
        → approved), so external callers (payment handler) can approve the
        order regardless of how far the receipt flow progressed.
        """
        await self._advance_to(order, OrderStatus.APPROVED, admin=admin,
                               note=note or "پرداخت تایید شد")
        order = await self.uow.orders.get_with_items(order.id)
        # Mark payment approved and decrement stock (once).
        payment = self._get_pending_payment(order)
        if payment:
            payment.status = PaymentStatus.APPROVED
        await self.uow.orders.decrement_items_stock(order)
        await self.uow.flush()
        return order

    async def _advance_to(
        self,
        order: Order,
        target: OrderStatus,
        admin: User | None = None,
        note: str | None = None,
    ) -> Order:
        """Walk the order forward along the standard lifecycle until it reaches
        ``target`` — only ever using legal single-step transitions."""
        guard = 0
        while order.status != target and guard < 10:
            guard += 1
            nxt = self._next_step(order.status, target)
            if nxt is None:
                break
            order = await self.transition_to(order, nxt, admin=admin, note=note)
        return order

    @staticmethod
    def _next_step(current: OrderStatus, target: OrderStatus) -> OrderStatus | None:
        """Return the immediate next status on the path from ``current`` to
        ``target`` following the linear lifecycle, without skipping a state."""
        chain = [
            OrderStatus.PENDING,
            OrderStatus.WAITING_PAYMENT,
            OrderStatus.PAYMENT_UPLOADED,
            OrderStatus.PAYMENT_REVIEWING,
            OrderStatus.APPROVED,
            OrderStatus.PREPARING,
            OrderStatus.DELIVERED,
            OrderStatus.COMPLETED,
        ]
        if current not in chain or target not in chain:
            return None
        if chain.index(target) <= chain.index(current):
            return None
        nxt = chain[chain.index(current) + 1]
        if nxt in TRANSITIONS.get(current, set()):
            return nxt
        return None

    async def start_preparing(self, order: Order, admin: User) -> Order:
        return await self.transition_to(
            order, OrderStatus.PREPARING, admin=admin, note="آماده‌سازی محصول",
        )

    async def deliver_order(
        self,
        order: Order,
        admin: User,
        delivered_data: dict | None = None,
        note: str | None = None,
    ) -> Order:
        """Mark as delivered and store delivered account data on items."""
        order = await self.uow.orders.get_with_items(order.id)
        if not order:
            raise OrderStatusError("سفارش یافت نشد")
        if delivered_data:
            for item in order.items:
                if item.product_type == "account" and item.product_id in delivered_data:
                    item.delivered_data = delivered_data[item.product_id]
        return await self.transition_to(
            order, OrderStatus.DELIVERED, admin=admin, note=note or "محصول ارسال شد",
        )

    async def complete_order(self, order: Order, admin: User | None = None) -> Order:
        return await self.transition_to(
            order, OrderStatus.COMPLETED, admin=admin, note="سفارش تکمیل شد",
        )

    async def cancel_order(
        self,
        order: Order,
        admin: User | None = None,
        reason: str | None = None,
    ) -> Order:
        """Cancel an order (before payment). Restores stock and cancels the
        pending payment."""
        if not order.can_cancel:
            raise OrderStatusError("این سفارش قابل لغو نیست")

        order = await self.transition_to(
            order, OrderStatus.CANCELLED, admin=admin,
            note=reason or "لغو توسط کاربر",
        )
        payment = self._get_pending_payment(order)
        if payment and payment.status == PaymentStatus.PENDING:
            payment.status = PaymentStatus.CANCELLED
        await self.uow.orders.restore_items_stock(order)
        await self.uow.flush()
        return order

    async def reject_order(
        self,
        order: Order,
        admin: User,
        reason: str,
    ) -> Order:
        """Reject the payment/order → REJECTED."""
        order = await self.transition_to(
            order, OrderStatus.REJECTED, admin=admin, note=reason,
        )
        payment = self._get_pending_payment(order)
        if payment and payment.status == PaymentStatus.PENDING:
            payment.status = PaymentStatus.REJECTED
        await self.uow.flush()
        return order

    async def refund_order(
        self,
        order: Order,
        admin: User,
        reason: str | None = None,
    ) -> Order:
        """Refund a paid order → REFUNDED (restores stock)."""
        if not order.is_paid:
            raise OrderStatusError("فقط سفارش پرداخت‌شده قابل بازگشت وجه است")
        order = await self.transition_to(
            order, OrderStatus.REFUNDED, admin=admin, note=reason or "بازگشت وجه",
        )
        payment = self._get_pending_payment(order)
        if payment and payment.status == PaymentStatus.APPROVED:
            payment.status = PaymentStatus.REJECTED  # no refund ledger yet
        await self.uow.orders.restore_items_stock(order)
        await self.uow.flush()
        return order

    # --- Notes / delivery -------------------------------------------------- #
    async def set_internal_note(self, order_id: str, note: str, admin: User | None = None) -> Order | None:
        order = await self.uow.orders.get(order_id)
        if not order:
            return None
        return await self.uow.orders.update(order_id, internal_notes=note)

    async def set_customer_notes(self, order_id: str, note: str) -> Order | None:
        order = await self.uow.orders.get(order_id)
        if not order:
            return None
        return await self.uow.orders.update(order_id, customer_notes=note)

    async def set_eta(self, order_id: str, eta: datetime) -> Order | None:
        return await self.uow.orders.update(order_id, estimated_delivery_at=eta)

    async def link_ticket(self, order_id: str, ticket_id: str) -> Order | None:
        return await self.uow.orders.update(order_id, linked_ticket_id=ticket_id)

    async def unlink_ticket(self, order_id: str) -> Order | None:
        return await self.uow.orders.update(order_id, linked_ticket_id=None)

    # --- Helpers ----------------------------------------------------------- #
    def _get_pending_payment(self, order: Order) -> Payment | None:
        """Return the order's main payment (latest)."""
        if order.payments:
            return order.payments[-1]
        return None

    # --- Admin queries ----------------------------------------------------- #
    async def filter_orders(
        self,
        filters: dict,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[Order]:
        return await self.uow.orders.filter_orders(filters, offset=offset, limit=limit)

    async def count_filtered(self, filters: dict) -> int:
        return await self.uow.orders.count_filtered(filters)

    async def get_pending_orders(self, offset: int = 0, limit: int = 50) -> Sequence[Order]:
        return await self.uow.orders.get_pending_orders(offset=offset, limit=limit)

    async def get_all_for_admin(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: OrderStatus | None = None,
        user_id: str | None = None,
    ) -> Sequence[Order]:
        return await self.uow.orders.get_all_for_admin(
            offset=offset, limit=limit, status=status, user_id=user_id
        )

    async def count_for_admin(self, status: OrderStatus | None = None, user_id: str | None = None) -> int:
        return await self.uow.orders.count_for_admin(status=status, user_id=user_id)

    async def get_revenue_stats(self) -> dict:
        return await self.uow.orders.get_revenue_stats()

    async def get_order_details(self, order_id: str) -> dict | None:
        """Full detail bundle for admin/user views."""
        order = await self.uow.orders.get_with_items(order_id)
        if not order:
            return None
        user = await self.uow.users.get(order.user_id)
        payments = await self.uow.payments.get_by_user(order.user_id)
        order_payments = [p for p in payments if p.order_id == order.id]
        return {
            "order": order,
            "user": user,
            "payments": order_payments,
        }


def status_message(order: Order, status: OrderStatus) -> str:
    """Build a customer-facing status-change notification."""
    num = order.order_number or order.id[:8]
    messages = {
        OrderStatus.PENDING: f"⏳ سفارش <b>{num}</b> ثبت شد. در انتظار پرداخت.",
        OrderStatus.WAITING_PAYMENT: f"💳 سفارش <b>{num}</b> در انتظار پرداخت است.",
        OrderStatus.PAYMENT_UPLOADED: f"📤 رسید پرداخت سفارش <b>{num}</b> دریافت شد. در انتظار تایید.",
        OrderStatus.PAYMENT_REVIEWING: f"🕵️ در حال بررسی رسید سفارش <b>{num}</b>...",
        OrderStatus.APPROVED: (
            f"✅ <b>پرداخت شما تایید شد!</b>\n\n"
            f"🧾 سفارش <b>{num}</b> در حال آماده‌سازی است.\n"
            "ادمین محصول شما را به زودی ارسال خواهد کرد."
        ),
        OrderStatus.PREPARING: f"🔧 سفارش <b>{num}</b> در حال آماده‌سازی است.",
        OrderStatus.DELIVERED: f"📦 سفارش <b>{num}</b> ارسال شد!",
        OrderStatus.COMPLETED: f"🎉 سفارش <b>{num}</b> با موفقیت تکمیل شد. ممنون از خرید شما!",
        OrderStatus.CANCELLED: f"🚫 سفارش <b>{num}</b> لغو شد.",
        OrderStatus.REFUNDED: f"💰 وجه سفارش <b>{num}</b> بازگردانده شد.",
        OrderStatus.REJECTED: f"❌ پرداخت سفارش <b>{num}</b> رد شد. لطفاً با پشتیبانی تماس بگیرید.",
    }
    return messages.get(status, f"وضعیت سفارش <b>{num}</b> تغییر کرد.")