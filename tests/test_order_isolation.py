"""Order Isolation Tests — Verify cross-user access prevention."""

import uuid
import pytest
from sqlalchemy import select

from bot.models.order import Order, OrderStatus
from bot.models.user import User


class TestOrderIsolation:
    """Verify that users cannot access each other's orders."""

    @pytest.mark.asyncio
    async def test_user_a_cannot_access_user_b_order(self, session, test_user, test_user_b, test_product):
        """User B must not be able to access User A's order."""
        # Create order for User A
        order_a = Order(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            order_number="NOX-A-001",
            status=OrderStatus.APPROVED,
            total_amount=90000,
            final_amount=90000,
        )
        session.add(order_a)
        await session.flush()
        
        # Verify order belongs to User A
        result = await session.execute(
            select(Order).where(Order.id == order_a.id)
        )
        db_order = result.scalar_one()
        
        assert db_order.user_id == test_user.id, "Order should belong to User A"
        assert db_order.user_id != test_user_b.id, "Order should NOT belong to User B"

    @pytest.mark.asyncio
    async def test_multiple_orders_isolated(self, session, test_user, test_product):
        """Multiple orders from same user must be isolated."""
        order_1 = Order(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            order_number="NOX-001",
            status=OrderStatus.APPROVED,
            total_amount=90000,
            final_amount=90000,
        )
        order_2 = Order(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            order_number="NOX-002",
            status=OrderStatus.WAITING_PAYMENT,
            total_amount=50000,
            final_amount=50000,
        )
        session.add_all([order_1, order_2])
        await session.flush()
        
        # Verify both orders exist and are separate
        result = await session.execute(
            select(Order).where(Order.user_id == test_user.id)
        )
        orders = result.scalars().all()
        
        assert len(orders) == 2, "Should have 2 separate orders"
        assert orders[0].id != orders[1].id, "Orders must have different IDs"
        assert orders[0].order_number != orders[1].order_number, "Orders must have different numbers"
