"""Admin top-up management handlers — review, approve, reject, manual credit/debit."""

import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import back_button, single_button_kb
from bot.keyboards.topup import (
    admin_topup_amount_detail_keyboard,
    admin_topup_amounts_keyboard,
    admin_topup_detail_keyboard,
    admin_topup_list_keyboard,
    admin_topup_menu_keyboard,
)
from bot.models.log import LogAction
from bot.models.topup import TopUpStatus
from bot.models.user import User
from bot.services.admin import AdminService
from bot.services.notification import NotificationService
from bot.services.topup import TopUpService
from bot.services.user import UserService
from bot.states import AdminTopUpStates
from bot.utils.editing import safe_edit_text
from bot.utils.format import format_price

router = Router(name="admin_topup")
logger = logging.getLogger(__name__)


def _req_text(req) -> str:
    """Build detail text for a top-up request."""
    lines = [
        "🧾 <b>درخواست شارژ کیف پول</b>\n",
        f"👤 کاربر: {req.user.display_name if req.user else '?'}",
        f"🆔 Telegram ID: <code>{req.user.telegram_id if req.user else '?'}</code>",
        f"💰 مبلغ: <b>{format_price(req.amount)} تومان</b>",
        f"💳 روش: {req.payment_method.label}",
        f"🔢 کد پیگیری: <code>{req.tracking_code}</code>",
        f"📊 وضعیت: {req.status.label}",
    ]
    if req.created_at:
        lines.append(f"📅 ایجاد: {req.created_at.strftime('%Y-%m-%d %H:%M')}")
    if req.reviewed_at:
        lines.append(f"📅 بررسی: {req.reviewed_at.strftime('%Y-%m-%d %H:%M')}")
    if req.reviewed_by:
        lines.append(f"👤 بررسی‌کننده: {req.reviewed_by.display_name}")
    if req.reject_reason:
        lines.append(f"📝 دلیل رد: {req.reject_reason}")
    lines.append(f"\n📎 تعداد رسید: {len(req.receipts)}")
    if req.receipts:
        for i, r in enumerate(req.receipts, 1):
            ts = r.created_at.strftime("%m-%d %H:%M") if r.created_at else "?"
            lines.append(f"  • رسید #{i} ({r.file_type}) — {ts}")
    return "\n".join(lines)


# ── Menu ───────────────────────────────────────────────────────────────── #

@router.callback_query(F.data == "atu:menu")
async def cb_topup_admin_menu(callback: CallbackQuery, uow, user: User) -> None:
    svc = TopUpService(uow)
    stats = await svc.get_stats()
    await safe_edit_text(callback,
        "🧾 <b>مدیریت شارژ کیف پول</b>\n\n"
        f"⏳ در انتظار: {stats['pending'] + stats['waiting_receipt']}\n"
        f"✅ تأیید شده: {stats['approved']}\n"
        f"❌ رد شده: {stats['rejected']}\n"
        f"💰 کل شارژ تأییدشده: {format_price(stats['total_approved_amount'])} تومان",
        reply_markup=admin_topup_menu_keyboard(stats),
    )
    await callback.answer()


# ── List views ─────────────────────────────────────────────────────────── #

@router.callback_query(F.data == "atu:pending")
async def cb_list_pending(callback: CallbackQuery, uow, user: User) -> None:
    svc = TopUpService(uow)
    reqs = await svc.get_pending_for_admin(limit=20)
    if not reqs:
        await safe_edit_text(callback, "⏳ درخواست در انتظاری وجود ندارد.",
            reply_markup=single_button_kb(back_button("atu:menu")))
        await callback.answer()
        return
    await safe_edit_text(callback, "⏳ <b>درخواست‌های در انتظار</b>",
        reply_markup=admin_topup_list_keyboard(reqs))
    await callback.answer()


@router.callback_query(F.data == "atu:approved")
async def cb_list_approved(callback: CallbackQuery, uow, user: User) -> None:
    svc = TopUpService(uow)
    reqs = await svc.get_all_for_admin(status=TopUpStatus.APPROVED, limit=20)
    if not reqs:
        await safe_edit_text(callback, "✅ درخواست تأییدشده‌ای وجود ندارد.",
            reply_markup=single_button_kb(back_button("atu:menu")))
        await callback.answer()
        return
    await safe_edit_text(callback, "✅ <b>درخواست‌های تأیید شده</b>",
        reply_markup=admin_topup_list_keyboard(reqs))
    await callback.answer()


