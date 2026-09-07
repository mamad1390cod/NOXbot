"""Safe message-editing helpers.

Telegram rejects ``edit_text`` when the new content + reply markup are
identical to the current ones ("message is not modified: Bad Request"). These
helpers swallow that specific error so buttons that re-render the same state
don't crash the handler.
"""

import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


async def safe_edit_text(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str = "HTML",
) -> bool:
    """Edit a callback's message, ignoring the 'not modified' Telegram error.

    Returns True if the edit succeeded (or was a no-op), False only on other
    Telegram errors.
    """
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e) or "not modified" in str(e):
            return True  # already identical — nothing to do
        logger.warning("edit_text failed: %s", e)
        return False
    except Exception as e:
        logger.warning("edit_text error: %s", e)
        return False


async def safe_edit_caption(
    callback: CallbackQuery,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """Like safe_edit_text but for media messages (changes caption only)."""
    try:
        await callback.message.edit_caption(caption=caption, reply_markup=reply_markup)
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e) or "not modified" in str(e):
            return True
        logger.warning("edit_caption failed: %s", e)
        return False
    except Exception as e:
        logger.warning("edit_caption error: %s", e)
        return False