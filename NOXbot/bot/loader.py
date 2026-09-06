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


def get_bot() -> Bot:
    """Return the shared Bot instance."""
    return _bot


def get_dispatcher() -> Dispatcher:
    """Return the shared Dispatcher instance."""
    return _dp


def register_middlewares() -> None:
    """Register global middlewares on the dispatcher.

    Order matters: 
    1. RequestContextMiddleware (sets request_id and user context for logging)
    2. UserContextMiddleware (injects user/uow)
    3. MaintenanceMiddleware
    4. AbuseMiddleware
    5. RbacMiddleware (uses user context to inject permissions)
    6. ThrottlingMiddleware
    """
    from bot.middlewares import (
        ThrottlingMiddleware,
        UserContextMiddleware,
        RbacMiddleware,
        MaintenanceMiddleware,
        AbuseMiddleware,
    )
    from bot.middlewares.request_context import RequestContextMiddleware

    # Request context middleware (for logging) - runs first
    _dp.update.outer_middleware(RequestContextMiddleware())
    
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