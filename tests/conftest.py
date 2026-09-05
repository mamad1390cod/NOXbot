"""Shared fixtures: a throwaway database, seeded data and a live dispatcher.

The tests here are *offline integration tests*: real routers, real middlewares,
real services and a real (temporary) SQLite database — only the Telegram API is
mocked. That combination is what makes it possible to assert "this button
actually works" instead of "this button exists".
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Configure the app *before* bot.config is imported anywhere.
_TMP_DB = Path(tempfile.gettempdir()) / "noxbot_tests.db"
if _TMP_DB.exists():
    _TMP_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ.setdefault("BOT_TOKEN", "8726649647:TEST")
os.environ.setdefault("OWNER_ID", "6929510084")
os.environ.setdefault("ADMIN_PASSWORD", "test")

OWNER_ID = int(os.environ["OWNER_ID"])
NORMAL_USER_ID = 111222333


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def seeded(event_loop):
    """Create the schema and one row of every entity the handlers need."""
    from bot.database.engine import init_db
    from bot.database.uow import UnitOfWork

    await init_db()

    ids: dict[str, str] = {}
    async with UnitOfWork() as uow:
        from bot.models.category import Category
        from bot.models.config_shop import ConfigProduct
        from bot.models.custom import Custom, CustomCategory, CustomRegistration
        from bot.models.order import Order, OrderItem, OrderStatus
        from bot.models.payment import Payment, PaymentStatus
        from bot.models.product import Product
        from bot.models.rbac import AdminProfile, AdminRole, AdminStatus
        from bot.models.ticket import Ticket, TicketCategory
        from bot.models.user import User
        from bot.models.user_dashboard import WishlistItem
        from bot.services.rbac import RbacService
        from bot.services.settings import SettingsService

        settings_service = SettingsService(uow)
        await settings_service.ensure_defaults()
        await settings_service.load_cache()
        await RbacService(uow).seed_roles()
        await uow.flush()

        owner = User(telegram_id=OWNER_ID, username="owner", first_name="Owner")
        member = User(telegram_id=NORMAL_USER_ID, username="member", first_name="Member")
        uow.session.add_all([owner, member])
        await uow.flush()

        category = Category(name="گیفت کارت", type="product")
        config_category = Category(name="کانفیگ‌ها", type="config")
        custom_category_cat = Category(name="کاستوم‌ها", type="custom")
        uow.session.add_all([category, config_category, custom_category_cat])
        await uow.flush()

        product = Product(title="۱۰۰۰ سکه", price=50000, category_id=category.id, stock=5)
        config_product = ConfigProduct(title="کانفیگ آیفون", price=25000, category_id=config_category.id)
        custom_category = CustomCategory(name="بتل رویال")
        uow.session.add_all([product, config_product, custom_category])
        await uow.flush()

        custom = Custom(
            title="تورنمنت هفتگی",
            entry_fee=10000,
            max_capacity=16,
            custom_category_id=custom_category.id,
        )
        uow.session.add(custom)
        await uow.flush()

        registration = CustomRegistration(
            custom_id=custom.id, user_id=member.id, codm_username="NOXplayer"
        )
        ticket_category = TicketCategory(name="مشکل پرداخت")
        uow.session.add_all([registration, ticket_category])
        await uow.flush()

        ticket = Ticket(
            user_id=member.id,
            ticket_category_id=ticket_category.id,
            subject="پرداخت انجام نشد",
            message="سلام، مبلغ کم شد ولی سفارش ثبت نشد.",
        )
        order = Order(
            user_id=member.id,
            order_number="NOX-1001",
            total_amount=50000,
            final_amount=50000,
            status=OrderStatus.PENDING,
        )
        uow.session.add_all([ticket, order])
        await uow.flush()

        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_title=product.title,
            product_type="product",
            quantity=1,
            unit_price=50000,
            total_price=50000,
        )
        payment = Payment(
            user_id=member.id,
            order_id=order.id,
            amount=50000,
            status=PaymentStatus.PENDING,
        )
        wishlist = WishlistItem(user_id=member.id, product_id=product.id)
        uow.session.add_all([order_item, payment, wishlist])
        await uow.flush()

        role = (await uow.admin_roles.get_all(limit=5))[0]
        profile = AdminProfile(user_id=member.id, role_id=role.id, status=AdminStatus.ACTIVE)
        uow.session.add(profile)
        await uow.flush()

        ids.update(
            owner_user_id=owner.id,
            user_id=member.id,
            category_id=category.id,
            config_category_id=config_category.id,
            custom_category_cat_id=custom_category_cat.id,
            product_id=product.id,
            config_product_id=config_product.id,
            custom_id=custom.id,
            custom_category_id=custom_category.id,
            registration_id=registration.id,
            ticket_category_id=ticket_category.id,
            ticket_id=ticket.id,
            order_id=order.id,
            payment_id=payment.id,
            role_id=role.id,
            wishlist_id=wishlist.id,
        )
        await uow.commit()
    return ids


@pytest.fixture(scope="session")
async def dispatcher(seeded):
    """The real dispatcher: production routers + production middlewares."""
    from bot.handlers import admin_router, user_router
    from bot.loader import get_dispatcher, register_middlewares

    dp = get_dispatcher()
    register_middlewares()
    if not dp.sub_routers:
        dp.include_router(user_router)
        dp.include_router(admin_router)
    return dp


@pytest.fixture(scope="session")
def mocked_bot():
    from tests.mocked_bot import make_mocked_bot

    bot, session = make_mocked_bot()
    return bot, session
