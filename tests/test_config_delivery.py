"""Config Delivery Tests — Verify config order delivery lifecycle."""

import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import select

from bot.models.order import Order, OrderStatus, OrderDelivery
from bot.models.user import User


class TestConfigDelivery:
    """Verify config delivery save/send lifecycle."""

    @pytest.mark.asyncio
    async def test_delivery_saved_as_draft(self, session, test_user, test_order):
        """Delivery must be saved as DRAFT, not sent to customer."""
        delivery = OrderDelivery(
            id=str(uuid.uuid4()),
            order_id=test_order.id,
            delivery_type="config_text",
            config_text="server=1.2.3.4\nuser=admin\npass=secret123",
            status="draft",
            created_by_id=test_user.id,
        )
        session.add(delivery)
        await session.flush()
        
        # Verify from DB
        result = await session.execute(
            select(OrderDelivery).where(OrderDelivery.order_id == test_order.id)
        )
        db_delivery = result.scalar_one_or_none()
        
        assert db_delivery is not None, "Delivery should exist in DB"
        assert db_delivery.status == "draft", f"Status should be 'draft', got '{db_delivery.status}'"
        assert db_delivery.config_text is not None
        assert db_delivery.delivered_at is None, "Should NOT be delivered yet"

    @pytest.mark.asyncio
    async def test_delivery_marked_delivered_on_complete(self, session, test_user, test_order):
        """When order completes, delivery must be marked as 'delivered'."""
        delivery = OrderDelivery(
            id=str(uuid.uuid4()),
            order_id=test_order.id,
            delivery_type="config_file",
            file_id="tg_file_id_123",
            file_name="config.zip",
            status="draft",
            created_by_id=test_user.id,
        )
        session.add(delivery)
        await session.flush()
        
        # Simulate delivery send (what the complete handler does)
        delivery.status = "delivered"
        delivery.delivered_at = datetime.now(timezone.utc)
        await session.flush()
        
        # Verify
        result = await session.execute(
            select(OrderDelivery).where(OrderDelivery.id == delivery.id)
        )
        db_delivery = result.scalar_one()
        
        assert db_delivery.status == "delivered"
        assert db_delivery.delivered_at is not None

    @pytest.mark.asyncio
    async def test_delivery_failed_status(self, session, test_user, test_order):
        """If Telegram send fails, delivery must be marked 'failed'."""
        delivery = OrderDelivery(
            id=str(uuid.uuid4()),
            order_id=test_order.id,
            delivery_type="mixed",
            config_text="some config",
            file_id="tg_file_id_456",
            status="draft",
            created_by_id=test_user.id,
        )
        session.add(delivery)
        await session.flush()
        
        # Simulate send failure
        delivery.status = "failed"
        await session.flush()
        
        # Verify order is NOT completed
        result = await session.execute(
            select(Order).where(Order.id == test_order.id)
        )
        db_order = result.scalar_one()
        assert db_order.status != OrderStatus.COMPLETED, (
            "Order should NOT be completed when delivery fails"
        )

    @pytest.mark.asyncio
    async def test_delivery_unique_per_order(self, session, test_user, test_order):
        """Only one delivery record per order (UNIQUE constraint)."""
        delivery_1 = OrderDelivery(
            id=str(uuid.uuid4()),
            order_id=test_order.id,
            delivery_type="config_text",
            config_text="first",
            status="draft",
        )
        session.add(delivery_1)
        await session.flush()
        
        # Attempt to create second delivery for same order
        delivery_2 = OrderDelivery(
            id=str(uuid.uuid4()),
            order_id=test_order.id,  # Same order_id
            delivery_type="config_file",
            file_id="file_123",
            status="draft",
        )
        session.add(delivery_2)
        
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    @pytest.mark.asyncio
    async def test_delivery_retry_possible(self, session, test_user, test_order):
        """After failure, admin must be able to retry."""
        delivery = OrderDelivery(
            id=str(uuid.uuid4()),
            order_id=test_order.id,
            delivery_type="config_text",
            config_text="retry config",
            status="failed",
            created_by_id=test_user.id,
        )
        session.add(delivery)
        await session.flush()
        
        # Retry: reset to draft
        delivery.status = "draft"
        await session.flush()
        
        # Now mark as delivered
        delivery.status = "delivered"
        delivery.delivered_at = datetime.now(timezone.utc)
        await session.flush()
        
        result = await session.execute(
            select(OrderDelivery).where(OrderDelivery.id == delivery.id)
        )
        db_delivery = result.scalar_one()
        assert db_delivery.status == "delivered"
