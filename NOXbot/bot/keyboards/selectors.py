"""Category picker keyboards — choose an existing category as inline buttons.

Used during product / config / custom creation so the admin always picks a
real category (or "بدون دسته") instead of typing a name that may silently
mismatch and leave the item uncategorized (invisible in that section).
"""

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import back_button, cancel_button


def category_picker_keyboard(
    categories: Sequence,
    *,
    callback_prefix: str,        # e.g. "pickcat_prod"
    empty: bool = True,          # show "بدون دسته" option
    back_to: str = "admin:products",
) -> InlineKeyboardMarkup:
    """Build inline buttons for each category + a 'no category' option."""
    keyboard = []
    for cat in categories:
        keyboard.append([
            InlineKeyboardButton(text=cat.name, callback_data=f"{callback_prefix}:{cat.id}")
        ])
    if empty:
        keyboard.append([
            InlineKeyboardButton(text="🚫 بدون دسته", callback_data=f"{callback_prefix}:none")
        ])
    keyboard.append([back_button(back_to)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)