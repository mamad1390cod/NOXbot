"""User-side wallet top-up handlers."""

import logging
from datetime import datetime

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import back_button, home_button
from bot.keyboards.topup import (
    topup_amounts_keyboard,
    topup_invoice_keyboard,
    topup_method_keyboard,
)
from bot.models.topup import TopUpPaymentMethod, TopUpStatus
from bot.models.user import User
from bot.services.notification import NotificationService
from bot.services.settings import SettingsService
from bot.services.topup import TopUpService
from bot.states import TopUpStates
from bot.utils.editing import safe_edit_text
from bot.utils.format import format_price

router = Router(name="topup")
logger = logging.getLogger(__name__)


# ── Entry point ────────────────────────────────────────────────────────── #

@router.callback_query(F.data == "tu:menu")
async def cb_topup_menu(callback: CallbackQuery, uow, user: User) -> None:
    """Show top-up amount selection."""
    svc = TopUpService(uow)
    amounts = await svc.get_active_amounts()
    if not amounts:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✏️ مبلغ دلخواه", callback_data="tu:custom_amt")],
            [back_button("dash:menu")],
        ])
        await safe_edit_text(callback,
            "💰 <b>شارژ کیف پول</b>\n\n"
            f"💼 موجودی فعلی: <b>{format_price(user.wallet_balance)} تومان</b>\n\n"
            "مبلغ دلخواه خود را وارد کنید (عدد به تومان):",
            reply_markup=kb,
        )
    else:
        await safe_edit_text(callback,
            "💰 <b>شارژ کیف پول</b>\n\n"
            f"💼 موجودی فعلی: <b>{format_price(user.wallet_balance)} تومان</b>\n\n"
            "مبلغ مورد نظر را انتخاب کنید:",
            reply_markup=topup_amounts_keyboard(amounts),
        )
    await callback.answer()


