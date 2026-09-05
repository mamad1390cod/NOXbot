"""Notification service — sends updates to admins."""

import html
import logging
from typing import Sequence

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardMarkup

from bot.config import get_settings
from bot.models.user import User
from bot.database.uow import UnitOfWork

logger = logging.getLogger(__name__)


def escape_html(text: str) -> str:
    """Escape text for safe HTML parsing mode."""
    return html.escape(str(text), quote=False)


class NotificationService:
    """Service for sending notifications and admin alerts."""

    def __init__(self, bot: Bot, uow: UnitOfWork) -> None:
        self.bot = bot
        self.uow = uow

    async def _admin_ids(self) -> list[int]:
        """Get list of admin telegram IDs."""
        settings = get_settings()
        ids = {settings.admin_id}
        # Extra admins from DB settings
        try:
            extra = await self.uow.settings.get_value("admin_ids", "")
            if extra:
                for part in extra.replace("[", "").replace("]", "").split(","):
                    part = part.strip()
                    if part.isdigit():
                        ids.add(int(part))
        except Exception:
            logger.debug("could not parse admin_ids setting", exc_info=True)
        return list(ids)

    async def send_to_admins(
        self,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        parse_mode: str = "HTML",
        photo: str | FSInputFile | None = None,
        caption: str | None = None,
    ) -> None:
        """Send a message to all admins."""
        for admin_id in await self._admin_ids():
            try:
                if photo:
                    await self.bot.send_photo(
                        admin_id,
                        photo=photo,
                        caption=caption or text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode,
                    )
                else:
                    await self.bot.send_message(
                        admin_id,
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode,
                    )
            except Exception as e:
                logger.warning("Failed to notify admin %s: %s", admin_id, e)

    def _user_block(self, user: User) -> str:
        """Build a user info block for notifications."""
        username = f"@{user.username}" if user.username else "ندارد"
        return (
            f"🆔 آیدی تلگرام: <code>{user.telegram_id}</code>\n"
            f"🆔 چت آیدی: <code>{user.telegram_id}</code>\n"
            f"👤 نام کاربری: {escape_html(username)}\n"
            f"👤 نام: {escape_html(user.first_name or '')} {escape_html(user.last_name or '')}\n"
        )

    async def notify_admin_request(
        self,
        request_type: str,
        user: User,
        details: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        photo: str | FSInputFile | None = None,
    ) -> None:
        """Notify admins about a user request with full context."""
        text = (
            f"📩 <b>درخواست جدید: {request_type}</b>\n\n"
            f"{self._user_block(user)}\n"
            f"📅 تاریخ: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}\n"
            f"🕒 زمان: {__import__('datetime').datetime.now().strftime('%H:%M:%S')}\n"
            f"🏷 نوع درخواست: {request_type}\n\n"
            f"📋 جزئیات:\n{details}"
        )
        await self.send_to_admins(
            text=text,
            reply_markup=reply_markup,
            photo=photo,
        )

    async def notify_user(self, user_id: int, text: str, reply_markup: InlineKeyboardMarkup | None = None, parse_mode: str = "HTML") -> None:
        """Send a message to a user, silently failing if blocked."""
        try:
            await self.bot.send_message(user_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            logger.warning("Failed to notify user %s: %s", user_id, e)

    async def broadcast(self, text: str) -> int:
        """Send a message to all users (returns success count)."""
        settings = get_settings()
        users: Sequence[User] = await self.uow.users.get_all(limit=10000)
        success = 0
        for user in users:
            if user.is_banned or user.telegram_id == settings.admin_id:
                continue
            try:
                await self.bot.send_message(user.telegram_id, text=text, parse_mode="HTML")
                success += 1
            except Exception as e:
                # Users who blocked the bot are expected here; log for stats.
                logger.debug("broadcast to %s failed: %s", user.telegram_id, e)
        return success

    async def broadcast_with_photo(self, photo: FSInputFile | str, caption: str = "") -> int:
        """Broadcast a photo to all users."""
        users: Sequence[User] = await self.uow.users.get_all(limit=10000)
        success = 0
        for user in users:
            if user.is_banned:
                continue
            try:
                await self.bot.send_photo(user.telegram_id, photo=photo, caption=caption, parse_mode="HTML")
                success += 1
            except Exception as e:
                # Users who blocked the bot are expected here; log for stats.
                logger.debug("broadcast to %s failed: %s", user.telegram_id, e)
        return success