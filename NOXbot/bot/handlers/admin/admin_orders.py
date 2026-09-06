"""Admin order management handlers — full lifecycle control."""

import json
import logging
from datetime import datetime, timezone

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import back_button, single_button_kb
from bot.keyboards.order import (
    admin_order_detail_keyboard,
    admin_order_filter_keyboard,
    admin_order_list_keyboard,
    admin_orders_menu_keyboard,
    order_confirm_action,
    order_payment_status_picker,
    order_status_picker,
)
from bot.models.log import LogAction
from bot.models.order import Order, OrderStatus
from bot.models.user import User
from bot.services.admin import AdminService
from bot.services.notification import NotificationService
from bot.services.order import OrderService, OrderStatusError, status_message
from bot.services.payment import PaymentService
from bot.services.settings import SettingsService
from bot.services.ticket import TicketService
from bot.services.user import UserService
from bot.states import AdminOrderStates, AdminDeliveryStates
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="admin_orders")
logger = logging.getLogger(__name__)

ITEMS_PER_PAGE = 10

# Active filter store: keyed by admin telegram id -> filter dict.
# (In-memory; acceptable for single-process SQLite bot.)
_ACTIVE_FILTERS: dict[int, dict] = {}


def _empty_filter() -> dict:
    return {}


# --- Section menu --------------------------------------------------------- #
@router.callback_query(F.data == "admin:orders")
async def cb_admin_orders(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, 
        "🎯 <b>مدیریت سفارش‌ها</b>\n\nانتخاب گزینه:",
        reply_markup=admin_orders_menu_keyboard(),
    )
    await callback.answer()


# --- List ---------------------------------------------------------- #
async def _list_orders(callback: CallbackQuery, uow, admin, page: int = 0, filter_tag: str = "default") -> None:
    f = _filters_for(admin.telegram_id, filter_tag)
    os = OrderService(uow)
    orders = await os.filter_orders(f, offset=page * ITEMS_PER_PAGE, limit=ITEMS_PER_PAGE)
    total = await os.count_filtered(f)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    if not orders:
        text = "🎯 سفارشی با این فیلتر یافت نشد."
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:orders")]])
        await safe_edit_text(callback, text, reply_markup=kb)
        await callback.answer()
        return

    desc = _filter_desc(f)
    text = f"🎯 <b>سفارش‌ها</b>\n{desc}\n\n" if desc else "🎯 <b>سفارش‌ها</b>\n"
    await safe_edit_text(callback, 
        text,
        reply_markup=admin_order_list_keyboard(orders, page, total_pages, filter_tag),
    )
    await callback.answer()


@router.callback_query(F.data == "aorder:list")
async def cb_aorder_list(callback: CallbackQuery, uow, user: User) -> None:
    await _list_orders(callback, uow, user, 0, "default")


