"""End-to-end flows through the real dispatcher (FSM included).

These cover the sections that were reported broken: categories, customs,
roles/permissions, the main menu on media messages, and the account-info flow
whose router was never mounted.
"""

from __future__ import annotations

import datetime as dt

import pytest
from aiogram.dispatcher.event.bases import UNHANDLED
from aiogram.types import (
    CallbackQuery,
    Chat,
    Message,
    PhotoSize,
    Update,
    User as TgUser,
)

from tests.conftest import NORMAL_USER_ID, OWNER_ID

pytestmark = pytest.mark.asyncio

_update_id = iter(range(50_000, 90_000))


def _msg_update(text: str, telegram_id: int = OWNER_ID) -> Update:
    return Update(
        update_id=next(_update_id),
        message=Message(
            message_id=next(_update_id),
            date=dt.datetime.now(dt.timezone.utc),
            chat=Chat(id=telegram_id, type="private"),
            from_user=TgUser(id=telegram_id, is_bot=False, first_name="Tester"),
            text=text,
        ),
    )


def _cb_update(data: str, telegram_id: int = OWNER_ID, *, with_photo: bool = False) -> Update:
    message = Message(
        message_id=next(_update_id),
        date=dt.datetime.now(dt.timezone.utc),
        chat=Chat(id=telegram_id, type="private"),
        from_user=TgUser(id=1, is_bot=True, first_name="NOX"),
        text=None if with_photo else "screen",
        caption="banner" if with_photo else None,
        photo=[PhotoSize(file_id="f", file_unique_id="u", width=1, height=1)] if with_photo else None,
    )
    return Update(
        update_id=next(_update_id),
        callback_query=CallbackQuery(
            id=str(next(_update_id)),
            from_user=TgUser(id=telegram_id, is_bot=False, first_name="Tester"),
            chat_instance="test",
            message=message,
            data=data,
        ),
    )


async def _feed(dispatcher, bot, update: Update):
    result = await dispatcher.feed_update(bot, update)
    assert result is not UNHANDLED, f"nothing handled {update}"
    return result


# --- Start / menu ---------------------------------------------------------- #
async def test_start_and_menu_commands(dispatcher, mocked_bot, seeded):
    bot, session = mocked_bot
    await _feed(dispatcher, bot, _msg_update("/start", NORMAL_USER_ID))
    # "/menu" used to be swallowed by a broken `or` filter
    await _feed(dispatcher, bot, _msg_update("/menu", NORMAL_USER_ID))
    await _feed(dispatcher, bot, _msg_update("منو", NORMAL_USER_ID))
    assert session.calls


async def test_home_button_works_on_a_photo_message(dispatcher, mocked_bot, seeded):
    """edit_text fails on media; the helper must fall back to caption/new msg."""
    bot, session = mocked_bot
    before = len(session.calls)
    await _feed(dispatcher, bot, _cb_update("menu:home", NORMAL_USER_ID, with_photo=True))
    assert len(session.calls) > before


async def test_pagination_placeholder_and_cancel_are_handled(dispatcher, mocked_bot, seeded):
    bot, _ = mocked_bot
    await _feed(dispatcher, bot, _cb_update("action:noop", NORMAL_USER_ID))
    await _feed(dispatcher, bot, _cb_update("noop", NORMAL_USER_ID))
    await _feed(dispatcher, bot, _cb_update("action:cancel", NORMAL_USER_ID))


# --- Category management (admin) ------------------------------------------- #
async def test_admin_can_create_and_rename_a_category(dispatcher, mocked_bot, seeded):
    from bot.database.uow import UnitOfWork

    bot, _ = mocked_bot
    await _feed(dispatcher, bot, _cb_update("admin:categories"))
    await _feed(dispatcher, bot, _cb_update("acat:add"))
    await _feed(dispatcher, bot, _cb_update("acat:add_type:product"))
    await _feed(dispatcher, bot, _msg_update("دسته تستی"))

    async with UnitOfWork() as uow:
        created = [c for c in await uow.categories.get_all(limit=100) if c.name == "دسته تستی"]
    assert created, "category was not created"
    cat_id = created[0].id

    # The ✏️ ویرایش button had no handler at all before.
    await _feed(dispatcher, bot, _cb_update(f"acat:edit:{cat_id}"))
    await _feed(dispatcher, bot, _msg_update("دسته ویرایش‌شده"))

    async with UnitOfWork() as uow:
        renamed = await uow.categories.get(cat_id)
    assert renamed.name == "دسته ویرایش‌شده"


