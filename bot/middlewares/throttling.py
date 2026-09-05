"""Throttling middleware — flood protection that never fails silently.

Why this was rewritten
----------------------
The previous version allowed **5 events per 3 seconds per user** and *dropped*
everything above that with ``return None``: no reply, no callback answer, no
log line. Tapping through a menu (very normal in an admin panel: open → list →
item → back → next) instantly exceeded the budget, so buttons appeared random:
some worked, some did nothing, and the log only showed
``Update ... is handled`` because a dropped update still counts as handled.

The new behaviour:

* separate budgets for messages and callback queries — taps are cheap, message
  sends are not;
* the owner and active admins are exempt (panel navigation is bursty);
* a throttled callback query is *answered* with a short notice, so the client
  stops spinning and the user understands what happened;
* throttling is logged at DEBUG so it can be traced when investigating.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, types

from bot.config import get_settings

logger = logging.getLogger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    """Sliding-window rate limiter per user and event type."""

    def __init__(
        self,
        message_limit: int = 12,
        callback_limit: int = 30,
        time_window: float = 3.0,
        notice: str = "⏳ کمی آرام‌تر! چند لحظه صبر کنید.",
    ) -> None:
        self.message_limit = message_limit
        self.callback_limit = callback_limit
        self.time_window = time_window
        self.notice = notice
        self._records: dict[tuple[str, int], list[float]] = defaultdict(list)
        self._last_notice: dict[int, float] = {}

    def _limit_for(self, event: types.TelegramObject) -> tuple[str, int]:
        if isinstance(event, types.CallbackQuery):
            return "callback", self.callback_limit
        return "message", self.message_limit

    def _is_privileged(self, event: types.TelegramObject, data: dict[str, Any]) -> bool:
        user_id = getattr(getattr(event, "from_user", None), "id", None)
        if user_id is not None and user_id == get_settings().admin_id:
            return True
        # RbacMiddleware already resolved the permissions for this update.
        permissions = data.get("permissions")
        return bool(permissions)

    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None or self._is_privileged(event, data):
            return await handler(event, data)

        kind, limit = self._limit_for(event)
        key = (kind, user.id)
        now = time.time()
        records = [t for t in self._records[key] if now - t <= self.time_window]
        self._records[key] = records

        if len(records) >= limit:
            logger.debug("throttled %s from %s (%d in %.1fs)", kind, user.id, len(records), self.time_window)
            await self._notify(event, user.id, now)
            return None

        self._records[key].append(now)
        return await handler(event, data)

    async def _notify(self, event: types.TelegramObject, user_id: int, now: float) -> None:
        """Tell the user why nothing happened (at most once per window)."""
        try:
            if isinstance(event, types.CallbackQuery):
                # Always answer a callback: otherwise the button keeps spinning.
                await event.answer(self.notice, show_alert=False)
                return
            if now - self._last_notice.get(user_id, 0.0) >= self.time_window:
                self._last_notice[user_id] = now
                if isinstance(event, types.Message):
                    await event.answer(self.notice)
        except Exception:  # pragma: no cover - notifying must never break the flow
            logger.debug("could not deliver throttling notice", exc_info=True)