@router.callback_query(F.data == "atu:rejected")
async def cb_list_rejected(callback: CallbackQuery, uow, user: User) -> None:
    svc = TopUpService(uow)
    reqs = await svc.get_all_for_admin(status=TopUpStatus.REJECTED, limit=20)
    if not reqs:
        await safe_edit_text(callback, "❌ درخواست ردشده‌ای وجود ندارد.",
            reply_markup=single_button_kb(back_button("atu:menu")))
        await callback.answer()
        return
    await safe_edit_text(callback, "❌ <b>درخواست‌های رد شده</b>",
        reply_markup=admin_topup_list_keyboard(reqs))
    await callback.answer()


@router.callback_query(F.data == "atu:all")
async def cb_list_all(callback: CallbackQuery, uow, user: User) -> None:
    svc = TopUpService(uow)
    reqs = await svc.get_all_for_admin(limit=30)
    if not reqs:
        await safe_edit_text(callback, "📋 درخواستی وجود ندارد.",
            reply_markup=single_button_kb(back_button("atu:menu")))
        await callback.answer()
        return
    await safe_edit_text(callback, "📋 <b>همه درخواست‌ها</b>",
        reply_markup=admin_topup_list_keyboard(reqs))
    await callback.answer()


# ── View detail ────────────────────────────────────────────────────────── #

async def _show_request_detail(callback: CallbackQuery, uow, request_id_prefix: str) -> None:
    svc = TopUpService(uow)
    all_reqs = await svc.get_all_for_admin(limit=200)
    req = next((r for r in all_reqs if r.id.startswith(request_id_prefix)), None)
    if not req:
        await callback.answer("درخواست یافت نشد", show_alert=True)
        return
    await safe_edit_text(callback, _req_text(req),
        reply_markup=admin_topup_detail_keyboard(req))


@router.callback_query(F.data.startswith("atu:view:"))
async def cb_view_request(callback: CallbackQuery, uow, user: User) -> None:
    prefix = callback.data.split(":", 2)[2]
    await _show_request_detail(callback, uow, prefix)
    await callback.answer()


# ── Approve ────────────────────────────────────────────────────────────── #

@router.callback_query(F.data.startswith("atu:ok:"))
async def cb_approve(callback: CallbackQuery, uow, user: User) -> None:
    prefix = callback.data.split(":", 2)[2]
    svc = TopUpService(uow)
    all_reqs = await svc.get_all_for_admin(limit=200)
    req = next((r for r in all_reqs if r.id.startswith(prefix)), None)
    if not req:
        await callback.answer("درخواست یافت نشد", show_alert=True)
        return
    try:
        approved = await svc.approve_request(req.id, user.id)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await uow.flush()

    await uow.commit()

    # Audit log
    api = AdminService(uow)
    await api.log_action(user, LogAction.SETTINGS_CHANGE,
        target_type="topup_request", target_id=req.id,
        description=f"تأیید شارژ {req.tracking_code} — {format_price(req.amount)} تومان")
    await uow.flush()

    await uow.commit()

    # Notify user
    if approved and approved.user:
        notifier = NotificationService(callback.bot, uow)
        await notifier.notify_user(approved.user.telegram_id,
            "━━━━━━━━━━━━━━\n"
            "✅ <b>پرداخت با موفقیت تأیید شد</b>\n\n"
            f"💰 مبلغ شارژ: <b>{format_price(approved.amount)} تومان</b>\n"
            f"💳 روش پرداخت: {approved.payment_method.label}\n"
            f"🆔 شماره پیگیری: <code>{approved.tracking_code}</code>\n"
            f"📅 تاریخ: {approved.approved_at.strftime('%Y-%m-%d %H:%M') if approved.approved_at else '—'}\n"
            f"💼 موجودی جدید: <b>{format_price(approved.user.wallet_balance)} تومان</b>\n"
            "━━━━━━━━━━━━━━\n\n"
            "مبلغ با موفقیت به کیف پول شما اضافه شد."
        )

    await safe_edit_text(callback,
        f"✅ درخواست <code>{req.tracking_code}</code> تأیید شد.\n"
        f"💰 مبلغ {format_price(req.amount)} تومان به کیف پول کاربر اضافه شد.",
        reply_markup=single_button_kb(back_button("atu:menu")),
    )
    await callback.answer("تأیید شد")


