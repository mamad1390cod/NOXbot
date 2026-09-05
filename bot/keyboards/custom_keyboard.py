"""Custom tournament keyboards."""

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import back_button, home_button
from bot.models.custom import Custom
from bot.texts import CONFIRM, CANCEL


def custom_panel_keyboard(customs: Sequence[Custom]) -> InlineKeyboardMarkup:
    """Build keyboard for a list of customs (user side)."""
    keyboard = []
    for custom in customs:
        icon = "🟢" if custom.can_register else "🔴"
        keyboard.append(
            [InlineKeyboardButton(text=f"{icon} {custom.title}", callback_data=f"custom_sel:{custom.id}")]
        )
    keyboard.append([back_button("menu:customs")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def custom_detail_keyboard(custom_id: str, is_registered: bool = False) -> InlineKeyboardMarkup:
    """Build keyboard for a single custom."""
    keyboard = []
    if not is_registered:
        keyboard.append(
            [InlineKeyboardButton(text="➕ افزودن", callback_data=f"custom_add:{custom_id}")]
        )
    else:
        keyboard.append(
            [InlineKeyboardButton(text="✅ ثبت‌نام شده", callback_data="noop")]
        )
    keyboard.append(
        [InlineKeyboardButton(text="🎯 سبد کاستوم", callback_data="menu:custom_cart")]
    )
    keyboard.append([back_button("menu:customs")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def custom_registration_keyboard(custom_id: str) -> InlineKeyboardMarkup:
    """Build keyboard for custom registration confirmation."""
    keyboard = [
        [
            InlineKeyboardButton(text=CONFIRM(), callback_data=f"reg_confirm:{custom_id}"),
            InlineKeyboardButton(text=CANCEL(), callback_data="menu:custom_cart"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def custom_cart_keyboard(items: Sequence) -> InlineKeyboardMarkup:
    """Build keyboard for the custom cart."""
    keyboard = []
    for item in items:
        title = item.custom.title if item.custom else "نامشخص"
        keyboard.append(
            [InlineKeyboardButton(text=title, callback_data=f"ccart_view:{item.id}")]
        )
    keyboard.append(
        [InlineKeyboardButton(text="🧹 پاک کردن", callback_data="customcart:clear")]
    )
    keyboard.append(
        [InlineKeyboardButton(text="🎯 ثبت نهایی", callback_data="customcart:register")]
    )
    keyboard.append([home_button("menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)