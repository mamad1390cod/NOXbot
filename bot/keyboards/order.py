"""Order keyboards — user order tracking + admin order management."""

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import back_button, home_button
from bot.models.order import Order, OrderStatus, STATUS_LABELS
from bot.utils.format import format_price


# --- User side ------------------------------------------------------------ #
def my_orders_keyboard(orders: Sequence[Order], page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    """Keyboard for a user's order list."""
    keyboard = []
    for order in orders:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{order.status_label} {order.order_number} — {format_price(order.final_amount)}",
                callback_data=f"orders:view:{order.id}",
            )
        ])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"orders:page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"orders:page:{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([home_button("menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def user_order_detail_keyboard(order: Order) -> InlineKeyboardMarkup:
    """Keyboard for a single order (user view)."""
    keyboard = []
    if order.can_cancel:
        keyboard.append([
            InlineKeyboardButton(text="🚫 لغو سفارش", callback_data=f"orders:cancel:{order.id}")
        ])
    keyboard.append([
        InlineKeyboardButton(text="📨 پشتیبانی", callback_data="menu:support"),
        home_button("menu:home"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# --- Admin side ----------------------------------------------------------- #
def admin_orders_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin orders section menu."""
    keyboard = [
        [
            InlineKeyboardButton(text="📋 همه سفارش‌ها", callback_data="aorder:list"),
            InlineKeyboardButton(text="⏳ در انتظار بررسی", callback_data="aorder:pending"),
        ],
        [
            InlineKeyboardButton(text="🔍 فیلتر", callback_data="aorder:filter"),
            InlineKeyboardButton(text="🔎 جستجوی شماره", callback_data="aorder:search"),
        ],
        [back_button("admin:panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_order_list_keyboard(
    orders: Sequence[Order],
    page: int = 0,
    total_pages: int = 1,
    filter_tag: str = "",
) -> InlineKeyboardMarkup:
    """Keyboard for an admin order list."""
    keyboard = []
    for order in orders:
        label = (
            f"{order.status_label} {order.order_number} — "
            f"{format_price(order.final_amount)} تومان"
        )
        if order.user and order.user.username:
            label += f" (@{order.user.username})"
        keyboard.append([
            InlineKeyboardButton(text=label, callback_data=f"aorder:view:{order.id}")
        ])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"aorder:page:{page - 1}:{filter_tag}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"aorder:page:{page + 1}:{filter_tag}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([back_button("admin:orders")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_order_detail_keyboard(order: Order) -> InlineKeyboardMarkup:
    """Keyboard for a single order (admin view) — legal status actions only."""
    keyboard = []

    status = order.status
    if status == OrderStatus.WAITING_PAYMENT:
        pass  # nothing admin can do before receipt
    elif status == OrderStatus.PAYMENT_UPLOADED:
        keyboard.append([
            InlineKeyboardButton(text="🕵️ بررسی رسید", callback_data=f"aorder:review:{order.id}"),
            InlineKeyboardButton(text="🚫 لغو", callback_data=f"aorder:cancel:{order.id}"),
        ])
    elif status == OrderStatus.PAYMENT_REVIEWING:
        keyboard.append([
            InlineKeyboardButton(text="✅ تایید پرداخت", callback_data=f"aorder:approve:{order.id}"),
            InlineKeyboardButton(text="❌ رد", callback_data=f"aorder:reject:{order.id}"),
        ])
    elif status == OrderStatus.APPROVED:
        keyboard.append([
            InlineKeyboardButton(text="🔧 شروع آماده‌سازی", callback_data=f"aorder:prepare:{order.id}"),
            InlineKeyboardButton(text="💰 بازگشت وجه", callback_data=f"aorder:refund:{order.id}"),
        ])
    elif status == OrderStatus.PREPARING:
        keyboard.append([
            InlineKeyboardButton(text="📦 ارسال", callback_data=f"aorder:deliver:{order.id}"),
            InlineKeyboardButton(text="💰 بازگشت وجه", callback_data=f"aorder:refund:{order.id}"),
        ])
    elif status == OrderStatus.DELIVERED:
        keyboard.append([
            InlineKeyboardButton(text="🎉 تکمیل سفارش", callback_data=f"aorder:complete:{order.id}"),
            InlineKeyboardButton(text="💰 بازگشت وجه", callback_data=f"aorder:refund:{order.id}"),
        ])

    # Notes / ticket links (always available).
    keyboard.append([
        InlineKeyboardButton(text="📝 یادداشت", callback_data=f"aorder:note:{order.id}"),
        InlineKeyboardButton(text="🎫 لینک تیکت", callback_data=f"aorder:ticket:{order.id}"),
    ])
    keyboard.append([back_button("aorder:list")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_order_filter_keyboard() -> InlineKeyboardMarkup:
    """Admin order filter builder."""
    keyboard = [
        [InlineKeyboardButton(text="📊 وضعیت", callback_data="aorder:f_status")],
        [InlineKeyboardButton(text="👤 کاربر", callback_data="aorder:f_user")],
        [InlineKeyboardButton(text="🧾 شماره سفارش", callback_data="aorder:f_number")],
        [InlineKeyboardButton(text="💰 محدوده قیمت", callback_data="aorder:f_price")],
        [InlineKeyboardButton(text="💳 وضعیت پرداخت", callback_data="aorder:f_payment")],
        [InlineKeyboardButton(text="📅 محدوده تاریخ", callback_data="aorder:f_date")],
        [InlineKeyboardButton(text="🧹 پاک کردن فیلتر", callback_data="aorder:f_clear")],
        [InlineKeyboardButton(text="🔍 اعمال فیلتر", callback_data="aorder:list")],
        [back_button("admin:orders")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def order_status_picker() -> InlineKeyboardMarkup:
    """Pick a status for filtering."""
    keyboard = []
    for status in OrderStatus:
        if status == OrderStatus.PENDING:
            continue  # legacy/transient
        keyboard.append([
            InlineKeyboardButton(text=status.label, callback_data=f"aorder:fs_status:{status.value}")
        ])
    keyboard.append([back_button("aorder:filter")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def order_payment_status_picker() -> InlineKeyboardMarkup:
    """Pick a payment status for filtering."""
    from bot.models.payment import PaymentStatus
    keyboard = []
    for status in PaymentStatus:
        keyboard.append([
            InlineKeyboardButton(text=status.value, callback_data=f"aorder:fs_payment:{status.value}")
        ])
    keyboard.append([back_button("aorder:filter")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def order_confirm_action(callback_prefix: str, order_id: str) -> InlineKeyboardMarkup:
    """Generic confirm/cancel for a single admin action."""
    keyboard = [
        [
            InlineKeyboardButton(text="⚠️ تایید", callback_data=f"{callback_prefix}:{order_id}"),
            InlineKeyboardButton(text="❌ انصراف", callback_data=f"aorder:view:{order_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)