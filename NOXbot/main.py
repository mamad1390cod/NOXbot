"""NOXbot Shop — main entry point.

Boot sequence:
1. Load config and initialize logging
2. Create DB tables (SQLite)
3. Register middlewares (user context, throttling)
4. Seed default bot settings
5. Mount user and admin routers
6. Start long-polling with graceful shutdown
"""

import asyncio
import contextlib
import logging
import sys
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import get_settings
from bot.core.logging import setup_logging, log_event
from bot.database.engine import init_db
from bot.database.uow import UnitOfWork
from bot.handlers import admin_router, user_router
from bot.loader import get_bot, get_dispatcher, register_middlewares
from bot.services.settings import SettingsService

# Initialize professional logging system
setup_logging(
    log_level='INFO',
    log_dir='logs',  # Enable file logging
    use_json=False,  # Use colored console output
    use_colors=True,
)
logger = logging.getLogger("noxbot")

# Ensure the modules importable
sys.path.insert(0, str(Path(__file__).resolve().parent))


async def seed_settings() -> None:
    """Ensure default settings and built-in RBAC roles exist."""
    uow = UnitOfWork()
    try:
        async with uow:
            ss = SettingsService(uow)
            await ss.ensure_defaults()
            await ss.load_cache()  # warm the in-memory settings cache
            # Make sure the built-in admin roles are present (idempotent).
            from bot.services.rbac import RbacService
            await RbacService(uow).seed_roles()
    except Exception as e:
        logger.exception("Failed to seed settings: %s", e)


async def main() -> None:
    settings = get_settings()
    
    log_event('application_starting', level=logging.INFO)

    logger.info("Initializing database...")
    await init_db()
    log_event('database_connected', level=logging.INFO)
    logger.info("Database ready.")

    await seed_settings()

    bot = get_bot()
    dp = get_dispatcher()

    # Register middlewares (user context + throttling)
    register_middlewares()

    # Scheduler (background tasks)
    scheduler = AsyncIOScheduler()

    async def _process_due_broadcasts() -> None:
        uow = UnitOfWork()
        try:
            async with uow:
                from bot.services.broadcast import BroadcastService
                await BroadcastService(uow, bot=bot).schedule_due()
        except Exception as e:
            logger.exception("broadcast scheduler tick failed: %s", e)

    scheduler.add_job(_process_due_broadcasts, "interval", seconds=45)
    scheduler.start()
    log_event('scheduler_started', level=logging.INFO)

    # Mount routers
    dp.include_router(user_router)
    dp.include_router(admin_router)

    logger.info("Routers mounted. Starting polling...")

    me = await bot.get_me()
    log_event('bot_connected', level=logging.INFO, username=me.username, bot_id=me.id)
    logger.info("Bot started: @%s (%s)", me.username, me.id)
    log_event('application_ready', level=logging.INFO)

    try:
        await dp.start_polling(
            bot,
            allowed_updates=set(dp.resolve_used_update_types()).union({"my_chat_member"}),
            handle_signals=True,
        )
    finally:
        log_event('shutdown_requested', level=logging.INFO)
        await dp.storage.close()
        await bot.session.close()
        scheduler.shutdown(wait=False)
        log_event('application_stopped', level=logging.INFO)
        logger.info("Bot stopped.")


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        import asyncio

        asyncio.run(main())