async def test_category_toggles_refresh_the_screen(dispatcher, mocked_bot, seeded):
    from bot.database.uow import UnitOfWork

    bot, _ = mocked_bot
    cat_id = seeded["category_id"]
    async with UnitOfWork() as uow:
        before = (await uow.categories.get(cat_id)).is_active

    await _feed(dispatcher, bot, _cb_update(f"acat:toggle:{cat_id}"))

    async with UnitOfWork() as uow:
        after = (await uow.categories.get(cat_id)).is_active
    assert after is not before


# --- Roles & permissions --------------------------------------------------- #
async def test_permission_toggle_uses_short_codes(dispatcher, mocked_bot, seeded):
    from bot.database.uow import UnitOfWork
    from bot.models.rbac import Permission
    from bot.utils.callback_data import permission_codec

    bot, _ = mocked_bot
    perm = Permission.VIEW_DASHBOARD
    code = permission_codec().encode(perm.value)

    async with UnitOfWork() as uow:
        # The owner role is intentionally immutable; pick an editable one.
        roles = [r for r in await uow.admin_roles.get_all(limit=20) if r.slug != "owner"]
        role_id = roles[0].id
        before = perm in roles[0].permission_set()

    await _feed(dispatcher, bot, _cb_update(f"admin:roles:perm:{role_id}:{code}"))

    async with UnitOfWork() as uow:
        role = await uow.admin_roles.get(role_id)
        after = perm in role.permission_set()
    assert after is not before


async def test_add_admin_flow_shows_the_user_name(dispatcher, mocked_bot, seeded):
    """The `display_name` AttributeError crashed this exact step."""
    bot, session = mocked_bot
    await _feed(dispatcher, bot, _cb_update("admin:roles:add"))
    before = len(session.calls)
    await _feed(dispatcher, bot, _msg_update(str(NORMAL_USER_ID)))
    texts = [getattr(c, "text", "") or "" for c in session.calls[before:]]
    assert any("نقشی" in t or "ادمین" in t for t in texts), texts


# --- Customs --------------------------------------------------------------- #
async def test_custom_winner_selection_end_to_end(dispatcher, mocked_bot, seeded):
    """Winner pick carried two UUIDs (86 bytes) and never reached Telegram."""
    from bot.database.uow import UnitOfWork

    bot, _ = mocked_bot
    custom_id = seeded["custom_id"]
    reg_id = seeded["registration_id"]

    await _feed(dispatcher, bot, _cb_update(f"acustom:winner:{custom_id}"))
    await _feed(dispatcher, bot, _cb_update(f"acustom:winner_type:{custom_id}:player"))
    await _feed(dispatcher, bot, _cb_update(f"acustom:pick:{reg_id}"))

    async with UnitOfWork() as uow:
        custom = await uow.customs.get(custom_id)
    assert custom.winner_id == seeded["user_id"]


async def test_user_can_browse_customs_and_cart(dispatcher, mocked_bot, seeded):
    bot, _ = mocked_bot
    await _feed(dispatcher, bot, _cb_update("menu:customs", NORMAL_USER_ID))
    await _feed(dispatcher, bot, _cb_update(f"custom_sel:{seeded['custom_id']}", NORMAL_USER_ID))
    await _feed(dispatcher, bot, _cb_update(f"custom_add:{seeded['custom_id']}", NORMAL_USER_ID))
    await _feed(dispatcher, bot, _cb_update("menu:custom_cart", NORMAL_USER_ID))


# --- Account-info flow (router was never mounted) --------------------------- #
async def test_account_info_router_is_mounted(dispatcher, mocked_bot, seeded):
    from bot.handlers import USER_ROUTER_SPECS

    assert any(name == "account" for name, _ in USER_ROUTER_SPECS)
    bot, _ = mocked_bot
    # account:confirm without state answers with an alert instead of dying
    await _feed(dispatcher, bot, _cb_update("account:confirm", NORMAL_USER_ID))
