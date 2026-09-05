"""Anti-abuse middleware — blocks blacklisted/suspended users, detects floods.

Runs after UserContext (user/uow present) and Maintenance. It:
- skips owner, admins, and whitelisted users,
- drops blacklisted / suspended (temp or perm) users while alerting once,
- detects message flooding via a rolling window and applies FLOOD events which
  escalate to a mute through the AntiAbuseService thresholds.
"""

import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, types
from aiogram.types import TelegramObject

from bot.config import get_settings
from bot.models.abuse import AbuseType
from bot.services.abuse import AntiAbuseService
from bot.services.rbac import RbacService
from bot.services.settings import SettingsService

logger = logging.getLogger(__name__)


class AbuseMiddleware(BaseMiddleware):
    """Persistently enforce anti-abuse rules for non-privileged users."""

    # Flood window: >FLOOD_LIMIT messages in FLOOD_WINDOW seconds => MESSAGE_FLOOD.
    FLOOD_WINDOW = 5.0
    FLOOD_LIMIT = 12

    def __init__(self) -> None:
        super().__init__()
        # in-memory flood tracking (window per user); DB persists the outcome.
        self._flood: dict[int, deque[float]] = defaultdict(deque)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        uow = data.get("uow")
        if user is None or uow is None:
            return await handler(event, data)

        # Privileged users bypass abuse enforcement.
        try:
            rbac = RbacService(uow)
            if rbac.is_owner(user) or await rbac.is_admin(user):
                return await handler(event, data)
        except Exception:
            # Fail closed: if RBAC cannot be read, treat the user as ordinary.
            logger.debug("privilege check failed; enforcing abuse rules", exc_info=True)

        if user.whitelisted:
            return await handler(event, data)

        abuse = AntiAbuseService(uow)
        try:
            # Blocked check: blacklist / permanent ban / suspension.
            status = await self._current_disposition(abuse, user)
            if status:
                await self._reply_blocked(event, status, user)
                return None

            # Flood detection.
            is_flood = self._track_flood(user)
            if is_flood:
                await abuse.record(AbuseType.MESSAGE_FLOOD, user=user, source="flood")
        except Exception as e:
            logger.exception("AbuseMiddleware error: %s", e)

        return await handler(event, data)

    async def _current_disposition(self, abuse: AntiAbuseService, user) -> str | None:
        if user.blacklisted:
            return "blacklist"
        if user.is_banned:
            return "ban"
        if user.abuse_suspended_until and user.abuse_suspended_until > datetime.now(timezone.utc):
            return "suspend"
        return None

    def _track_flood(self, user) -> bool:
        now = time.time()
        dq = self._flood[user.id]
        dq.append(now)
        while dq and now - dq[0] > self.FLOOD_WINDOW:
            dq.popleft()
        return len(dq) > self.FLOOD_LIMIT

    async def _reply_blocked(self, event, status: str, user) -> None:
        target = None
        if isinstance(event, types.Message):
            target = event
        elif isinstance(event, types.CallbackQuery) and event.message:
            target = event.message
        if target is None:
            return
        msgs = {
            "blacklist": "🚫 شما در لیست سیاه قرار دارید.",
            "ban": "🚫 شما مسدود شده‌اید.",
            "suspend": "⏸ حساب شما به‌طور موقت مسدود شده است.",
        }
        try:
            await target.answer(msgs.get(status, "🚫 دسترسی مسدود است."), parse_mode="HTML")
        except Exception as e:
            logger.debug("blocked reply failed: %s", e)