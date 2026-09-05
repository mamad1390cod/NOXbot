"""Loader module — creates and exposes the shared Bot, Dispatcher and BotServiceContainer.

Handlers import these singletons to access the bot, dispatcher, and services.
"""

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Telegram API limits
_bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

_dp = Dispatcher(storage=MemoryStorage())

# Guard so a second call cannot register every middleware twice (each event
# would then be processed twice: double DB writes, double throttling).
_middlewares_registered = False


def get_bot() -> Bot:
    """Return the shared Bot instance."""
    return _bot


def get_dispatcher() -> Dispatcher:
    """Return the shared Dispatcher instance."""
    return _dp


def register_middlewares() -> None:
    """Register global middlewares on the dispatcher.

    Order matters:

    * ``CallbackTokenMiddleware`` is an **outer** middleware — it rewrites
      short ``ct:<hash>`` callback data into the real payload *before* filters
      run, so handler filters see the full data.
    * ``UserContextMiddleware`` runs first among the inner ones and injects
      ``user``/``uow``, then maintenance/abuse/RBAC use those, then throttling.
    """
    global _middlewares_registered
    if _middlewares_registered:
        logger.debug("middlewares already registered — skipping")
        return

    from bot.middlewares import (
        AbuseMiddleware,
        CallbackTokenMiddleware,
        MaintenanceMiddleware,
        RbacMiddleware,
        ThrottlingMiddleware,
        UserContextMiddleware,
    )

    _dp.callback_query.outer_middleware(CallbackTokenMiddleware())

    for observer in (_dp.message, _dp.callback_query, _dp.my_chat_member):
        observer.middleware(UserContextMiddleware())
    for observer in (_dp.message, _dp.callback_query, _dp.my_chat_member):
        observer.middleware(MaintenanceMiddleware())
    for observer in (_dp.message, _dp.callback_query, _dp.my_chat_member):
        observer.middleware(AbuseMiddleware())
    for observer in (_dp.message, _dp.callback_query, _dp.my_chat_member):
        observer.middleware(RbacMiddleware())
    for observer in (_dp.message, _dp.callback_query):
        observer.middleware(ThrottlingMiddleware())

    _middlewares_registered = True


def mount_routers(dispatcher=None) -> None:
    """Attach the user and admin router trees to the dispatcher, exactly once.

    ``Dispatcher.include_router`` raises "Router is already attached" on a
    second call, so mounting is guarded here instead of being duplicated at
    every call site (main.py, tests, scripts).
    """
    from bot.handlers import admin_router, user_router

    dp = dispatcher or _dp
    for router in (user_router, admin_router):
        if router.parent_router is None:
            dp.include_router(router)
        elif router.parent_router is not dp:
            raise RuntimeError(
                f"Router {router.name!r} is attached to {router.parent_router.name!r}, "
                "not to this dispatcher — check for a second composition root."
            )