# ── Reject ─────────────────────────────────────────────────────────────── #

@router.callback_query(F.data.startswith("atu:no:"))
async def cb_reject_start(callback: CallbackQuery, state: FSMContext) -> None:
    prefix = callback.data.split(":", 2)[2]
    await state.set_data({"reject_request_prefix": prefix})
    await state.set_state(AdminTopUpStates.waiting_reject_reason)
    await callback.message.answer("❌ دلیل رد پرداخت را بنویسید (یا /skip):")
    await callback.answer()


@router.message(AdminTopUpStates.waiting_reject_reason)
async def do_reject(message: Message, state: FSMContext, uow, user: User) -> None:
    data = await state.get_data()
    prefix = data.get("reject_request_prefix")
    reason = message.text.strip() if message.text and not message.text.startswith("/skip") else "بدون دلیل"

    svc = TopUpService(uow)
    all_reqs = await svc.get_all_for_admin(limit=200)
    req = next((r for r in all_reqs if r.id.startswith(prefix)), None)
    if not req:
        await state.clear()
        await message.answer("❌ درخواست یافت نشد.")
        return

    try:
        rejected = await svc.reject_request(req.id, user.id, reason)
    except ValueError as e:
        await state.clear()
        await message.answer(f"⚠️ {e}")
        return
    await uow.flush()

    await uow.commit()

    # Audit log
    api = AdminService(uow)
    await api.log_action(user, LogAction.SETTINGS_CHANGE,
        target_type="topup_request", target_id=req.id,
        description=f"رد شارژ {req.tracking_code} — دلیل: {reason}")
    await uow.flush()

    await uow.commit()

    # Notify user
    if rejected and rejected.user:
        notifier = NotificationService(message.bot, uow)
        await notifier.notify_user(rejected.user.telegram_id,
            "❌ <b>پرداخت شما رد شد.</b>\n\n"
            f"🆔 شماره پیگیری: <code>{rejected.tracking_code}</code>\n"
            f"📝 دلیل: {reason}\n\n"
            "مبلغی به کیف پول شما اضافه نشد."
        )

    await state.clear()
    await message.answer(
        f"❌ درخواست <code>{req.tracking_code}</code> رد شد.",
        reply_markup=single_button_kb(back_button("atu:menu")),
    )


# ── Request new receipt ────────────────────────────────────────────────── #

@router.callback_query(F.data.startswith("atu:rs:"))
async def cb_request_new_receipt(callback: CallbackQuery, uow, user: User) -> None:
    prefix = callback.data.split(":", 2)[2]
    svc = TopUpService(uow)
    all_reqs = await svc.get_all_for_admin(limit=200)
    req = next((r for r in all_reqs if r.id.startswith(prefix)), None)
    if not req:
        await callback.answer("درخواست یافت نشد", show_alert=True)
        return

    try:
        updated = await svc.request_new_receipt(req.id, user.id)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await uow.flush()

    await uow.commit()

    # Notify user to resubmit
    if updated and updated.user:
        notifier = NotificationService(callback.bot, uow)
        await notifier.notify_user(updated.user.telegram_id,
            "⚠️ <b>رسید پرداخت شما مورد تأیید قرار نگرفت.</b>\n\n"
            f"🔢 کد پیگیری: <code>{updated.tracking_code}</code>\n\n"
            "لطفاً رسید صحیح را مجدداً از بخش «شارژ حساب» ارسال کنید."
        )

    await safe_edit_text(callback,
        f"🔄 درخواست رسید مجدد برای <code>{req.tracking_code}</code> ارسال شد.",
        reply_markup=single_button_kb(back_button("atu:menu")),
    )
    await callback.answer("درخواست ارسال شد")


# ── Search by tracking code ────────────────────────────────────────────── #

@router.callback_query(F.data == "atu:search")
async def cb_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminTopUpStates.waiting_search_code)
    await callback.message.answer("🔍 کد پیگیری را ارسال کنید (مثال: TOPUP-A3F9B2):")
    await callback.answer()


