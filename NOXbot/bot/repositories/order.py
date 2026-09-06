"""Order repository."""

from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import func, select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models.order import Order, OrderItem, OrderStatus, OrderDelivery
from bot.models.order_event import OrderStatusEvent
from bot.models.payment import Payment, PaymentStatus
from bot.repositories.base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    """Order repository with specialized queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Order)

    # --- Order number ------------------------------------------------------ #
    async def next_order_number(self) -> str:
        """Generate the next human-readable order number.

        Uses the latest existing order number for the current year and
        increments it. Falls back to NOX-<year>-000001. The unique constraint
        on ``order_number`` is the safety net against races.
        """
        year = str(datetime.now(timezone.utc).year)
        prefix = f"NOX-{year}-"
        stmt = select(Order.order_number).where(
            Order.order_number.like(f"{prefix}%")
        ).order_by(Order.order_number.desc()).limit(1)
        result = await self.session.execute(stmt)
        last = result.scalar_one_or_none()
        if last:
            seq = int(last.rsplit("-", 1)[1]) + 1
        else:
            seq = 1
        return f"{prefix}{seq:06d}"

    async def get_by_number(self, order_number: str) -> Order | None:
        """Get order by its human-readable number."""
        stmt = select(Order).where(Order.order_number == order_number).options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.items).selectinload(OrderItem.config_product),
            selectinload(Order.user),
            selectinload(Order.status_events),
            selectinload(Order.payments),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # --- Relations --------------------------------------------------------- #
    async def get_by_user(
        self,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        status: OrderStatus | None = None,
    ) -> Sequence[Order]:
        """Get orders by user with pagination."""
        stmt = select(Order).where(Order.user_id == user_id).options(
            selectinload(Order.items),
            selectinload(Order.status_events),
        )
        if status:
            stmt = stmt.where(Order.status == status)
        stmt = stmt.order_by(desc(Order.created_at)).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_user(self, user_id: str, status: OrderStatus | None = None) -> int:
        stmt = select(func.count()).select_from(Order).where(Order.user_id == user_id)
        if status:
            stmt = stmt.where(Order.status == status)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_with_items(self, order_id: str) -> Order | None:
        stmt = select(Order).where(Order.id == order_id).options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.items).selectinload(OrderItem.config_product),
            selectinload(Order.user),
            selectinload(Order.status_events).selectinload(OrderStatusEvent.changed_by),
            selectinload(Order.payments),
            selectinload(Order.approved_by),
            selectinload(Order.delivered_by),
            selectinload(Order.cancelled_by),
            selectinload(Order.rejected_by),
            selectinload(Order.linked_ticket),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # --- Create ------------------------------------------------------------ #
    async def create_order(
        self,
        user_id: str,
        items: list[dict],
        order_number: str,
        payment_method=None,
        coupon_code: str | None = None,
        discount_amount: int = 0,
        customer_notes: str | None = None,
    ) -> Order:
        """Create an order from cart items.

        The order starts in WAITING_PAYMENT. A status event is recorded.
        """
        total_amount = sum(item["total_price"] for item in items)
        final_amount = total_amount - discount_amount

        order = Order(
            user_id=user_id,
            order_number=order_number,
            status=OrderStatus.WAITING_PAYMENT,
            payment_method=payment_method,
            total_amount=total_amount,
            discount_amount=discount_amount,
            final_amount=final_amount,
            coupon_code=coupon_code,
            customer_notes=customer_notes,
        )
        self.session.add(order)
        await self.session.flush()

        for item in items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item.get("product_id"),
                config_product_id=item.get("config_product_id"),
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                total_price=item["total_price"],
                product_title=item["title"],
                product_type=item["product_type"],
            )
            self.session.add(order_item)

        await self.status_event(
            order_id=order.id,
            to_status=OrderStatus.WAITING_PAYMENT,
            note="ایجاد سفارش",
            is_system=True,
        )
        await self.session.flush()
        await self.session.refresh(order)
        return order

    # --- Status transitions ------------------------------------------------ #
    async def status_event(
        self,
        order_id: str,
        to_status: OrderStatus,
        from_status: OrderStatus | None = None,
        changed_by_id: str | None = None,
        note: str | None = None,
        is_system: bool = False,
    ) -> OrderStatusEvent:
        """Insert a status-event row (audit trail)."""
        event = OrderStatusEvent(
            order_id=order_id,
            from_status=from_status,
            to_status=to_status,
            changed_by_id=changed_by_id,
            note=note,
            is_system=is_system,
        )
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def transition(
        self,
        order: Order,
        to_status: OrderStatus,
        changed_by_id: str | None = None,
        note: str | None = None,
        is_system: bool = False,
    ) -> Order:
        """Apply a status transition: set the new status + timestamp and
        record a status event."""
        updates = {"status": to_status}
        now = datetime.now(timezone.utc)

        if to_status == OrderStatus.PAYMENT_UPLOADED:
            updates["payment_uploaded_at"] = now
        elif to_status == OrderStatus.PAYMENT_REVIEWING:
            updates["payment_reviewed_at"] = now
        elif to_status == OrderStatus.APPROVED:
            updates["approved_at"] = now
            updates["paid_at"] = now
            updates["approved_by_id"] = changed_by_id
        elif to_status == OrderStatus.PREPARING:
            updates["preparing_at"] = now
        elif to_status == OrderStatus.DELIVERED:
            updates["delivered_at"] = now
            updates["actual_delivered_at"] = now
            updates["delivered_by_id"] = changed_by_id
        elif to_status == OrderStatus.COMPLETED:
            updates["completed_at"] = now
        elif to_status == OrderStatus.CANCELLED:
            updates["cancelled_at"] = now
            updates["cancelled_by_id"] = changed_by_id
            if note:
                updates["cancellation_reason"] = note
        elif to_status == OrderStatus.REFUNDED:
            updates["refunded_at"] = now
            if note:
                updates["refund_reason"] = note
        elif to_status == OrderStatus.REJECTED:
            updates["rejected_at"] = now
            updates["rejected_by_id"] = changed_by_id
            if note:
                updates["rejection_reason"] = note

        await self.update(order.id, **updates)
        await self.status_event(
            order_id=order.id,
            from_status=order.status,
            to_status=to_status,
            changed_by_id=changed_by_id,
            note=note,
            is_system=is_system,
        )
        await self.session.flush()
        return await self.get(order.id)

    # --- Stock discipline on terminal states ------------------------------- #
    async def restore_items_stock(self, order: Order) -> None:
        """Restore product/config stock for an order's items."""
        for item in order.items:
            if item.product_id:
                product = item.product
                if product and not product.unlimited_stock:
                    product.stock += item.quantity
                    if product.stock > 0 and product.status.name == "OUT_OF_STOCK":
                        from bot.models.product import ProductStatus
                        product.status = ProductStatus.ACTIVE
            elif item.config_product_id:
                cfg = item.config_product
                if cfg and not cfg.unlimited_stock:
                    cfg.stock += item.quantity

    async def decrement_items_stock(self, order: Order) -> bool:
        """Decrement stock for all items. Returns False if any item is short."""
        for item in order.items:
            if item.product_id:
                product = item.product
                if product is None or product.unlimited_stock:
                    continue
                if product.stock < item.quantity:
                    return False
            elif item.config_product_id:
                cfg = item.config_product
                if cfg is None or cfg.unlimited_stock:
                    continue
                if cfg.stock < item.quantity:
                    return False
        # All checks passed -> apply
        for item in order.items:
            if item.product_id:
                product = item.product
                if product and not product.unlimited_stock:
                    product.stock -= item.quantity
            elif item.config_product_id:
                cfg = item.config_product
                if cfg and not cfg.unlimited_stock:
                    cfg.stock -= item.quantity
        return True

    # --- Admin filtering --------------------------------------------------- #
    def _filter_stmt(self, f: dict[str, Any]):
        stmt = select(Order)
        if f.get("status"):
            stmt = stmt.where(Order.status == f["status"])
        if f.get("order_number"):
            stmt = stmt.where(Order.order_number.like(f"{f['order_number']}%"))
        if f.get("date_from") and f.get("date_to"):
            stmt = stmt.where(Order.created_at.between(f["date_from"], f["date_to"]))
        elif f.get("date_from"):
            stmt = stmt.where(Order.created_at >= f["date_from"])
        elif f.get("date_to"):
            stmt = stmt.where(Order.created_at <= f["date_to"])
        if f.get("price_min") is not None:
            stmt = stmt.where(Order.final_amount >= f["price_min"])
        if f.get("price_max") is not None:
            stmt = stmt.where(Order.final_amount <= f["price_max"])
        if f.get("user_id"):
            stmt = stmt.where(Order.user_id == f["user_id"])
        if f.get("admin_id"):
            stmt = stmt.where(
                or_(
                    Order.approved_by_id == f["admin_id"],
                    Order.delivered_by_id == f["admin_id"],
                )
            )
        if f.get("payment_status"):
            stmt = stmt.join(Order.payments).where(Payment.status == f["payment_status"])
        if f.get("product_query"):
            stmt = stmt.join(Order.items).where(
                or_(
                    OrderItem.product_title.ilike(f"%{f['product_query']}%"),
                    OrderItem.product_id == f.get("product_id"),
                )
            )
        return stmt

    async def filter_orders(
        self,
        f: dict[str, Any],
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[Order]:
        stmt = self._filter_stmt(f).options(
            selectinload(Order.user),
            selectinload(Order.items),
        ).order_by(desc(Order.created_at)).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().unique().all()

    async def count_filtered(self, f: dict[str, Any]) -> int:
        stmt = self._filter_stmt(f)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        result = await self.session.execute(count_stmt)
        return result.scalar_one()

    # --- Legacy admin methods (kept for compatibility) --------------------- #
    async def get_pending_orders(self, *, offset: int = 0, limit: int = 50) -> Sequence[Order]:
        """Orders awaiting admin review (receipt uploaded or under review)."""
        stmt = select(Order).where(
            Order.status.in_([
                OrderStatus.PAYMENT_UPLOADED,
                OrderStatus.PAYMENT_REVIEWING,
            ])
        ).options(
            selectinload(Order.user),
            selectinload(Order.items),
        ).order_by(Order.created_at).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_for_admin(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: OrderStatus | None = None,
        user_id: str | None = None,
    ) -> Sequence[Order]:
        f: dict[str, Any] = {}
        if status:
            f["status"] = status
        if user_id:
            f["user_id"] = user_id
        return await self.filter_orders(f, offset=offset, limit=limit)

    async def count_for_admin(self, status: OrderStatus | None = None, user_id: str | None = None) -> int:
        f: dict[str, Any] = {}
        if status:
            f["status"] = status
        if user_id:
            f["user_id"] = user_id
        return await self.count_filtered(f)

    async def get_revenue_stats(self) -> dict:
        # Total revenue
        stmt = select(func.sum(Order.final_amount)).where(Order.status.in_(
            [OrderStatus.APPROVED, OrderStatus.PREPARING, OrderStatus.DELIVERED, OrderStatus.COMPLETED]
        ))
        result = await self.session.execute(stmt)
        total_revenue = result.scalar_one() or 0

        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(func.sum(Order.final_amount)).where(
            Order.status.in_([OrderStatus.APPROVED, OrderStatus.PREPARING, OrderStatus.DELIVERED, OrderStatus.COMPLETED]),
            Order.paid_at >= today,
        )
        result = await self.session.execute(stmt)
        today_revenue = result.scalar_one() or 0

        stmt = select(func.count()).select_from(Order).where(Order.status != OrderStatus.CANCELLED)
        result = await self.session.execute(stmt)
        total_orders = result.scalar_one()

        return {
            "total_revenue": total_revenue,
            "today_revenue": today_revenue,
            "total_orders": total_orders,
        }

class OrderDeliveryRepository(BaseRepository[OrderDelivery]):
    """Repository for order delivery data."""

    model = OrderDelivery

    async def get_by_order_id(self, order_id: str) -> OrderDelivery | None:
        """Get delivery data for an order."""
        from sqlalchemy import select
        stmt = select(self.model).where(self.model.order_id == order_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_delivery(
        self,
        order_id: str,
        config_text: str | None = None,
        file_id: str | None = None,
        file_name: str | None = None,
        note: str | None = None,
        delivery_type: str = "config_text",
        created_by_id: str | None = None,
    ) -> OrderDelivery:
        """Save or update delivery data for an order."""
        existing = await self.get_by_order_id(order_id)
        if existing:
            # Update existing
            existing.config_text = config_text
            existing.file_id = file_id
            existing.file_name = file_name
            existing.note = note
            existing.delivery_type = delivery_type
            existing.status = "draft"  # Reset to draft
            await self.session.flush()
            return existing
        else:
            # Create new
            delivery = OrderDelivery(
                order_id=order_id,
                config_text=config_text,
                file_id=file_id,
                file_name=file_name,
                note=note,
                delivery_type=delivery_type,
                status="draft",
                created_by_id=created_by_id,
            )
            self.session.add(delivery)
            await self.session.flush()
            return delivery
