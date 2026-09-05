"""Expands short ``ct:<hash>`` callback references back into real payloads.

Registered as an **outer** middleware on ``callback_query`` so the substitution
happens *before* aiogram resolves handler filters — handlers and their
``F.data.startswith(...)`` filters therefore never know a token was involved.

See ``bot/utils/callback_data.py`` for why oversized payloads exist at all.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject

from bot.utils.callback_data import expand, is_token

logger = logging.getLogger(__name__)

EXPIRED_MESSAGE = "⌛️ این دکمه منقضی شده است. لطفاً منو را دوباره باز کنید."


class CallbackTokenMiddleware(BaseMiddleware):
    """Swap ``ct:<hash>`` callback data for the payload it stands for."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, CallbackQuery) and is_token(event.data):
            payload = expand(event.data)
            if payload is None:
                logger.info("Unknown callback token %s (store evicted or restarted)", event.data)
                await event.answer(EXPIRED_MESSAGE, show_alert=True)
                return None
            bot = data.get("bot") or getattr(event, "bot", None)
            event = event.model_copy(update={"data": payload})
            if bot is not None:
                event = event.as_(bot)
            data["event_callback_query"] = event
        return await handler(event, data)