@router.message(AdminTopUpStates.waiting_search_code)
async def do_search(message: Message, state: FSMContext, uow, user: User) -> None:
    code = message.text.strip() if message.text else ""
    if not code:
        await message.answer("⚠️ کد پیگیری را وارد کنید:")
        return
    svc = TopUpService(uow)
    req = await svc.search_by_tracking(code)
    await state.clear()
    if not req:
        await message.answer("❌ درخواستی با این کد پیگیری یافت نشد.",
            reply_markup=single_button_kb(back_button("atu:menu")))
        return
    await message.answer(_req_text(req),
        reply_markup=admin_topup_detail_keyboard(req))


# ── Manual Credit ──────────────────────────────────────────────────────── #

@router.callback_query(F.data == "atu:credit")
async def cb_credit_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminTopUpStates.waiting_credit_user)
    await callback.message.answer(
        "💰 <b>شارژ دستی کاربر</b>\n\n"
        "🆔 آیدی عددی تلگرام کاربر را ارسال کنید:"
    )
    await callback.answer()


@router.message(AdminTopUpStates.waiting_credit_user)
async def do_credit_user(message: Message, state: FSMContext, uow, user: User) -> None:
    raw = message.text.strip() if message.text else ""
    if not raw.isdigit():
        await message.answer("⚠️ آیدی عددی معتبر ارسال کنید:")
        return
    tg_id = int(raw)
    us = UserService(uow)
    target = await us.get_by_telegram_id(tg_id)
    if not target:
        await message.answer("❌ کاربری با این آیدی یافت نشد.")
        await state.clear()
        return
    await state.update_data(
        credit_user_id=target.id,
        credit_tg_id=tg_id,
        credit_name=target.display_name,
    )
    await state.set_state(AdminTopUpStates.waiting_credit_amount)
    await message.answer(
        f"👤 کاربر: <b>{target.display_name}</b>\n"
        f"🆔 آیدی: <code>{tg_id}</code>\n"
        f"💼 موجودی فعلی: <b>{format_price(target.wallet_balance)} تومان</b>\n\n"
        "💰 مبلغ شارژ را به تومان ارسال کنید:"
    )


@router.message(AdminTopUpStates.waiting_credit_amount)
async def do_credit_amount(message: Message, state: FSMContext, uow, user: User) -> None:
    raw = message.text.strip().replace(",", "") if message.text else ""
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("⚠️ مبلغ معتبر (عدد مثبت) ارسال کنید:")
        return
    amount = int(raw)
    await state.update_data(credit_amount=amount)
    await state.set_state(AdminTopUpStates.waiting_credit_note)
    await message.answer(f"💰 مبلغ: <b>{format_price(amount)} تومان</b>\n\n📝 توضیحات (اختیاری، یا /skip):")


@router.message(AdminTopUpStates.waiting_credit_note)
async def do_credit_note(message: Message, state: FSMContext, uow, user: User) -> None:
    data = await state.get_data()
    target_id = data["credit_user_id"]
    amount = data["credit_amount"]
    note = message.text.strip() if message.text and not message.text.startswith("/skip") else "شارژ دستی توسط ادمین"

    svc = TopUpService(uow)
    try:
        target, txn = await svc.admin_credit(target_id, amount, user.id, note)
    except ValueError as e:
        await state.clear()
        await message.answer(f"⚠️ {e}")
        return
    await uow.flush()

    await uow.commit()

    # Audit log
    api = AdminService(uow)
    await api.log_action(user, LogAction.SETTINGS_CHANGE,
        target_type="wallet", target_id=target.id,
        description=f"شارژ دستی {format_price(amount)} تومان برای {target.display_name}")
    await uow.flush()

    await uow.commit()

    # Notify user
    notifier = NotificationService(message.bot, uow)
    await notifier.notify_user(target.telegram_id,
        f"💰 <b>کیف پول شما شارژ شد</b>\n\n"
        f"💰 مبلغ: <b>{format_price(amount)} تومان</b>\n"
        f"💼 موجودی جدید: <b>{format_price(target.wallet_balance)} تومان</b>\n"
        f"📝 {note}"
    )

    await state.clear()
    await message.answer(
        f"✅ <b>{format_price(amount)} تومان</b> به کیف پول <b>{target.display_name}</b> اضافه شد.\n"
        f"💼 موجودی جدید: <b>{format_price(target.wallet_balance)} تومان</b>",
        reply_markup=single_button_kb(back_button("atu:menu")),
    )


# ── Manual Debit ───────────────────────────────────────────────────────── #

