"""Database Integrity Tests — Schema, constraints, relationships."""

import uuid
import pytest
from sqlalchemy import select, inspect, text
from sqlalchemy.exc import IntegrityError

from bot.models.base import Base
from bot.models.user import User, UserRole
from bot.models.order import Order, OrderItem, OrderStatus, OrderDelivery
from bot.models.payment import Payment, PaymentStatus, PaymentMethod
from bot.models.product import Product, ProductStatus
from bot.models.cart import Cart, CartItem
from bot.models.user_dashboard import Transaction, TransactionType


class TestSchemaIntegrity:
    """Verify database schema is correct."""

    @pytest.mark.asyncio
    async def test_all_models_create_tables(self, engine):
        """All models must create tables without error."""
        async with engine.begin() as conn:
            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
        
        required_tables = [
            'users', 'orders', 'order_items', 'payments', 'products',
            'categories', 'carts', 'cart_items', 'transactions',
            'order_deliveries', 'admin_roles', 'admin_profiles',
        ]
        for table in required_tables:
            assert table in tables, f"Table '{table}' missing from schema"

    @pytest.mark.asyncio
    async def test_user_wallet_balance_not_null(self, session, test_user):
        """Wallet balance must default to 0, not NULL."""
        user = User(
            id=str(uuid.uuid4()),
            telegram_id=200001,
            username="wallet_test",
            role=UserRole.USER,
            referral_code="REF-WALLET",
        )
        session.add(user)
        await session.flush()
        
        result = await session.execute(select(User).where(User.id == user.id))
        db_user = result.scalar_one()
        assert db_user.wallet_balance is not None, "wallet_balance should default to 0, not NULL"
        assert db_user.wallet_balance >= 0, "wallet_balance should be non-negative"

    @pytest.mark.asyncio
    async def test_order_unique_order_number(self, session, test_user):
        """Order numbers must be unique."""
        order_1 = Order(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            order_number="NOX-UNIQUE-001",
            status=OrderStatus.PENDING,
            total_amount=1000,
            final_amount=1000,
        )
        session.add(order_1)
        await session.flush()
        
        order_2 = Order(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            order_number="NOX-UNIQUE-001",  # Duplicate!
            status=OrderStatus.PENDING,
            total_amount=2000,
            final_amount=2000,
        )
        session.add(order_2)
        
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    @pytest.mark.asyncio
    async def test_order_delivery_unique_per_order(self, session, test_order):
        """Order delivery must be unique per order."""
        d1 = OrderDelivery(
            id=str(uuid.uuid4()),
            order_id=test_order.id,
            delivery_type="config_text",
            config_text="test",
            status="draft",
        )
        session.add(d1)
        await session.flush()
        
        d2 = OrderDelivery(
            id=str(uuid.uuid4()),
            order_id=test_order.id,  # Same order
            delivery_type="config_file",
            file_id="file",
            status="draft",
        )
        session.add(d2)
        
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    @pytest.mark.asyncio
    async def test_order_items_cascade_delete(self, session, test_user, test_product):
        """Deleting an order must cascade-delete its items."""
        order = Order(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            order_number="NOX-CASCADE-001",
            status=OrderStatus.PENDING,
            total_amount=90000,
            final_amount=90000,
        )
        session.add(order)
        await session.flush()
        
        item = OrderItem(
            id=str(uuid.uuid4()),
            order_id=order.id,
            product_id=test_product.id,
            product_title=test_product.title,
            product_type="product",
            unit_price=test_product.price,
            quantity=1,
        )
        session.add(item)
        await session.flush()
        
        item_id = item.id
        
        # Delete order
        await session.delete(order)
        await session.flush()
        
        # Verify item is gone
        result = await session.execute(
            select(OrderItem).where(OrderItem.id == item_id)
        )
        assert result.scalar_one_or_none() is None, "OrderItem should be cascade-deleted"

    @pytest.mark.asyncio
    async def test_transaction_balance_consistency(self, session, test_user):
        """Transaction balance_before/after must be consistent with amount."""
        balance_before = 500000
        amount = -90000
        balance_after = balance_before + amount  # 410000
        
        txn = Transaction(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            type=TransactionType.PURCHASE,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
        )
        session.add(txn)
        await session.flush()
        
        result = await session.execute(
            select(Transaction).where(Transaction.id == txn.id)
        )
        db_txn = result.scalar_one()
        
        # Verify mathematical consistency
        assert db_txn.balance_after == db_txn.balance_before + db_txn.amount, (
            f"Transaction math inconsistent: "
            f"{db_txn.balance_before} + {db_txn.amount} != {db_txn.balance_after}"
        )


