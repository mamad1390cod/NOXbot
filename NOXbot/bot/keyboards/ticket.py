"""Ticket keyboards."""

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import back_button, home_button


def ticket_menu_keyboard() -> InlineKeyboardMarkup:
    """Build the support ticket menu."""
    keyboard = [
        [InlineKeyboardButton(text="📝 ثبت تیکت جدید", callback_data="ticket:new")],
        [InlineKeyboardButton(text="📋 تیکت‌های من", callback_data="ticket:list")],
        [back_button("menu:home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def ticket_categories_keyboard(categories: Sequence) -> InlineKeyboardMarkup:
    """Build keyboard for ticket categories."""
    keyboard = []
    for cat in categories:
        label = f"{cat.name}"
        keyboard.append(
            [InlineKeyboardButton(text=label, callback_data=f"tick_cat:{cat.id}")]
        )
    keyboard.append([InlineKeyboardButton(text="❌ انصراف", callback_data="menu:support")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def ticket_detail_keyboard(ticket_id: str, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Build keyboard for a single ticket."""
    keyboard = [
        [
            InlineKeyboardButton(text="✍️ پاسخ", callback_data=f"ticket:reply:{ticket_id}"),
            InlineKeyboardButton(text="✅ تکمیل شد", callback_data=f"ticket:close:{ticket_id}"),
        ]
    ]
    if is_admin:
        keyboard.append(
            [InlineKeyboardButton(text="🗑 حذف", callback_data=f"ticket:admin_del:{ticket_id}")]
        )
    keyboard.append([back_button("menu:support")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def my_tickets_keyboard(tickets: Sequence, page: int = 0) -> InlineKeyboardMarkup:
    """Build keyboard for user's ticket list."""
    keyboard = []
    for t in tickets:
        status_icon = "🟢" if t.status.value in ("open", "in_progress", "waiting_user") else "🔴"
        keyboard.append(
            [InlineKeyboardButton(text=f"{status_icon} {t.subject}", callback_data=f"ticket:view:{t.id}")]
        )
    keyboard.append([back_button("menu:support")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)