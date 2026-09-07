"""Wallet top-up keyboards."""

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import back_button, home_button
from bot.models.topup import TopUpAmount, TopUpRequest, TopUpStatus
from bot.utils.format import format_price


def topup_amounts_keyboard(amounts: Sequence[TopUpAmount]) -> InlineKeyboardMarkup:
    """Show available top-up amounts as buttons."""
    keyboard = []
    for a in amounts:
        label = a.label or f"💰 {format_price(a.amount)} تومان"
        keyboard.append([
            InlineKeyboardButton(text=label, callback_data=f"tu:amt:{a.id}")
        ])
    keyboard.append([
        InlineKeyboardButton(text="✏️ مبلغ دلخواه", callback_data="tu:custom_amt")
    ])
    keyboard.append([back_button("dash:menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def topup_method_keyboard(amount: int) -> InlineKeyboardMarkup:
    """Show payment method selection."""
    keyboard = [
        [InlineKeyboardButton(text="💳 کارت به کارت", callback_data="tu:m:card")],
        [InlineKeyboardButton(text="₿ ارز دیجیتال (غیرفعال)", callback_data="tu:m:crypto")],
        [back_button("tu:menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def topup_invoice_keyboard(amount: int) -> InlineKeyboardMarkup:
    """Confirm/cancel invoice before showing card info."""
    keyboard = [
        [
            InlineKeyboardButton(text="✅ تأیید و ادامه", callback_data="tu:confirm"),
            InlineKeyboardButton(text="❌ انصراف", callback_data="tu:menu"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ── Admin keyboards ──────────────────────────────────────────────────────── #

def admin_topup_menu_keyboard(stats: dict) -> InlineKeyboardMarkup:
    """Admin top-up management menu."""
    keyboard = [
        [
            InlineKeyboardButton(
                text=f"⏳ در انتظار ({stats.get('pending', 0) + stats.get('waiting_receipt', 0)})",
                callback_data="atu:pending",
            ),
        ],
        [
            InlineKeyboardButton(text="✅ تأیید شده", callback_data="atu:approved"),
            InlineKeyboardButton(text="❌ رد شده", callback_data="atu:rejected"),
        ],
        [InlineKeyboardButton(text="📋 همه", callback_data="atu:all")],
        [InlineKeyboardButton(text="🔍 جستجوی کد پیگیری", callback_data="atu:search")],
        [InlineKeyboardButton(text="💰 شارژ دستی کاربر", callback_data="atu:credit")],
        [InlineKeyboardButton(text="➖ کسر موجودی کاربر", callback_data="atu:debit")],
        [InlineKeyboardButton(text="🏷 مبلغ‌های شارژ", callback_data="atu:amounts")],
        [back_button("admin:panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_topup_list_keyboard(requests: Sequence[TopUpRequest]) -> InlineKeyboardMarkup:
    """List of top-up requests for admin."""
    keyboard = []
    for r in requests:
        icon = {
            TopUpStatus.PENDING: "⏳",
            TopUpStatus.WAITING_FOR_RECEIPT: "📤",
            TopUpStatus.UNDER_REVIEW: "🔍",
            TopUpStatus.WAITING_FOR_NEW_RECEIPT: "🔄",
            TopUpStatus.APPROVED: "✅",
            TopUpStatus.REJECTED: "❌",
        }.get(r.status, "▫️")
        user_label = r.user.display_name if r.user else "?"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{icon} {r.tracking_code} — {format_price(r.amount)} — {user_label}",
                callback_data=f"atu:view:{r.id[:8]}",
            )
        ])
    keyboard.append([back_button("atu:menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_topup_detail_keyboard(request: TopUpRequest) -> InlineKeyboardMarkup:
    """Admin actions for a single top-up request."""
    keyboard = []
    if not request.is_finalized:
        keyboard.append([
            InlineKeyboardButton(text="✅ تأیید پرداخت", callback_data=f"atu:ok:{request.id[:8]}"),
            InlineKeyboardButton(text="❌ رد", callback_data=f"atu:no:{request.id[:8]}"),
        ])
        keyboard.append([
            InlineKeyboardButton(text="🔄 درخواست رسید مجدد", callback_data=f"atu:rs:{request.id[:8]}"),
        ])
    keyboard.append([back_button("atu:menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_topup_amounts_keyboard(amounts: Sequence[TopUpAmount]) -> InlineKeyboardMarkup:
    """Admin management of top-up amounts."""
    keyboard = []
    for a in amounts:
        icon = "🟢" if a.is_active else "🔴"
        label = a.label or f"{format_price(a.amount)} تومان"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{icon} {label}",
                callback_data=f"atua:view:{a.id[:8]}",
            )
        ])
    keyboard.append([
        InlineKeyboardButton(text="➕ افزودن مبلغ", callback_data="atua:add"),
    ])
    keyboard.append([back_button("atu:menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_topup_amount_detail_keyboard(amount_id: str, is_active: bool) -> InlineKeyboardMarkup:
    """Admin actions for a single top-up amount."""
    toggle_text = "🔴 غیرفعال" if is_active else "🟢 فعال"
    keyboard = [
        [
            InlineKeyboardButton(text="✏️ ویرایش مبلغ", callback_data=f"atua:edit:{amount_id[:8]}"),
            InlineKeyboardButton(text=toggle_text, callback_data=f"atua:tog:{amount_id[:8]}"),
        ],
        [
            InlineKeyboardButton(text="🗑 حذف", callback_data=f"atua:del:{amount_id[:8]}"),
        ],
        [back_button("atu:amounts")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
