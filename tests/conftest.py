"""Test fixtures — isolated SQLite database per test session."""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from bot.models.base import Base
from bot.models.user import User, UserRole
from bot.models.product import Product, ProductStatus
from bot.models.category import Category
from bot.models.config_shop import ConfigProduct, ConfigCategory
from bot.models.cart import Cart, CartItem
from bot.models.order import Order, OrderItem, OrderStatus, OrderDelivery
from bot.models.payment import Payment, PaymentStatus, PaymentMethod
from bot.models.user_dashboard import Transaction, TransactionType
from bot.models.rbac import AdminRole, AdminProfile, AdminStatus, RoleSlug


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def session(engine):
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as sess:
        yield sess
        await sess.rollback()


@pytest_asyncio.fixture(scope="function")
async def uow(session):
    """Create a UnitOfWork-like wrapper for testing."""
    from bot.database.uow import UnitOfWork
    # We'll create a mock UoW that uses our test session
    class TestUoW:
        def __init__(self, session):
            self.session = session
            self._committed = False
        
        async def commit(self):
            await self.session.commit()
            self._committed = True
        
        async def rollback(self):
            await self.session.rollback()
        
        async def flush(self):
            await self.session.flush()
        
        def __getattr__(self, name):
            # Lazy-init repositories
            from bot.repositories.user import UserRepository
            from bot.repositories.product import ProductRepository
            from bot.repositories.category import CategoryRepository
            from bot.repositories.cart import CartRepository
            from bot.repositories.order import OrderRepository, OrderDeliveryRepository
            from bot.repositories.payment import PaymentRepository
            from bot.repositories.user_dashboard import TransactionRepository
            from bot.repositories.rbac import AdminRoleRepository, AdminProfileRepository
            from bot.repositories.config_shop import ConfigProductRepository
            
            repo_map = {
                'users': UserRepository,
                'products': ProductRepository,
                'categories': CategoryRepository,
                'carts': CartRepository,
                'orders': OrderRepository,
                'order_deliveries': OrderDeliveryRepository,
                'payments': PaymentRepository,
                'transactions': TransactionRepository,
                'admin_roles': AdminRoleRepository,
                'admin_profiles': AdminProfileRepository,
                'config_products': ConfigProductRepository,
            }
            if name in repo_map:
                repo = repo_map[name](self.session)
                setattr(self, name, repo)
                return repo
            raise AttributeError(f"TestUoW has no attribute '{name}'")
    
    return TestUoW(session)


# --- Factory fixtures ---

@pytest_asyncio.fixture
async def test_user(session) -> User:
    user = User(
        id=str(uuid.uuid4()),
        telegram_id=100001,
        username="testuser",
        first_name="Test",
        last_name="User",
        role=UserRole.USER,
        wallet_balance=500000,
        email="test@test.com",
        customer_name="Test User",
        referral_code="REF-TEST-A",
    )
    session.add(user)
    await session.flush()
    return user


@pytest_asyncio.fixture
async def test_user_b(session) -> User:
    user = User(
        id=str(uuid.uuid4()),
        telegram_id=100002,
        username="testuserb",
        first_name="Test",
        last_name="UserB",
        role=UserRole.USER,
        wallet_balance=300000,
        referral_code="REF-TEST-B",
    )
    session.add(user)
    await session.flush()
    return user


@pytest_asyncio.fixture
async def admin_user(session) -> User:
    user = User(
        id=str(uuid.uuid4()),
        telegram_id=999999,
        username="admin",
        first_name="Admin",
        role=UserRole.ADMIN,
        wallet_balance=0,
        referral_code="REF-ADMIN",
    )
    session.add(user)
    await session.flush()
    return user


@pytest_asyncio.fixture
async def test_category(session) -> Category:
    cat = Category(
        id=str(uuid.uuid4()),
        name="Test Category",
        type="product",
        sort_order=0,
    )
    session.add(cat)
    await session.flush()
    return cat


@pytest_asyncio.fixture
async def test_product(session, test_category) -> Product:
    prod = Product(
        id=str(uuid.uuid4()),
        title="Test Product",
        description="A test product",
        price=90000,
        stock=10,
        category_id=test_category.id,
        status=ProductStatus.ACTIVE,
    )
    session.add(prod)
    await session.flush()
    return prod


@pytest_asyncio.fixture
async def test_order(session, test_user, test_product) -> Order:
    order = Order(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        order_number="NOX-TEST-001",
        status=OrderStatus.APPROVED,
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
        unit_price=test_product.price,
        product_type="product",
        quantity=1,
    )
    session.add(item)
    await session.flush()
    return order


@pytest_asyncio.fixture
async def paid_order(session, test_user, test_product, test_order) -> Order:
    """An order that has been paid via wallet."""
    test_order.status = OrderStatus.APPROVED
    
    payment = Payment(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        order_id=test_order.id,
        amount=90000,
        method=PaymentMethod.BALANCE,
        status=PaymentStatus.APPROVED,
    )
    session.add(payment)
    
    test_user.wallet_balance = 410000  # 500000 - 90000
    
    txn = Transaction(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        type=TransactionType.PURCHASE,
        amount=-90000,
        balance_before=500000,
        balance_after=410000,
        ref_id=test_order.id,
    )
    session.add(txn)
    await session.flush()
    return test_order
