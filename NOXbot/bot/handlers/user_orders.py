"""User-facing order tracking handlers."""

import logging

from aiogram import F, Router, types
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import home_button, single_button_kb
from bot.keyboards.order import my_orders_keyboard, user_order_detail_keyboard
from bot.models.order import Order, OrderStatus
from bot.models.user import User
from bot.services.notification import NotificationService
from bot.services.order import OrderService
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="user_orders")
logger = logging.getLogger(__name__)

ITEMS_PER_PAGE = 8


def _fmt_dt(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "—"


def _user_order_text(order: Order) -> str:
    lines = [
        f"🎯 <b>سفارش {order.order_number}</b>",
        f"📊 وضعیت: {order.status_label}",
        "",
        "🛒 <b>آیتم‌ها:</b>",
    ]
    for item in order.items:
        lines.append(f"• {item.product_title} × {item.quantity} = {format_price(item.total_price)} تومان")
    lines += [
        "",
        f"🧾 مبلغ نهایی: <b>{format_price(order.final_amount)} تومان</b>",
        "",
        "🕒 <b>زمان‌ها:</b>",
        f"📅 ثبت: {_fmt_dt(order.created_at)}",
        f"📤 رسید: {_fmt_dt(order.payment_uploaded_at)}",
        f"✅ تایید: {_fmt_dt(order.approved_at)}",
        f"🔧 آماده‌سازی: {_fmt_dt(order.preparing_at)}",
        f"📦 ارسال: {_fmt_dt(order.delivered_at)}",
        f"🎉 تکمیل: {_fmt_dt(order.completed_at)}",
    ]
    if order.estimated_delivery_at:
        lines.append(f"⏰ زمان تخمینی ارسال: {_fmt_dt(order.estimated_delivery_at)}")
    return "\n".join(lines)


@router.callback_query(F.data == "orders:list")
async def cb_orders_list(callback: CallbackQuery, uow, user: User) -> None:
    """Show the user's orders with pagination."""
    await _show_orders(callback, uow, user, 0)


async def _show_orders(callback: CallbackQuery, uow, user: User, page: int) -> None:
    os = OrderService(uow)
    orders = await os.get_user_orders(user.id, offset=page * ITEMS_PER_PAGE, limit=ITEMS_PER_PAGE)
    total = await os.count_user_orders(user.id)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    if not orders:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[home_button("menu:home")]])
        await safe_edit_text(callback, 
            "📦 هنوز سفارشی ثبت نکرده‌اید.\nاز منوی اصلی خرید کنید.",
            reply_markup=kb,
        )
        await callback.answer()
        return

    await safe_edit_text(callback, 
        "📦 <b>سفارش‌های من</b>",
        reply_markup=my_orders_keyboard(orders, page, total_pages),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("orders:page:"))
async def cb_orders_page(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("داده‌های نامعتبر", show_alert=True)
        return
    page = int(parts[2])
    await _show_orders(callback, uow, user, page)


@router.callback_query(F.data.startswith("orders:view:"))
async def cb_order_view(callback: CallbackQuery, uow, user: User, bot) -> None:
    """Show a single order's details + status timeline."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("سفارش یافت نشد", show_alert=True)
        return
    order_id = parts[2]
    os = OrderService(uow)
    order = await os.get_order(order_id)
    if not order:
        await callback.answer("سفارش یافت نشد", show_alert=True)
        return
    if order.user_id != user.id:
        await callback.answer("این سفارش متعلق به شما نیست", show_alert=True)
        return
    await safe_edit_text(callback, 
        _user_order_text(order),
        reply_markup=user_order_detail_keyboard(order),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("orders:cancel:"))
async def cb_order_cancel(callback: CallbackQuery, uow, user: User) -> None:
    """User cancels an order before payment."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("سفارش یافت نشد", show_alert=True)
        return
    order_id = parts[2]
    os = OrderService(uow, notifier=NotificationService(callback.bot, uow))
    order = await os.get_order(order_id)
    if order is None:
        await callback.answer("سفارش یافت نشد", show_alert=True)
        return
    if order.user_id != user.id:
        await callback.answer("سفارش متعلق به شما نیست", show_alert=True)
        return
    if not order.can_cancel:
        await callback.answer("این سفارش قابل لغو نیست", show_alert=True)
        return
    await os.cancel_order(order, admin=user, reason="لغو توسط کاربر")
    await uow.flush()

    await uow.commit()
    await callback.answer("سفارش لغو شد")
    await safe_edit_text(callback, "سفارش لغو شد.", reply_markup=single_button_kb(home_button("menu:home")))