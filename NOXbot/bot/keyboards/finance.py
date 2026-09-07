"""Financial dashboard keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import back_button


def finance_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="🔍 فیلتر", callback_data="fin:filter")],
        [InlineKeyboardButton(text="🧹 پاک کردن فیلتر", callback_data="fin:clear")],
        [
            InlineKeyboardButton(text="📄 CSV", callback_data="fin:export:csv"),
            InlineKeyboardButton(text="📊 Excel", callback_data="fin:export:excel"),
        ],
        [
            InlineKeyboardButton(text="📕 PDF", callback_data="fin:export:pdf"),
            InlineKeyboardButton(text="📈 نمودار", callback_data="fin:export:chart"),
        ],
        [InlineKeyboardButton(text="📦 خروجی کامل", callback_data="fin:export:all")],
        [back_button("admin:panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def finance_filter_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="📅 بازه تاریخ", callback_data="fin:f_date")],
        [InlineKeyboardButton(text="👤 کاربر", callback_data="fin:f_user")],
        [InlineKeyboardButton(text="📦 محصول", callback_data="fin:f_product")],
        [InlineKeyboardButton(text="🏷 دسته", callback_data="fin:f_category")],
        [InlineKeyboardButton(text="💳 وضعیت پرداخت", callback_data="fin:f_payment")],
        [InlineKeyboardButton(text="👨💼 ادمین", callback_data="fin:f_admin")],
        [InlineKeyboardButton(text="🔍 اعمال فیلتر", callback_data="fin:home")],
        [back_button("admin:finance")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)