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
from bot.database.engine import init_db
from bot.database.uow import UnitOfWork
from bot.handlers import admin_router, user_router  # noqa: F401 - builds the router tree
from bot.loader import get_bot, get_dispatcher, mount_routers, register_middlewares
from bot.services.settings import SettingsService

def _setup_logging() -> logging.Logger:
    """Console + rotating file logging that survives Windows code pages.

    Persian log lines crash a cp1256/cp1252 stream with UnicodeEncodeError when
    stdout is redirected to a file, so the console stream is reconfigured to
    UTF-8 and a UTF-8 log file is kept under ``logs/``.
    """
    from logging.handlers import RotatingFileHandler

    with contextlib.suppress(Exception):  # Python <3.7 / exotic streams
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%H:%M:%S"
    )
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)

    handlers: list[logging.Handler] = [console]
    with contextlib.suppress(OSError):
        log_dir = Path(__file__).resolve().parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "noxbot.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        handlers.append(file_handler)

    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)
    return logging.getLogger("noxbot")


logger = _setup_logging()

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

    logger.info("Initializing database...")
    await init_db()
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

    # Mount routers (idempotent: safe if the entry point is re-entered)
    mount_routers(dp)

    logger.info("Routers mounted. Starting polling...")

    try:
        me = await bot.get_me()
    except Exception as e:
        # A bad token or no internet used to dump a 40-line traceback and leave
        # the aiohttp session unclosed.
        logger.error("اتصال به تلگرام برقرار نشد: %s", e)
        logger.error("BOT_TOKEN را در فایل .env و دسترسی به اینترنت را بررسی کنید.")
        await bot.session.close()
        scheduler.shutdown(wait=False)
        return
    logger.info("Bot started: @%s (%s)", me.username, me.id)

    try:
        await dp.start_polling(
            bot,
            allowed_updates=set(dp.resolve_used_update_types()).union({"my_chat_member"}),
            handle_signals=True,
        )
    finally:
        await dp.storage.close()
        await bot.session.close()
        scheduler.shutdown(wait=False)
        logger.info("Bot stopped.")


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        import asyncio

        asyncio.run(main())