@router.callback_query(F.data == "aorder:pending")
async def cb_aorder_pending(callback: CallbackQuery, uow, user: User) -> None:
    os = OrderService(uow)
    orders = await os.get_pending_orders(limit=ITEMS_PER_PAGE)
    if not orders:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:orders")]])
        await safe_edit_text(callback, "🎯 سفارش در انتظار بررسی وجود ندارد.", reply_markup=kb)
        await callback.answer()
        return
    await safe_edit_text(callback, 
        "🎯 <b>سفارش‌های در انتظار بررسی</b>",
        reply_markup=admin_order_list_keyboard(orders, 0, 1, "default"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("aorder:page:"))
async def cb_aorder_page(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("داده‌های نامعتبر", show_alert=True)
        return
    page = int(parts[2])
    filter_tag = parts[3] if len(parts) > 3 else "default"
    await _list_orders(callback, uow, user, page, filter_tag)


def _filters_for(tg_id: int, tag: str) -> dict:
    f = _ACTIVE_FILTERS.get(tg_id, {}).copy()
    if tag != "default":
        raise ValueError("unknown filter tag")
    return f


def _filter_desc(f: dict) -> str:
    parts = []
    if f.get("status"):
        labels = [OrderStatus(s).label for s in f["status"]]
        parts.append(f"📊 وضعیت: {', '.join(labels)}")
    if f.get("order_number"):
        parts.append(f"🧾 شماره: {f['order_number']}")
    if f.get("user_id"):
        parts.append(f"👤 کاربر: {f['user_id']}")
    if f.get("price_min") is not None or f.get("price_max") is not None:
        parts.append(f"💰 قیمت: {f.get('price_min', 0)}-{f.get('price_max', '∞')}")
    if f.get("payment_status"):
        parts.append(f"💳 پرداخت: {f['payment_status']}")
    return "\n".join(parts)


# --- Filter UI -------------------------------------------------------------
@router.callback_query(F.data == "aorder:filter")
async def cb_aorder_filter(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, 
        "🔍 <b>فیلتر سفارش‌ها</b>\n\nانتخاب فیلتر:",
        reply_markup=admin_order_filter_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "aorder:f_clear")
async def cb_aorder_f_clear(callback: CallbackQuery, uow, user: User) -> None:
    _ACTIVE_FILTERS[user.telegram_id] = {}
    await callback.answer("فیلتر پاک شد")
    await _list_orders(callback, uow, user, 0, "default")


@router.callback_query(F.data == "aorder:f_status")
async def cb_aorder_f_status(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, "📊 انتخاب وضعیت:", reply_markup=order_status_picker())
    await callback.answer()


@router.callback_query(F.data.startswith("aorder:fs_status:"))
async def cb_aorder_fs_status(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("وضعیت نامعتبر", show_alert=True)
        return
    val = parts[2]
    f = _ACTIVE_FILTERS.setdefault(user.telegram_id, {})
    f["status"] = OrderStatus(val)
    await callback.answer("فیلتر وضعیت اعمال شد")
    await cb_aorder_filter(callback)


@router.callback_query(F.data == "aorder:f_payment")
async def cb_aorder_f_payment(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, "💳 انتخاب وضعیت پرداخت:", reply_markup=order_payment_status_picker())
    await callback.answer()


@router.callback_query(F.data.startswith("aorder:fs_payment:"))
async def cb_aorder_fs_payment(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("پرداخت_STATUS نامعتبر", show_alert=True)
        return
    val = parts[2]
    f = _ACTIVE_FILTERS.setdefault(user.telegram_id, {})
    f["payment_status"] = val
    await callback.answer("اعمال شد")
    await cb_aorder_filter(callback)


@router.callback_query(F.data == "aorder:f_number")
async def cb_aorder_f_number(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminOrderStates.waiting_filter_number)
    await callback.message.answer("🧾 شماره سفارش (یا بخشی از آن) را ارسال کنید:")
    await callback.answer()


@router.message(AdminOrderStates.waiting_filter_number)
async def do_filter_number(message: Message, state: FSMContext, uow, user: User) -> None:
    f = _ACTIVE_FILTERS.setdefault(user.telegram_id, {})
    f["order_number"] = message.text.strip()
    await state.clear()
    await message.answer("✅ فیلتر شماره اعمال شد.", reply_markup=single_button_kb(back_button("aorder:filter")))


@router.callback_query(F.data == "aorder:f_user")
async def cb_aorder_f_user(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminOrderStates.waiting_filter_user)
    await callback.message.answer("👤 آیدی تلگرام یا یوزرنیم کاربر را ارسال کنید:")
    await callback.answer()


@router.message(AdminOrderStates.waiting_filter_user)
async def do_filter_user(message: Message, state: FSMContext, uow, user: User) -> None:
    query = message.text.strip()
    us = UserService(uow)
    users = await us.search_users(query, limit=1)
    if not users:
        await message.answer("❌ کاربری یافت نشد.")
        await state.clear()
        return
    f = _ACTIVE_FILTERS.setdefault(user.telegram_id, {})
    f["user_id"] = users[0].id
    await state.clear()
    await message.answer(f"✅ فیلتر کاربر: {users[0].display_name} اعمال شد.")
    await _reply_to_list(message, uow, user)


async def _reply_to_list(message: Message, uow, user: User, page: int = 0) -> None:
    f = _ACTIVE_FILTERS.get(user.telegram_id, {})
    os = OrderService(uow)
    orders = await os.filter_orders(f, offset=page * ITEMS_PER_PAGE, limit=ITEMS_PER_PAGE)
    total = await os.count_filtered(f)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    await message.answer(
        "🎯 <b>سفارش‌ها</b>",
        reply_markup=admin_order_list_keyboard(orders, page, total_pages, "default"),
    )


@router.callback_query(F.data == "aorder:f_price")
async def cb_aorder_f_price(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminOrderStates.waiting_filter_price)
    await callback.message.answer("💰 محدوده قیمت را ارسال کنید: `min-max` (مثال: 1000-500000):")
    await callback.answer()


@router.message(AdminOrderStates.waiting_filter_price)
async def do_filter_price(message: Message, state: FSMContext, uow, user: User) -> None:
    raw = message.text.strip()
    try:
        if "-" in raw:
            lo, hi = raw.split("-", 1)
            f = _ACTIVE_FILTERS.setdefault(user.telegram_id, {})
            if lo:
                f["price_min"] = int(lo.replace(",", ""))
            if hi:
                f["price_max"] = int(hi.replace(",", ""))
        else:
            raise ValueError
        await state.clear()
        await message.answer("✅ فیلتر قیمت اعمال شد.")
    except ValueError:
        await message.answer("⚠️ فرمت اشتباه است. مثال: 1000-500000")


@router.callback_query(F.data == "aorder:f_date")
async def cb_aorder_f_date(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminOrderStates.waiting_filter_date)
    await callback.message.answer("🗓 تاریخ شروع را ارسال کنید (YYYY-MM-DD):")
    await callback.answer()


@router.message(AdminOrderStates.waiting_filter_date)
async def do_filter_date(message: Message, state: FSMContext, uow, user: User) -> None:
    raw = message.text.strip()
    from datetime import datetime as _dt
    data = await state.get_data()
    raw_from = data.get("filter_date_from", "")

    # First input: start date. Second input: end date.
    if not raw_from:
        try:
            _dt.strptime(raw, "%Y-%m-%d")
        except ValueError:
            await message.answer("⚠️ تاریخ اشتباه است. مثال: 2026-08-06")
            return
        await state.update_data(filter_date_from=raw)
        await message.answer("🗓 تاریخ پایان را ارسال کنید (YYYY-MM-DD):")
        return

    try:
        _dt.strptime(raw, "%Y-%m-%d")
    except ValueError:
        await message.answer("⚠️ تاریخ اشتباه است. مثال: 2026-08-31")
        return
    f = _ACTIVE_FILTERS.setdefault(user.telegram_id, {})
    f["date_from"] = raw_from
    f["date_to"] = raw
    await state.clear()
    await message.answer(f"✅ فیلتر تاریخ: {raw_from} تا {raw} اعمال شد.")


# --- Search by order number ------------------------------------------------ #
@router.callback_query(F.data == "aorder:search")
async def cb_aorder_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminOrderStates.waiting_search_number)
    await callback.message.answer("🧾 شماره سفارش را ارسال کنید (مثال: NOX-2026-000001):")
    await callback.answer()


@router.message(AdminOrderStates.waiting_search_number)
async def do_search_order_number(message: Message, state: FSMContext, uow, user: User) -> None:
    query = message.text.strip()
    os = OrderService(uow)
    order = await os.get_order_by_number(query)
    await state.clear()
    if not order:
        await message.answer("❌ سفارشی با این شماره یافت نشد.")
        return
    await _show_order_detail_message(message, uow, user, order)


# --- Detail view ----------------------------------------------------------- #
def _fmt_dt(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "—"


async def _show_order_detail(callback: CallbackQuery, uow, user: User, order: Order) -> None:
    text = _order_detail_text(order)
    kb = admin_order_detail_keyboard(order)
    await safe_edit_text(callback, text, reply_markup=kb)
    await callback.answer()


async def _show_order_detail_message(message: Message, uow, user: User, order: Order) -> None:
    text = _order_detail_text(order)
    kb = admin_order_detail_keyboard(order)
    await message.answer(text, reply_markup=kb)


def _order_detail_text(order: Order) -> str:
    user = order.user
    cust = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip() or user.telegram_id if user else "?"
    lines = [
        f"🎯 <b>سفارش {order.order_number}</b>",
        f"👤 مشتری: @{cust} (<code>{user.telegram_id if user else '?'}</code>)",
    ]
    
    # Add customer info if available
    if user and (user.customer_name or user.email or user.password):
        lines.append("")
        lines.append("📋 <b>اطلاعات مشتری:</b>")
        if user.customer_name:
            lines.append(f"👤 نام: {user.customer_name}")
        if user.email:
            lines.append(f"📧 ایمیل: {user.email}")
        if user.password:
            lines.append(f"🔐 رمز: <code>{user.password}</code>")
    
    lines += [
        f"📊 وضعیت: {order.status_label}",
        "",
        "🛒 <b>آیتم‌ها:</b>",
    ]
    for item in order.items:
        lines.append(f"• {item.product_title} × {item.quantity} = {format_price(item.total_price)} تومان")
    lines += [
        "",
        f"💰 مبلغ کل: {format_price(order.total_amount)} تومان",
        f"💸 تخفیف: {format_price(order.discount_amount)} تومان",
        f"🧾 مبلغ نهایی: <b>{format_price(order.final_amount)} تومان</b>",
        f"💳 روش پرداخت: {order.payment_method.value if order.payment_method else '—'}",
        "",
        "🕒 <b>زمان‌ها:</b>",
        f"📅 ثبت: {_fmt_dt(order.created_at)}",
        f"📤 رسید: {_fmt_dt(order.payment_uploaded_at)}",
        f"🕵️ بررسی: {_fmt_dt(order.payment_reviewed_at)}",
        f"✅ تایید: {_fmt_dt(order.approved_at)}",
        f"🔧 آماده‌سازی: {_fmt_dt(order.preparing_at)}",
        f"📦 ارسال: {_fmt_dt(order.delivered_at)}",
        f"🎉 تکمیل: {_fmt_dt(order.completed_at)}",
        f"🚫 لغو: {_fmt_dt(order.cancelled_at)}",
    ]
    if order.approved_by:
        lines.append(f"👨‍💼 تایید توسط: {order.approved_by.username or order.approved_by.first_name}")
    if order.delivered_by:
        lines.append(f"📦 ارسال توسط: {order.delivered_by.username or order.delivered_by.first_name}")
    if order.internal_notes:
        lines += ["", f"📝 یادداشت داخلی: {order.internal_notes}"]
    if order.customer_notes:
        lines += ["", f"💬 یادداشت مشتری: {order.customer_notes}"]
    if order.cancellation_reason:
        lines += ["", f"🚫 دلیل لغو: {order.cancellation_reason}"]
    if order.rejection_reason:
        lines += ["", f"❌ دلیل رد: {order.rejection_reason}"]
    if order.linked_ticket_id:
        lines += ["", f"🎫 تیکت مرتبط: <code>{order.linked_ticket_id[:8]}</code>"]

    # Timeline
    if order.status_events:
        lines += ["", "📜 <b>نمودار وضعیت:</b>"]
        for ev in order.status_events:
            who = ev.changed_by.username if ev.changed_by else ("سیستم" if ev.is_system else "—")
            lines.append(
                f"• {_fmt_dt(ev.created_at)} | {ev.from_label} → {ev.to_label} | {who}"
            )
    return "\n".join(lines)


@router.callback_query(F.data.startswith("aorder:view:"))
async def cb_aorder_view(callback: CallbackQuery, uow, user: User) -> None:
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
    await _show_order_detail(callback, uow, user, order)


# --- Status transitions ---------------------------------------------------- #
async def _transition(
    callback: CallbackQuery,
    uow,
    user: User,
    order: Order,
    to_status: OrderStatus,
    note: str | None = None,
) -> None:
    os = OrderService(uow, notifier=NotificationService(callback.bot, uow))
    try:
        await os.transition_to(order, to_status, admin=user, note=note)
        await uow.flush()

        await uow.commit()
    except OrderStatusError as e:
        await callback.answer(str(e), show_alert=True)
        return
    api = AdminService(uow)
    await api.log_action(user, LogAction.ORDER_EDIT, target_id=order.id,
                         description=f"تغییر وضعیت به {to_status.value}")
    await uow.flush()

    await uow.commit()
    await callback.answer("وضعیت تغییر کرد")
    fresh = await os.get_order(order.id)
    if fresh:
        await _show_order_detail(callback, uow, user, fresh)


@router.callback_query(F.data.startswith("aorder:review:"))
async def cb_aorder_review(callback: CallbackQuery, uow, user: User) -> None:
    order = await _load_order(callback, uow)
    if not order:
        return
    await _transition(callback, uow, user, order, OrderStatus.PAYMENT_REVIEWING)


@router.callback_query(F.data.startswith("aorder:approve:"))
async def cb_aorder_approve(callback: CallbackQuery, uow, user: User) -> None:
    order = await _load_order(callback, uow)
    if not order:
        return
    await _transition(callback, uow, user, order, OrderStatus.APPROVED, note="پرداخت تایید شد")


@router.callback_query(F.data.startswith("aorder:prepare:"))
async def cb_aorder_prepare(callback: CallbackQuery, uow, user: User) -> None:
    order = await _load_order(callback, uow)
    if not order:
        return
    await _transition(callback, uow, user, order, OrderStatus.PREPARING)


@router.callback_query(F.data.startswith("aorder:deliver:"))
async def cb_aorder_deliver(callback: CallbackQuery, uow, user: User) -> None:
    order = await _load_order(callback, uow)
    if not order:
        return
    await _transition(callback, uow, user, order, OrderStatus.DELIVERED, note="محصول ارسال شد")


@router.callback_query(F.data.startswith("aorder:complete:"))
async def cb_aorder_complete(callback: CallbackQuery, uow, user: User) -> None:
    """Complete order: send config delivery if applicable, then mark completed."""
    order = await _load_order(callback, uow)
    if not order:
        return
    
    # Check if order has config items
    has_config = any(item.config_product_id for item in order.items)
    
    if has_config:
        # Check if delivery data exists
        delivery = await uow.order_deliveries.get_by_order_id(order.id)
        if not delivery:
            await callback.answer(
                "⚠️ برای این سفارش هنوز کانفیگ تحویل ثبت نشده است.\n"
                "ابتدا از دکمه «ثبت تحویل کانفیگ» استفاده کنید.",
                show_alert=True
            )
            return
        
        # Send delivery data to customer
        try:
            # Build delivery message
            delivery_text = f"📦 <b>تحویل سفارش {order.order_number}</b>\n\n"
            if delivery.config_text:
                delivery_text += f"{delivery.config_text}\n\n"
            if delivery.note:
                delivery_text += f"💬 {delivery.note}\n"
            
            # Send text message
            await callback.bot.send_message(
                order.user.telegram_id,
                delivery_text
            )
            
            # Send file if exists
            if delivery.file_id:
                await callback.bot.send_document(
                    order.user.telegram_id,
                    delivery.file_id,
                    caption=delivery.file_name or "فایل کانفیگ"
                )
            
            # Mark delivery as delivered
            delivery.status = "delivered"
            delivery.delivered_at = datetime.now(timezone.utc)
            await uow.flush()
            
            logger.info(
                "config_delivery_sent: order=%s user=%s admin=%s",
                order.order_number, order.user.telegram_id, user.telegram_id
            )
            
        except Exception as e:
            logger.exception(f"config_delivery_failed: order={order.order_number} error={e}")
            # Mark delivery as failed
            delivery.status = "failed"
            await uow.flush()
            await uow.commit()
            
            await callback.answer(
                f"❌ ارسال کانفیگ به مشتری ناموفق بود: {e}\n"
                f"سفارش تکمیل نشد. لطفاً دوباره تلاش کنید.",
                show_alert=True
            )
            return
    
    # Now complete the order
    await _transition(callback, uow, user, order, OrderStatus.COMPLETED)


@router.callback_query(F.data.startswith("aorder:reject:"))
async def cb_aorder_reject(callback: CallbackQuery, uow, user: User, state: FSMContext) -> None:
    order = await _load_order(callback, uow)
    if not order:
        return
    await state.set_data({"order_id": order.id})
    await state.set_state(AdminOrderStates.waiting_reject_reason)
    await callback.message.answer("❌ دلیل رد سفارش را بنویسید:")
    await callback.answer()


@router.message(AdminOrderStates.waiting_reject_reason)
async def do_reject(message: Message, state: FSMContext, uow, user: User) -> None:
    data = await state.get_data()
    order = await OrderService(uow).get_order(data.get("order_id"))
    await state.clear()
    if not order:
        return
    await _transition_message(message, uow, user, order,
                              OrderStatus.REJECTED, note=message.text.strip())


@router.callback_query(F.data.startswith("aorder:cancel:"))
async def cb_aorder_cancel(callback: CallbackQuery, uow, user: User, state: FSMContext) -> None:
    order = await _load_order(callback, uow)
    if not order:
        return
    await state.set_data({"order_id": order.id})
    await state.set_state(AdminOrderStates.waiting_cancel_reason)
    await callback.message.answer("🚫 دلیل لغو سفارش را بنویسید:")
    await callback.answer()


@router.message(AdminOrderStates.waiting_cancel_reason)
async def do_cancel(message: Message, state: FSMContext, uow, user: User) -> None:
    data = await state.get_data()
    order = await OrderService(uow).get_order(data.get("order_id"))
    await state.clear()
    if not order:
        return
    await _transition_message(message, uow, user, order,
                              OrderStatus.CANCELLED, note=message.text.strip())


@router.callback_query(F.data.startswith("aorder:refund:"))
async def cb_aorder_refund(callback: CallbackQuery, uow, user: User) -> None:
    """Refund order: credit wallet atomically and mark as refunded."""
    order = await _load_order(callback, uow)
    if not order:
        return
    
    try:
        from bot.services.refund import RefundService
        refund_service = RefundService(uow)
        refunded_order = await refund_service.refund_order(order, user, reason="بازگشت وجه توسط ادمین")
        await uow.commit()
        
        await callback.answer("✅ بازگشت وجه با موفقیت انجام شد", show_alert=True)
        
        # Refresh order and show updated detail
        from bot.services.order import OrderService
        os = OrderService(uow)
        refreshed_order = await os.get_order(order.id)
        
        await callback.message.edit_text(
            f"✅ <b>بازگشت وجه انجام شد</b>\n\n"
            f"سفارش: {refreshed_order.order_number}\n"
            f"مبلغ: {refreshed_order.final_amount:,} تومان\n"
            f"وضعیت: {refreshed_order.status_label}",
            reply_markup=admin_order_detail_keyboard(refreshed_order)
        )
        
    except Exception as e:
        logger.exception(f"Refund failed: {e}")
        await uow.rollback()
        await callback.answer(f"❌ خطا در بازگشت وجه: {e}", show_alert=True)


async def _load_order(callback: CallbackQuery, uow) -> Order | None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("سفارش یافت نشد", show_alert=True)
        return None
    order_id = parts[2]
    os = OrderService(uow)
    order = await os.get_order(order_id)
    if not order:
        await callback.answer("سفارش یافت نشد", show_alert=True)
        return None
    return order


async def _transition_message(
    message: Message, uow, user: User, order: Order, to_status: OrderStatus, note: str | None = None
) -> None:
    """Handle a status transition initiated from a text (reason) message."""
    os = OrderService(uow, notifier=NotificationService(message.bot, uow))
    try:
        await os.transition_to(order, to_status, admin=user, note=note)
        await uow.flush()

        await uow.commit()
    except OrderStatusError as e:
        await message.answer(str(e))
        return
    api = AdminService(uow)
    await api.log_action(user, LogAction.ORDER_EDIT, target_id=order.id,
                         description=f"تغییر وضعیت به {to_status.value}")
    await uow.flush()

    await uow.commit()
    fresh = await os.get_order(order.id)
    detail = _order_detail_text(fresh) if fresh else "سفارش"
    await message.answer("✅ وضعیت تغییر کرد.\n\n" + detail,
                         reply_markup=admin_order_detail_keyboard(fresh) if fresh else None)


# --- Notes / ticket -------------------------------------------------------- #
@router.callback_query(F.data.startswith("aorder:note:"))
async def cb_aorder_note(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("سفارش یافت نشد", show_alert=True)
        return
    order_id = parts[2]
    await state.set_data({"order_id": order_id})
    await state.set_state(AdminOrderStates.waiting_note)
    await callback.message.answer("📝 یادداشت داخلی را بنویسید:")
    await callback.answer()


@router.message(AdminOrderStates.waiting_note)
async def do_note(message: Message, state: FSMContext, uow, user: User) -> None:
    data = await state.get_data()
    os = OrderService(uow)
    await os.set_internal_note(data["order_id"], message.text.strip(), admin=user)
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.ORDER_EDIT, target_id=data["order_id"], description="ثبت یادداشت سفارش")
    await uow.flush()

    await uow.commit()
    await state.clear()
    await message.answer("✅ یادداشت ثبت شد.")


@router.callback_query(F.data.startswith("aorder:ticket:"))
async def cb_aorder_ticket(callback: CallbackQuery, state: FSMContext) -> None:
    order_id = callback.data.split(":", 2)[2]
    await state.set_data({"order_id": order_id})
    await state.set_state(AdminOrderStates.waiting_ticket_link)
    await callback.message.answer("🎫 آیدی تیکت را برای لینک ارسال کنید (یا /none برای حذف):")
    await callback.answer()


@router.message(AdminOrderStates.waiting_ticket_link)
async def do_link_ticket(message: Message, state: FSMContext, uow, user: User) -> None:
    data = await state.get_data()
    os = OrderService(uow)
    raw = message.text.strip()
    if raw.lower() == "/none":
        await os.unlink_ticket(data["order_id"])
        await uow.flush()

        await uow.commit()
        await message.answer("✅ لینک تیکت حذف شد.")
        await state.clear()
        return
    ts = TicketService(uow)
    ticket = await ts.get_ticket(raw)
    if not ticket:
        await message.answer("❌ تیکتی با این آیدی یافت نشد.")
        return
    await os.link_ticket(data["order_id"], ticket.id)
    await uow.flush()

    await uow.commit()
    await state.clear()
    await message.answer(f"✅ تیکت {ticket.id[:8]} به سفارش لینک شد.")

# --- Config Delivery ------------------------------------------------------- #
def _order_has_config(order: Order) -> bool:
    """Check if order has any config items."""
    return any(item.config_product_id for item in order.items)


@router.callback_query(F.data.startswith("aorder:delivery:"))
async def cb_aorder_delivery(callback: CallbackQuery, state: FSMContext, uow, user: User) -> None:
    """Start config delivery entry for an order."""
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
    
    if not _order_has_config(order):
        await callback.answer("این سفارش کانفیگ ندارد", show_alert=True)
        return
    
    await state.update_data(delivery_order_id=order_id)
    await state.set_state(AdminDeliveryStates.waiting_config_text)
    await callback.message.answer(
        "📦 <b>تحویل کانفیگ</b>\n\n"
        "متن/اطلاعات کانفیگ را وارد کنید:\n"
        "(یا /skip برای رد کردن و فقط ارسال فایل)",
        reply_markup=single_button_kb(back_button(f"aorder:view:{order_id}"))
    )
    await callback.answer()


@router.message(AdminDeliveryStates.waiting_config_text)
async def collect_delivery_text(message: Message, state: FSMContext, uow, user: User) -> None:
    """Collect config text and ask for file."""
    config_text = None if message.text and message.text.strip() == "/skip" else (message.text.strip() if message.text else None)
    
    await state.update_data(config_text=config_text)
    await state.set_state(AdminDeliveryStates.waiting_config_file)
    await message.answer(
        "📎 فایل کانفیگ را ارسال کنید (یا /skip برای رد کردن):"
    )


@router.message(AdminDeliveryStates.waiting_config_file)
async def collect_delivery_file(message: Message, state: FSMContext, uow, user: User) -> None:
    """Collect config file and ask for note."""
    file_id = None
    file_name = None
    
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
    elif message.text and message.text.strip() != "/skip":
        await message.answer("⚠️ لطفاً یک فایل ارسال کنید یا /skip بزنید:")
        return
    
    await state.update_data(file_id=file_id, file_name=file_name)
    await state.set_state(AdminDeliveryStates.waiting_delivery_note)
    await message.answer(
        "📝 یادداشت تحویل (اختیاری، یا /skip):"
    )


@router.message(AdminDeliveryStates.waiting_delivery_note)
async def save_delivery_data(message: Message, state: FSMContext, uow, user: User) -> None:
    """Save delivery data to database (DRAFT status, NOT sent to customer)."""
    data = await state.get_data()
    order_id = data.get("delivery_order_id")
    config_text = data.get("config_text")
    file_id = data.get("file_id")
    file_name = data.get("file_name")
    note = None if message.text and message.text.strip() == "/skip" else (message.text.strip() if message.text else None)
    
    # Determine delivery type
    if config_text and file_id:
        delivery_type = "mixed"
    elif file_id:
        delivery_type = "config_file"
    else:
        delivery_type = "config_text"
    
    try:
        delivery = await uow.order_deliveries.save_delivery(
            order_id=order_id,
            config_text=config_text,
            file_id=file_id,
            file_name=file_name,
            note=note,
            delivery_type=delivery_type,
            created_by_id=user.id,
        )
        await uow.commit()
        
        await state.clear()
        
        # Build confirmation message
        text = "✅ <b>اطلاعات تحویل ذخیره شد</b>\n\n"
        text += "⚠️ این اطلاعات هنوز برای مشتری ارسال نشده است.\n"
        text += "برای ارسال، از دکمه «پایان سفارش» استفاده کنید.\n\n"
        if config_text:
            text += f"📝 متن: {config_text[:100]}{'...' if len(config_text) > 100 else ''}\n"
        if file_name:
            text += f"📎 فایل: {file_name}\n"
        if note:
            text += f"💬 یادداشت: {note}\n"
        
        logger.info("config_delivery_saved: order=%s admin=%s type=%s", order_id, user.telegram_id, delivery_type)
        
        os = OrderService(uow)
        order = await os.get_order(order_id)
        await message.answer(
            text,
            reply_markup=admin_order_detail_keyboard(order) if order else single_button_kb(back_button("aorder:list"))
        )
    except Exception as e:
        logger.exception(f"Failed to save delivery: {e}")
        await state.clear()
        await message.answer(f"❌ خطا در ذخیره تحویل: {e}")