@router.callback_query(F.data == "tu:custom_amt")
async def cb_custom_amount(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask user for custom amount."""
    await state.set_state(TopUpStates.waiting_custom_amount)
    await callback.message.answer("💰 مبلغ مورد نظر را به تومان ارسال کنید (فقط عدد):")
    await callback.answer()


@router.message(TopUpStates.waiting_custom_amount)
async def do_custom_amount(message: Message, state: FSMContext, uow, user: User) -> None:
    """Handle custom amount input."""
    raw = message.text.strip().replace(",", "") if message.text else ""
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("⚠️ لطفاً یک عدد مثبت معتبر وارد کنید:")
        return
    amount = int(raw)
    await state.update_data(topup_amount=amount)
    await state.clear()
    await _show_method_selection(message, amount, edit=False)


@router.callback_query(F.data.startswith("tu:amt:"))
async def cb_select_amount(callback: CallbackQuery, state: FSMContext, uow) -> None:
    """Handle preset amount selection."""
    amount_id = callback.data.split(":", 2)[2]
    svc = TopUpService(uow)
    amounts = await svc.get_all_amounts()
    selected = next((a for a in amounts if a.id.startswith(amount_id)), None)
    if not selected:
        await callback.answer("مبلغ یافت نشد", show_alert=True)
        return
    await state.update_data(topup_amount=selected.amount)
    await _show_method_selection(callback, selected.amount, edit=True)
    await callback.answer()


async def _show_method_selection(event, amount: int, edit: bool = True) -> None:
    """Show payment method selection."""
    text = (
        f"💰 <b>مبلغ انتخاب‌شده: {format_price(amount)} تومان</b>\n\n"
        "روش پرداخت را انتخاب کنید:"
    )
    kb = topup_method_keyboard(amount)
    if edit and isinstance(event, CallbackQuery):
        await safe_edit_text(event, text, reply_markup=kb)
    else:
        await event.answer(text, reply_markup=kb)


@router.callback_query(F.data == "tu:m:crypto")
async def cb_crypto_disabled(callback: CallbackQuery) -> None:
    await callback.answer("⚠️ پرداخت ارز دیجیتال فعلاً غیرفعال است.", show_alert=True)


@router.callback_query(F.data == "tu:m:card")
async def cb_card_method(callback: CallbackQuery, state: FSMContext) -> None:
    """Show invoice for card payment."""
    data = await state.get_data()
    amount = data.get("topup_amount")
    if not amount:
        await callback.answer("خطا", show_alert=True)
        return
    await state.update_data(payment_method="card")
    text = (
        "━━━━━━━━━━━━━━\n"
        "🧾 <b>فاکتور شارژ حساب</b>\n\n"
        f"💰 مبلغ شارژ: <b>{format_price(amount)} تومان</b>\n\n"
        "شما در حال پرداخت این مبلغ به فروشگاه هستید.\n"
        "آیا از انجام این پرداخت مطمئن هستید؟\n"
        "━━━━━━━━━━━━━━"
    )
    await safe_edit_text(callback, text, reply_markup=topup_invoice_keyboard(amount))
    await callback.answer()


@router.callback_query(F.data == "tu:confirm")
async def cb_confirm_invoice(callback: CallbackQuery, state: FSMContext, uow, user: User) -> None:
    """After confirming, show card info and ask for receipt."""
    data = await state.get_data()
    amount = data.get("topup_amount")
    if not amount:
        await callback.answer("خطا", show_alert=True)
        return

    # Create top-up request
    svc = TopUpService(uow)
    req = await svc.create_request(
        user_id=user.id,
        amount=amount,
        payment_method=TopUpPaymentMethod.CARD,
    )
    await uow.flush()

    await uow.commit()

    # Get card info from settings
    settings_svc = SettingsService(uow)
    info = await settings_svc.get_payment_info()

    text = (
        "💳 <b>اطلاعات پرداخت</b>\n\n"
    )
    if info.get("card_number"):
        text += f"💳 شماره کارت:\n<code>{info['card_number']}</code>\n\n"
    if info.get("card_holder"):
        text += f"👤 صاحب حساب:\n{info['card_holder']}\n\n"
    if info.get("bank_name"):
        text += f"🏦 بانک: {info['bank_name']}\n\n"
    text += (
        f"💰 مبلغ قابل پرداخت:\n<b>{format_price(amount)} تومان</b>\n\n"
        "⚠️ لطفاً دقیقاً همین مبلغ را انتقال دهید.\n\n"
        f"🔢 کد پیگیری: <code>{req.tracking_code}</code>\n\n"
        "📤 پس از انتقال، رسید پرداخت خود را ارسال کنید."
    )
    await state.update_data(topup_request_id=req.id)
    await state.set_state(TopUpStates.waiting_receipt)

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="❌ انصراف", callback_data="tu:cancel_req")],
    ])
    await safe_edit_text(callback, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "tu:cancel_req")
async def cb_cancel_request(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel the current top-up flow."""
    await state.clear()
    await safe_edit_text(callback, "❌ عملیات شارژ لغو شد.")
    await callback.answer()


@router.message(TopUpStates.waiting_receipt, F.photo)
async def do_receipt(message: Message, state: FSMContext, uow, user: User) -> None:
    """Receive receipt photo from user."""
    data = await state.get_data()
    request_id = data.get("topup_request_id")
    if not request_id:
        await state.clear()
        return

    photo = message.photo[-1]
    svc = TopUpService(uow)
    await svc.submit_receipt(request_id, photo.file_id, user.id, "photo")
    await uow.flush()

    await uow.commit()

    req = await svc.get_request(request_id)
    await state.clear()

    await message.answer(
        "⏳ <b>رسید شما دریافت شد.</b>\n\n"
        "درخواست شما برای بررسی ارسال شد.\n"
        "لطفاً تا تأیید یا رد پرداخت منتظر بمانید.\n\n"
        f"🔢 کد پیگیری: <code>{req.tracking_code}</code>"
    )

    # Notify admins
    _now = datetime.now()
    admin_text = (
        "🧾 <b>درخواست شارژ کیف پول</b>\n\n"
        f"👤 کاربر: {user.display_name}\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
        f"💰 مبلغ شارژ: <b>{format_price(req.amount)} تومان</b>\n"
        f"💳 روش پرداخت: {req.payment_method.label}\n"
        f"🔢 کد پیگیری: <code>{req.tracking_code}</code>\n"
        f"📅 تاریخ: {_now.strftime('%Y-%m-%d %H:%M')}\n"
    )
    from bot.keyboards.topup import admin_topup_detail_keyboard
    notifier = NotificationService(message.bot, uow)
    await notifier.send_to_admins(
        text=admin_text,
        photo=photo.file_id,
        reply_markup=admin_topup_detail_keyboard(req),
    )


@router.message(TopUpStates.waiting_receipt, F.document)
async def do_receipt_document(message: Message, state: FSMContext, uow, user: User) -> None:
    """Receive receipt as document."""
    data = await state.get_data()
    request_id = data.get("topup_request_id")
    if not request_id:
        await state.clear()
        return

    doc = message.document
    svc = TopUpService(uow)
    await svc.submit_receipt(request_id, doc.file_id, user.id, "document")
    await uow.flush()

    await uow.commit()

    req = await svc.get_request(request_id)
    await state.clear()

    await message.answer(
        "⏳ <b>رسید شما دریافت شد.</b>\n\n"
        "درخواست شما برای بررسی ارسال شد.\n"
        f"🔢 کد پیگیری: <code>{req.tracking_code}</code>"
    )

    # Notify admins
    _now = datetime.now()
    admin_text = (
        "🧾 <b>درخواست شارژ کیف پول</b>\n\n"
        f"👤 کاربر: {user.display_name}\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
        f"💰 مبلغ شارژ: <b>{format_price(req.amount)} تومان</b>\n"
        f"💳 روش پرداخت: {req.payment_method.label}\n"
        f"🔢 کد پیگیری: <code>{req.tracking_code}</code>\n"
        f"📅 تاریخ: {_now.strftime('%Y-%m-%d %H:%M')}\n"
    )
    from bot.keyboards.topup import admin_topup_detail_keyboard
    notifier = NotificationService(message.bot, uow)
    await notifier.send_to_admins(
        text=admin_text,
        document=doc.file_id,
        reply_markup=admin_topup_detail_keyboard(req),
    )


@router.message(TopUpStates.waiting_receipt)
async def do_receipt_invalid(message: Message) -> None:
    await message.answer("⚠️ لطفاً تصویر یا فایل رسید پرداخت را ارسال کنید.")


# ── Resubmit receipt flow ──────────────────────────────────────────────── #

@router.message(TopUpStates.resubmit_receipt, F.photo)
async def do_resubmit_receipt(message: Message, state: FSMContext, uow, user: User) -> None:
    """Receive resubmitted receipt."""
    data = await state.get_data()
    request_id = data.get("topup_request_id")
    if not request_id:
        await state.clear()
        return

    photo = message.photo[-1]
    svc = TopUpService(uow)
    await svc.submit_receipt(request_id, photo.file_id, user.id, "photo")
    await uow.flush()

    await uow.commit()

    req = await svc.get_request(request_id)
    await state.clear()

    await message.answer(
        "⏳ <b>رسید جدید دریافت شد.</b>\n\n"
        "درخواست مجدداً برای بررسی ارسال شد.\n"
        f"🔢 کد پیگیری: <code>{req.tracking_code}</code>"
    )

    # Re-notify admins
    _now = datetime.now()
    admin_text = (
        "🔄 <b>رسید مجدد — درخواست شارژ کیف پول</b>\n\n"
        f"👤 کاربر: {user.display_name}\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
        f"💰 مبلغ: <b>{format_price(req.amount)} تومان</b>\n"
        f"🔢 کد پیگیری: <code>{req.tracking_code}</code>\n"
        f"📅 تاریخ: {_now.strftime('%Y-%m-%d %H:%M')}\n"
        f"📎 شماره رسید: {len(req.receipts)}\n"
    )
    from bot.keyboards.topup import admin_topup_detail_keyboard
    notifier = NotificationService(message.bot, uow)
    await notifier.send_to_admins(
        text=admin_text,
        photo=photo.file_id,
        reply_markup=admin_topup_detail_keyboard(req),
    )


@router.message(TopUpStates.resubmit_receipt)
async def do_resubmit_invalid(message: Message) -> None:
    await message.answer("⚠️ لطفاً تصویر رسید را ارسال کنید.")