@router.callback_query(F.data == "atu:debit")
async def cb_debit_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminTopUpStates.waiting_debit_user)
    await callback.message.answer(
        "➖ <b>کسر موجودی کاربر</b>\n\n"
        "🆔 آیدی عددی تلگرام کاربر را ارسال کنید:"
    )
    await callback.answer()


@router.message(AdminTopUpStates.waiting_debit_user)
async def do_debit_user(message: Message, state: FSMContext, uow, user: User) -> None:
    raw = message.text.strip() if message.text else ""
    if not raw.isdigit():
        await message.answer("⚠️ آیدی عددی معتبر ارسال کنید:")
        return
    tg_id = int(raw)
    us = UserService(uow)
    target = await us.get_by_telegram_id(tg_id)
    if not target:
        await message.answer("❌ کاربری با این آیدی یافت نشد.")
        await state.clear()
        return
    await state.update_data(
        debit_user_id=target.id,
        debit_tg_id=tg_id,
        debit_name=target.display_name,
    )
    await state.set_state(AdminTopUpStates.waiting_debit_amount)
    await message.answer(
        f"👤 کاربر: <b>{target.display_name}</b>\n"
        f"🆔 آیدی: <code>{tg_id}</code>\n"
        f"💼 موجودی فعلی: <b>{format_price(target.wallet_balance)} تومان</b>\n\n"
        "💰 مبلغ کسر را به تومان ارسال کنید:"
    )


@router.message(AdminTopUpStates.waiting_debit_amount)
async def do_debit_amount(message: Message, state: FSMContext, uow, user: User) -> None:
    raw = message.text.strip().replace(",", "") if message.text else ""
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("⚠️ مبلغ معتبر (عدد مثبت) ارسال کنید:")
        return
    amount = int(raw)
    await state.update_data(debit_amount=amount)
    await state.set_state(AdminTopUpStates.waiting_debit_reason)
    await message.answer(f"💰 مبلغ: <b>{format_price(amount)} تومان</b>\n\n📝 دلیل کسر موجودی را بنویسید:")


@router.message(AdminTopUpStates.waiting_debit_reason)
async def do_debit_reason(message: Message, state: FSMContext, uow, user: User) -> None:
    data = await state.get_data()
    target_id = data["debit_user_id"]
    amount = data["debit_amount"]
    reason = message.text.strip() if message.text else "کسر دستی توسط ادمین"

    svc = TopUpService(uow)
    try:
        target, txn = await svc.admin_debit(target_id, amount, user.id, reason)
    except ValueError as e:
        await state.clear()
        await message.answer(f"❌ {e}")
        return
    await uow.flush()

    await uow.commit()

    # Audit log
    api = AdminService(uow)
    await api.log_action(user, LogAction.SETTINGS_CHANGE,
        target_type="wallet", target_id=target.id,
        description=f"کسر دستی {format_price(amount)} تومان از {target.display_name} — {reason}")
    await uow.flush()

    await uow.commit()

    # Notify user
    notifier = NotificationService(message.bot, uow)
    await notifier.notify_user(target.telegram_id,
        f"➖ <b>مبلغی از کیف پول شما کسر شد</b>\n\n"
        f"💰 مبلغ: <b>{format_price(amount)} تومان</b>\n"
        f"💼 موجودی جدید: <b>{format_price(target.wallet_balance)} تومان</b>\n"
        f"📝 دلیل: {reason}"
    )

    await state.clear()
    await message.answer(
        f"✅ <b>{format_price(amount)} تومان</b> از کیف پول <b>{target.display_name}</b> کسر شد.\n"
        f"💼 موجودی جدید: <b>{format_price(target.wallet_balance)} تومان</b>\n"
        f"📝 دلیل: {reason}",
        reply_markup=single_button_kb(back_button("atu:menu")),
    )


# ── Top-Up Amounts Management ──────────────────────────────────────────── #

@router.callback_query(F.data == "atu:amounts")
async def cb_amounts_list(callback: CallbackQuery, uow, user: User) -> None:
    svc = TopUpService(uow)
    amounts = await svc.get_all_amounts()
    await safe_edit_text(callback, "🏷 <b>مبلغ‌های شارژ</b>",
        reply_markup=admin_topup_amounts_keyboard(amounts))
    await callback.answer()


