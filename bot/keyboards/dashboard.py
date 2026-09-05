"""User dashboard ('My Account') keyboards."""

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import back_button, home_button


def dashboard_menu_keyboard() -> InlineKeyboardMarkup:
    """Main 'My Account' menu."""
    keyboard = [
        [InlineKeyboardButton(text="👤 پروفایل", callback_data="dash:profile")],
        [InlineKeyboardButton(text="📦 سفارش‌ها", callback_data="dash:orders")],
        [InlineKeyboardButton(text="💳 پرداخت‌ها", callback_data="dash:payments")],
        [InlineKeyboardButton(text="🎫 تیکت‌ها", callback_data="dash:tickets")],
        [InlineKeyboardButton(text="🎮 کاستوم‌ها / نتایج", callback_data="dash:tournaments")],
        [InlineKeyboardButton(text="⬇️ دانلودها", callback_data="dash:downloads")],
        [InlineKeyboardButton(text="💖 علاقه‌مندی‌ها", callback_data="dash:wishlist")],
        [InlineKeyboardButton(text="👛 کیف پول", callback_data="dash:wallet")],
        [InlineKeyboardButton(text="🎖 دستاوردها", callback_data="dash:achievements")],
        [InlineKeyboardButton(text="🎁 رفرال و کد", callback_data="dash:referral")],
        [home_button("menu:home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def dashboard_orders_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="⏳ جاری", callback_data="dash:orders:current")],
        [InlineKeyboardButton(text="🎉 تکمیل‌شده", callback_data="dash:orders:completed")],
        [InlineKeyboardButton(text="🚫 لغوشده", callback_data="dash:orders:cancelled")],
        [back_button("dash:menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def orders_list_keyboard(orders: Sequence, prefix: str, page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    keyboard = []
    for o in orders:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{o.status_label} {o.order_number}",
                callback_data=f"dash:{prefix}:view:{o.id}",
            )
        ])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"dash:{prefix}:page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"dash:{prefix}:page:{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([home_button()])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def wishlist_keyboard(items: Sequence) -> InlineKeyboardMarkup:
    keyboard = []
    for item in items:
        keyboard.append([
            InlineKeyboardButton(text=item.title, callback_data=f"dash:wishlist:view:{item.id}")
        ])
    keyboard.append([home_button()])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)