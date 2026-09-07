"""Admin payment review handlers."""

import logging

from aiogram import F, Router, types
from aiogram.types import CallbackQuery

from bot.keyboards.admin import admin_payments_keyboard, payment_review_keyboard
from bot.keyboards.common import back_button
from bot.models.log import LogAction
from bot.models.payment import PaymentStatus
from bot.models.user import User
from bot.services.admin import AdminService
from bot.services.notification import NotificationService
from bot.services.order import OrderService
from bot.services.payment import PaymentService
from bot.texts import PAYMENT_APPROVED, PAYMENT_REJECTED
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="admin_payments")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "admin:payments")
async def cb_admin_payments(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, "💳 <b>مدیریت پرداخت‌ها</b>", reply_markup=admin_payments_keyboard())
    await callback.answer()


@router.callback_query(F.data == "apay:pending")
async def cb_payments_pending(callback: CallbackQuery, uow, user: User) -> None:
    ps = PaymentService(uow)
    payments = await ps.get_pending_payments(limit=20)
    if not payments:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:payments")]])
        await safe_edit_text(callback, "💳 پرداخت در انتظاری نیست.", reply_markup=kb)
        await callback.answer()
        return
    await safe_edit_text(callback, "💳 <b>پرداخت‌های در انتظار</b>", reply_markup=_payment_list_keyboard(payments))
    await callback.answer()


@router.callback_query(F.data == "apay:approved")
async def cb_payments_approved(callback: CallbackQuery, uow, user: User) -> None:
    ps = PaymentService(uow)
    payments = await ps.get_all_for_admin(status=PaymentStatus.APPROVED, limit=20)
    if not payments:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:payments")]])
        await safe_edit_text(callback, "💳 پرداخت تایید شده‌ای نیست.", reply_markup=kb)
        await callback.answer()
        return
    await safe_edit_text(callback, "✅ <b>پرداخت‌های تایید شده</b>", reply_markup=_payment_list_keyboard(payments))
    await callback.answer()


@router.callback_query(F.data == "apay:rejected")
async def cb_payments_rejected(callback: CallbackQuery, uow, user: User) -> None:
    ps = PaymentService(uow)
    payments = await ps.get_all_for_admin(status=PaymentStatus.REJECTED, limit=20)
    if not payments:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:payments")]])
        await safe_edit_text(callback, "💳 پرداخت رد شده‌ای نیست.", reply_markup=kb)
        await callback.answer()
        return
    await safe_edit_text(callback, "❌ <b>پرداخت‌های رد شده</b>", reply_markup=_payment_list_keyboard(payments))
    await callback.answer()


@router.callback_query(F.data == "apay:all")
async def cb_payments_all(callback: CallbackQuery, uow, user: User) -> None:
    ps = PaymentService(uow)
    payments = await ps.get_all_for_admin(limit=20)
    if not payments:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:payments")]])
        await safe_edit_text(callback, "💳 پرداختی ثبت نشده است.", reply_markup=kb)
        await callback.answer()
        return
    await safe_edit_text(callback, "💳 <b>همه پرداخت‌ها</b>", reply_markup=_payment_list_keyboard(payments))
    await callback.answer()


def _payment_list_keyboard(payments) -> types.InlineKeyboardMarkup:
    keyboard = []
    for p in payments:
        user = p.user
        label = f"💳 {user.username or user.telegram_id if user else '?'} — {format_price(p.amount)}"
        keyboard.append([types.InlineKeyboardButton(text=label, callback_data=f"apay:view:{p.id}")])
    keyboard.append([back_button("admin:payments")])
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.callback_query(F.data.startswith("apay:view:"))
async def cb_payment_view(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("پرداخت یافت نشد", show_alert=True)
        return
    payment_id = parts[2]
    ps = PaymentService(uow)
    payment = await ps.get_payment(payment_id)
    if not payment:
        await callback.answer("پرداخت یافت نشد", show_alert=True)
        return
    puser = payment.user
    status_map = {"pending": "⏳ در انتظار", "approved": "✅ تایید", "rejected": "❌ رد", "cancelled": "🚫 لغو"}
    text = (
        f"💳 <b>پرداخت</b>\n\n"
        f"🆔 آیدی تلگرام: <code>{puser.telegram_id if puser else '?'}</code>\n"
        f"👤 نام: {puser.first_name or ''} {puser.last_name or ''} (@{puser.username or '-'})\n"
        f"💰 مبلغ: <b>{format_price(payment.amount)} تومان</b>\n"
        f"📊 وضعیت: {status_map.get(payment.status.value, payment.status.value)}\n"
        f"📅 ثبت: {payment.created_at.strftime('%Y-%m-%d %H:%M') if payment.created_at else '—'}\n"
    )
    kb = payment_review_keyboard(payment_id)
    if payment.receipt_url:
        await callback.message.edit_media(
            types.InputMediaPhoto(media=payment.receipt_url, caption=text),
            reply_markup=kb,
        )
    else:
        await safe_edit_text(callback, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("apay:approve:"))
async def cb_payment_approve(callback: CallbackQuery, uow, user: User, bot) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("پرداخت یافت نشد", show_alert=True)
        return
    payment_id = parts[2]
    ps = PaymentService(uow)
    try:
        payment = await ps.approve_payment(payment_id, user.id)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await uow.flush()

    await uow.commit()

    api = AdminService(uow)
    await api.log_action(user, LogAction.PAYMENT_APPROVE, target_id=payment_id, description=f"تایید پرداخت {format_price(payment.amount)}")
    await uow.flush()

    await uow.commit()

    # Notify user
    if payment.user:
        notifier = NotificationService(callback.bot, uow)
        await notifier.notify_user(payment.user.telegram_id, PAYMENT_APPROVED())

    await callback.answer("پرداخت تایید شد")
    await safe_edit_text(callback, "✅ پرداخت تایید شد.")


@router.callback_query(F.data.startswith("apay:reject:"))
async def cb_payment_reject(callback: CallbackQuery, uow, user: User) -> None:
    payment_id = callback.data.split(":", 2)[2]
    ps = PaymentService(uow)
    try:
        payment = await ps.reject_payment(payment_id, user.id, reason="عدم تطابق رسید")
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await uow.flush()

    await uow.commit()

    api = AdminService(uow)
    await api.log_action(user, LogAction.PAYMENT_REJECT, target_id=payment_id, description="رد پرداخت")
    await uow.flush()

    await uow.commit()

    if payment.user:
        notifier = NotificationService(callback.bot, uow)
        await notifier.notify_user(payment.user.telegram_id, PAYMENT_REJECTED())

    await callback.answer("پرداخت رد شد")
    await safe_edit_text(callback, "❌ پرداخت رد شد.")


@router.callback_query(F.data.startswith("apay:again:"))
async def cb_payment_request_again(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("پرداخت یافت نشد", show_alert=True)
        return
    payment_id = parts[2]
    ps = PaymentService(uow)
    payment = await ps.request_receipt_again(payment_id, user.id)
    await uow.flush()

    await uow.commit()

    # Notify user to resubmit receipt
    if payment and payment.user:
        notifier = NotificationService(callback.bot, uow)
        await notifier.notify_user(
            payment.user.telegram_id,
            "🔄 رسید پرداخت شما قابل قبول نبود. لطفاً رسید جدید را ارسال کنید.",
        )
    await callback.answer("درخواست رسید مجدد ارسال شد")
    await safe_edit_text(callback, "🔄 درخواست رسید مجدد ارسال شد.")