class TestCartIsolation:
    """Verify cart isolation between users."""

    @pytest.mark.asyncio
    async def test_cart_per_user(self, session, test_user, test_user_b, test_product):
        """Each user must have their own cart."""
        cart_a = Cart(id=str(uuid.uuid4()), user_id=test_user.id)
        cart_b = Cart(id=str(uuid.uuid4()), user_id=test_user_b.id)
        session.add_all([cart_a, cart_b])
        await session.flush()
        
        item_a = CartItem(
            id=str(uuid.uuid4()),
            cart_id=cart_a.id,
            product_id=test_product.id,
            quantity=2,
        )
        item_b = CartItem(
            id=str(uuid.uuid4()),
            cart_id=cart_b.id,
            product_id=test_product.id,
            quantity=5,
        )
        session.add_all([item_a, item_b])
        await session.flush()
        
        # Verify User A's cart
        result_a = await session.execute(
            select(CartItem).join(Cart).where(Cart.user_id == test_user.id)
        )
        items_a = result_a.scalars().all()
        assert len(items_a) == 1
        assert items_a[0].quantity == 2
        
        # Verify User B's cart
        result_b = await session.execute(
            select(CartItem).join(Cart).where(Cart.user_id == test_user_b.id)
        )
        items_b = result_b.scalars().all()
        assert len(items_b) == 1
        assert items_b[0].quantity == 5
        
        # Verify isolation
        assert items_a[0].quantity != items_b[0].quantity, "Carts must be isolated"


class TestTelegramIDOverflow:
    """Regression test for SQLite INTEGER overflow with large Telegram IDs."""

    @pytest.mark.asyncio
    async def test_large_telegram_id_storage(self, session):
        """Verify that large Telegram IDs (>2^31) can be stored without overflow."""
        from bot.models.user import User, UserRole
        
        # Modern Telegram IDs can exceed 2^31 (2,147,483,647)
        # Some are in the range of 5-7 billion or higher
        large_telegram_id = 5_500_000_000  # 5.5 billion
        
        user = User(
            id=str(uuid.uuid4()),
            telegram_id=large_telegram_id,
            username="large_id_user",
            first_name="Large",
            last_name="ID",
            role=UserRole.USER,
            wallet_balance=0,
            referral_code="REF-LARGE-ID",
        )
        session.add(user)
        await session.flush()
        
        # Verify it was stored correctly
        result = await session.execute(
            select(User).where(User.telegram_id == large_telegram_id)
        )
        db_user = result.scalar_one_or_none()
        
        assert db_user is not None, "User with large Telegram ID should be stored"
        assert db_user.telegram_id == large_telegram_id, (
            f"Telegram ID mismatch: expected {large_telegram_id}, got {db_user.telegram_id}"
        )

    @pytest.mark.asyncio
    async def test_very_large_telegram_id_storage(self, session):
        """Verify that very large Telegram IDs (near 64-bit limit) can be stored."""
        from bot.models.user import User, UserRole
        
        # Test with a value near the 64-bit signed integer limit
        # SQLite INTEGER is 64-bit signed: max is 9,223,372,036,854,775,807
        very_large_id = 9_000_000_000_000  # 9 trillion (well within 64-bit range)
        
        user = User(
            id=str(uuid.uuid4()),
            telegram_id=very_large_id,
            username="very_large_id_user",
            first_name="Very",
            last_name="Large",
            role=UserRole.USER,
            wallet_balance=0,
            referral_code="REF-VERY-LARGE",
        )
        session.add(user)
        await session.flush()
        
        # Verify it was stored correctly
        result = await session.execute(
            select(User).where(User.telegram_id == very_large_id)
        )
        db_user = result.scalar_one_or_none()
        
        assert db_user is not None, "User with very large Telegram ID should be stored"
        assert db_user.telegram_id == very_large_id, (
            f"Telegram ID mismatch: expected {very_large_id}, got {db_user.telegram_id}"
        )
