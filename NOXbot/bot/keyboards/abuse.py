"""Admin anti-abuse panel keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import back_button


def abuse_menu_keyboard() -> InlineKeyboardMarkup:
    """Anti-abuse panel main menu."""
    keyboard = [
        [InlineKeyboardButton(text="📊 گزارش امنیتی", callback_data="abuse:report")],
        [InlineKeyboardButton(text="📜 رویدادهای اخیر", callback_data="abuse:events")],
        [
            InlineKeyboardButton(text="➖ لیست سیاه", callback_data="abuse:bl_list"),
            InlineKeyboardButton(text="➕ ‌لیست سفید", callback_data="abuse:wl_list"),
        ],
        [
            InlineKeyboardButton(text="📕 خروجی CSV", callback_data="abuse:export"),
            InlineKeyboardButton(text="🧹 پاک‌کردن شمارنده", callback_data="abuse:clear_counters"),
        ],
        [back_button("admin:panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def abuse_report_keyboard() -> InlineKeyboardMarkup:
    """Actions after the security report."""
    keyboard = [
        [InlineKeyboardButton(text="👤 مشاهده کاربر", callback_data="abuse:report_user")],
        [back_button("admin:abuse")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)