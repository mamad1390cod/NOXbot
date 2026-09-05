"""The full boot sequence from ``main.py``, minus the network.

Everything ``main()`` does before ``start_polling`` is executed here against a
mocked Telegram session, so a broken startup is caught by the test-suite
instead of by the user at 3 a.m.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_boot_sequence_runs(seeded, mocked_bot):
    """init_db → seed settings → middlewares → routers → get_me → update types."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from bot.database.engine import init_db
    from bot.loader import get_dispatcher, mount_routers, register_middlewares
    from main import seed_settings

    bot, session = mocked_bot

    await init_db()
    await seed_settings()

    dp = get_dispatcher()
    register_middlewares()
    register_middlewares()  # idempotent: must not double-register

    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: None, "interval", seconds=45)
    scheduler.start()
    try:
        mount_routers(dp)
        mount_routers(dp)  # idempotent: must not raise "already attached"

        me = await bot.get_me()
        assert me.username

        update_types = set(dp.resolve_used_update_types()).union({"my_chat_member"})
        assert {"message", "callback_query", "my_chat_member"} <= update_types
    finally:
        scheduler.shutdown(wait=False)


async def test_settings_cache_is_warm(seeded):
    """Keyboard labels come from the settings cache; an empty cache = blank UI."""
    from bot.services import text_store

    assert text_store.button("btn_products")
    assert text_store.button("btn_admin")


async def test_every_entered_fsm_state_has_a_handler():
    """A state the bot *enters* must be consumed, otherwise the flow dead-ends.

    (States that are merely declared but never entered are fine — they are
    reserved for future steps.)
    """
    import re
    from pathlib import Path

    from aiogram.fsm.state import State

    from bot.handlers import admin_router, user_router

    root = Path(__file__).resolve().parent.parent

    entered: set[str] = set()
    pattern = re.compile(r"set_state\(\s*([A-Za-z_]+)\.([A-Za-z_]+)")
    for path in (root / "bot").rglob("*.py"):
        for group, name in pattern.findall(path.read_text(encoding="utf-8")):
            entered.add(f"{group}:{name}")

    used: set[str] = set()

    def walk(router):
        for observer in router.observers.values():
            for handler in observer.handlers:
                for flt in handler.filters or []:
                    callback = getattr(flt, "callback", None)
                    if isinstance(callback, State) and callback.state:
                        used.add(callback.state)
                    for item in getattr(callback, "states", None) or ():
                        if isinstance(item, State) and item.state:
                            used.add(item.state)
        for sub in router.sub_routers:
            walk(sub)

    walk(user_router)
    walk(admin_router)

    missing = sorted(entered - used)
    assert not missing, f"the bot enters these states but nothing handles the answer: {missing}"
