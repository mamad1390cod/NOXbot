"""Safe message-editing helpers.

Editing a Telegram message can fail for several perfectly normal reasons, and
each failure used to leave the user staring at an unchanged screen — the
classic "this button does nothing" report:

* ``message is not modified`` — the new content equals the old one (harmless);
* ``there is no text in the message to edit`` — the current message is a photo
  or video (product image, custom banner, receipt), so only its *caption* can
  be edited;
* ``message can't be edited`` / ``MESSAGE_ID_INVALID`` — the message is too old
  or was sent by someone else.

These helpers degrade gracefully: edit text → edit caption → send a fresh
message, so a tap always produces a visible result.
"""

from __future__ import annotations

import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

_NOT_MODIFIED = "not modified"
_NO_TEXT_MARKERS = (
    "no text in the message to edit",
    "message to edit not found",
    "message can't be edited",
    "MESSAGE_ID_INVALID",
)


async def safe_edit_text(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str = "HTML",
) -> bool:
    """Show ``text`` in place of the callback's message.

    Returns True when the user ends up seeing the new content (edited or newly
    sent), False only when nothing could be delivered.
    """
    message = callback.message
    if message is None:  # inline mode / message too old to be attached
        return False

    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except TelegramBadRequest as e:
        error = str(e)
        if _NOT_MODIFIED in error:
            return True  # already identical — nothing to do
        if any(marker in error for marker in _NO_TEXT_MARKERS):
            return await _fallback(callback, text, reply_markup, parse_mode, error)
        logger.warning("edit_text failed: %s", e)
        return await _fallback(callback, text, reply_markup, parse_mode, error)
    except Exception as e:  # network/unknown — still try to show something
        logger.warning("edit_text error: %s", e)
        return await _fallback(callback, text, reply_markup, parse_mode, str(e))


async def _fallback(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None,
    parse_mode: str,
    original_error: str,
) -> bool:
    """Media message → edit the caption; anything else → send a new message."""
    message = callback.message
    if message is None:
        return False

    if message.caption is not None or message.photo or message.video or message.document:
        try:
            await message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
            return True
        except TelegramBadRequest as e:
            if _NOT_MODIFIED in str(e):
                return True
            logger.debug("edit_caption fallback failed: %s", e)
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("edit_caption fallback error: %s", e)

    try:
        await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except Exception as e:
        logger.warning("could not deliver update (%s); original error: %s", e, original_error)
        return False


async def safe_edit_caption(
    callback: CallbackQuery,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """Like :func:`safe_edit_text` but for media messages (caption only)."""
    message = callback.message
    if message is None:
        return False
    try:
        await message.edit_caption(caption=caption, reply_markup=reply_markup)
        return True
    except TelegramBadRequest as e:
        if _NOT_MODIFIED in str(e):
            return True
        logger.warning("edit_caption failed: %s", e)
        return await _fallback(callback, caption, reply_markup, "HTML", str(e))
    except Exception as e:
        logger.warning("edit_caption error: %s", e)
        return await _fallback(callback, caption, reply_markup, "HTML", str(e))
