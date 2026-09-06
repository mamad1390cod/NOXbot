"""Cart keyboards."""

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import back_button, home_button
from bot.models.cart import CartItem


def cart_item_keyboard(item: CartItem, page: int = 0) -> InlineKeyboardMarkup:
    """Build keyboard for a single cart item."""
    item_id = item.id
    keyboard = [
        [
            InlineKeyboardButton(text="➖", callback_data=f"cart:dec:{item_id}"),
            InlineKeyboardButton(text=f"تعداد: {item.quantity}", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"cart:inc:{item_id}"),
        ],
        [
            InlineKeyboardButton(text="🗑 حذف", callback_data=f"cart:del:{item_id}"),
        ],
        [
            back_button("menu:cart"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def cart_keyboard(items: Sequence[CartItem], page: int = 0) -> InlineKeyboardMarkup:
    """Build keyboard for cart listing."""
    keyboard = []
    for item in items:
        title = item.title
        keyboard.append(
            [InlineKeyboardButton(text=title, callback_data=f"cart:view:{item.id}")]
        )
    keyboard.append(
        [InlineKeyboardButton(text="🧹 پاک کردن سبد", callback_data="cart:clear")]
    )
    keyboard.append(
        [InlineKeyboardButton(text="💳 پرداخت", callback_data="cart:checkout")]
    )
    keyboard.append(
        [
            back_button("menu:home"),
            home_button("menu:home"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def checkout_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for checkout confirmation."""
    keyboard = [
        [
            InlineKeyboardButton(text="✅ تایید و پرداخت", callback_data="checkout:confirm"),
            InlineKeyboardButton(text="❌ انصراف", callback_data="menu:cart"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def confirm_cancel_keyboard(confirm_data: str, cancel_data: str) -> InlineKeyboardMarkup:
    """Generic confirm/cancel keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(text="✅ تایید", callback_data=confirm_data),
            InlineKeyboardButton(text="❌ انصراف", callback_data=cancel_data),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def wallet_checkout_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for wallet checkout (sufficient balance)."""
    keyboard = [
        [
            InlineKeyboardButton(text="💳 پرداخت از کیف پول", callback_data="checkout:confirm"),
        ],
        [
            InlineKeyboardButton(text="❌ انصراف", callback_data="menu:cart"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def insufficient_balance_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for insufficient balance (redirect to topup)."""
    keyboard = [
        [
            InlineKeyboardButton(text="💰 شارژ حساب", callback_data="tu:menu"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به سبد", callback_data="menu:cart"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)