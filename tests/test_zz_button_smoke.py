"""Every inline button is clicked for real, against a mocked Telegram API.

The file is named ``test_zz_*`` on purpose: clicking every button includes
destructive actions (delete category, delete product, ban user), so it must run
*after* the focused flow tests that rely on the seeded rows.

For each ``callback_data`` pattern the keyboards can emit (collected by
``tools/audit_buttons.py``), a concrete payload is built from the seeded
database and pushed through the *real* dispatcher. A button passes when:

* a handler claims the update (``feed_update`` returns something other than
  ``UNHANDLED``), and
* no exception escapes the handler.

This is the regression net for the "خیلی از دکمه‌ها کار نمی‌کنه" class of bugs:
missing handlers, AttributeError on ORM objects, wrong callback parsing,
oversized callback_data, unregistered routers.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import sys
from pathlib import Path

import pytest
from aiogram.dispatcher.event.bases import UNHANDLED
from aiogram.types import CallbackQuery, Chat, Message, Update, User as TgUser

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from tests.conftest import NORMAL_USER_ID, OWNER_ID  # noqa: E402

pytestmark = pytest.mark.asyncio


def _patterns() -> list[tuple[str, bool]]:
    """(pattern, built_through_cb) for every callback_data the UI can emit."""
    from audit_buttons import build_report

    report = build_report()
    seen: dict[str, bool] = {}
    for button in report.buttons:
        seen.setdefault(button.pattern, button.safe_builder)
    return list(seen.items())


class _ErrorCollector(logging.Handler):
    """Catches exceptions that middlewares log and swallow."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record.getMessage())


def _fill(pattern: str, ids: dict[str, str]) -> str | None:
    """Turn a rendered pattern into a concrete callback payload."""
    if "{" not in pattern:
        return pattern

    def replace(match: re.Match[str]) -> str:
        expr = match.group(0)[1:-1].lower()
        if "perm" in expr:
            from bot.models.rbac import Permission
            from bot.utils.callback_data import permission_codec

            return permission_codec().encode(next(iter(Permission)).value)
        if "spec.key" in expr or "key" == expr:
            return "welcome_message"
        if "page" in expr or "idx" in expr or "index" in expr:
            return "0"
        if "qty" in expr or "quantity" in expr or "amount" in expr:
            return "1"
        if "action" in expr:
            return "addrole"
        if "tg_id" in expr or "telegram" in expr:
            return str(NORMAL_USER_ID)
        if "status" in expr:
            from bot.models.order import OrderStatus

            return OrderStatus.PENDING.value
        if "type" in expr:
            return "product"
        if "reg" in expr:
            return ids["registration_id"]
        if "custom_category" in expr or "ccat" in expr:
            return ids["custom_category_id"]
        if "custom" in expr:
            return ids["custom_id"]
        if "config" in expr or "conf" in expr:
            return ids["config_product_id"]
        if "product" in expr or "prod" in expr or expr.startswith("p."):
            return ids["product_id"]
        if "order" in expr or expr.startswith("o."):
            return ids["order_id"]
        if "payment" in expr or "pay" in expr:
            return ids["payment_id"]
        if "ticket" in expr or expr.startswith("t."):
            return ids["ticket_id"]
        if "role" in expr or expr.startswith("r."):
            return ids["role_id"]
        if "user" in expr or expr.startswith("u."):
            return ids["user_id"]
        if "cat" in expr:
            return ids["category_id"]
        if "item" in expr or "wish" in expr:
            return ids["wishlist_id"]
        return ids["product_id"]

    return re.sub(r"\{[^}]*\}", replace, pattern)


def _callback_update(data: str, telegram_id: int, update_id: int) -> Update:
    chat = Chat(id=telegram_id, type="private")
    user = TgUser(id=telegram_id, is_bot=False, first_name="Tester")
    message = Message(
        message_id=42,
        date=dt.datetime.now(dt.timezone.utc),
        chat=chat,
        from_user=TgUser(id=1, is_bot=True, first_name="NOX"),
        text="menu",
    )
    return Update(
        update_id=update_id,
        callback_query=CallbackQuery(
            id=str(update_id),
            from_user=user,
            chat_instance="test",
            message=message,
            data=data,
        ),
    )


async def test_every_button_is_handled_without_error(dispatcher, mocked_bot, seeded):
    from bot.utils.callback_data import cb

    bot, _session = mocked_bot
    failures: list[str] = []
    unhandled: list[str] = []

    collector = _ErrorCollector()
    logging.getLogger().addHandler(collector)

    for index, (pattern, via_cb) in enumerate(_patterns()):
        data = _fill(pattern, seeded)
        if data is None:
            continue
        if via_cb or len(data.encode()) > 64:
            # Long payloads reach Telegram as a short token; the outer
            # middleware must expand it back before the filters run.
            data = cb(*data.split(":"))
        if len(data.encode()) > 64:
            failures.append(f"{pattern!r}: payload too long ({data})")
            continue
        seen_errors = len(collector.records)
        # The owner passes every RBAC gate, so admin buttons are covered too.
        update = _callback_update(data, OWNER_ID, 10_000 + index)
        try:
            result = await dispatcher.feed_update(bot, update)
        except Exception as exc:  # noqa: BLE001 - that is exactly what we hunt
            failures.append(f"{pattern!r} -> {type(exc).__name__}: {exc}")
            continue
        if result is UNHANDLED:
            unhandled.append(f"{pattern!r} (payload {data})")
        for message in collector.records[seen_errors:]:
            failures.append(f"{pattern!r} -> logged error: {message}")

    logging.getLogger().removeHandler(collector)

    assert not failures, "buttons raising an exception:\n  " + "\n  ".join(failures)
    assert not unhandled, "buttons nothing handles:\n  " + "\n  ".join(unhandled)


async def test_normal_user_cannot_reach_admin_buttons(dispatcher, mocked_bot, seeded):
    """RBAC gate: a plain user's admin callbacks must not be handled."""
    bot, _session = mocked_bot
    update = _callback_update("admin:panel", 999_000_111, 20_001)
    result = await dispatcher.feed_update(bot, update)
    assert result is UNHANDLED