@router.callback_query(F.data == "atua:add")
async def cb_amount_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminTopUpStates.waiting_amount_value)
    await callback.message.answer("💰 مبلغ جدید را به تومان ارسال کنید (فقط عدد):")
    await callback.answer()


@router.message(AdminTopUpStates.waiting_amount_value)
async def do_amount_value(message: Message, state: FSMContext, uow, user: User) -> None:
    raw = message.text.strip().replace(",", "") if message.text else ""
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("⚠️ عدد مثبت معتبر ارسال کنید:")
        return
    amount = int(raw)
    await state.update_data(new_amount_value=amount)
    await state.set_state(AdminTopUpStates.waiting_amount_label)
    await message.answer(f"💰 مبلغ: <b>{format_price(amount)} تومان</b>\n\n🏷 برچسب (اختیاری، یا /skip):")


@router.message(AdminTopUpStates.waiting_amount_label)
async def do_amount_label(message: Message, state: FSMContext, uow, user: User) -> None:
    data = await state.get_data()
    amount = data["new_amount_value"]
    label = message.text.strip() if message.text and not message.text.startswith("/skip") else None

    svc = TopUpService(uow)
    await svc.create_amount(amount, label=label)
    await uow.flush()

    await uow.commit()

    await state.clear()
    await message.answer(
        f"✅ مبلغ <b>{format_price(amount)} تومان</b> اضافه شد.",
        reply_markup=single_button_kb(back_button("atu:amounts")),
    )


@router.callback_query(F.data.startswith("atua:tog:"))
async def cb_amount_toggle(callback: CallbackQuery, uow, user: User) -> None:
    prefix = callback.data.split(":", 2)[2]
    svc = TopUpService(uow)
    amounts = await svc.get_all_amounts()
    target = next((a for a in amounts if a.id.startswith(prefix)), None)
    if not target:
        await callback.answer("مبلغ یافت نشد", show_alert=True)
        return
    await svc.toggle_amount(target.id)
    await callback.answer("تغییر کرد")
    # Refresh list
    amounts = await svc.get_all_amounts()
    await safe_edit_text(callback, "🏷 <b>مبلغ‌های شارژ</b>",
        reply_markup=admin_topup_amounts_keyboard(amounts))


@router.callback_query(F.data.startswith("atua:del:"))
async def cb_amount_delete(callback: CallbackQuery, uow, user: User) -> None:
    prefix = callback.data.split(":", 2)[2]
    svc = TopUpService(uow)
    amounts = await svc.get_all_amounts()
    target = next((a for a in amounts if a.id.startswith(prefix)), None)
    if not target:
        await callback.answer("مبلغ یافت نشد", show_alert=True)
        return
    await svc.delete_amount(target.id)
    await callback.answer("حذف شد")
    amounts = await svc.get_all_amounts()
    await safe_edit_text(callback, "🏷 <b>مبلغ‌های شارژ</b>",
        reply_markup=admin_topup_amounts_keyboard(amounts))


@router.callback_query(F.data.startswith("atua:view:"))
async def cb_amount_view(callback: CallbackQuery, uow, user: User) -> None:
    prefix = callback.data.split(":", 2)[2]
    svc = TopUpService(uow)
    amounts = await svc.get_all_amounts()
    target = next((a for a in amounts if a.id.startswith(prefix)), None)
    if not target:
        await callback.answer("مبلغ یافت نشد", show_alert=True)
        return
    label = target.label or f"{format_price(target.amount)} تومان"
    text = (
        f"🏷 <b>{label}</b>\n\n"
        f"💰 مبلغ: {format_price(target.amount)} تومان\n"
        f"📊 وضعیت: {'🟢 فعال' if target.is_active else '🔴 غیرفعال'}\n"
        f"🔢 ترتیب: {target.display_order}"
    )
    await safe_edit_text(callback, text,
        reply_markup=admin_topup_amount_detail_keyboard(target.id, target.is_active))
    await callback.answer()


@router.callback_query(F.data.startswith("atua:edit:"))
async def cb_amount_edit(callback: CallbackQuery, state: FSMContext) -> None:
    prefix = callback.data.split(":", 2)[2]
    await state.set_data({"edit_amount_prefix": prefix})
    await state.set_state(AdminTopUpStates.waiting_amount_value)
    await callback.message.answer("💰 مبلغ جدید را به تومان ارسال کنید:")
    await callback.answer()
