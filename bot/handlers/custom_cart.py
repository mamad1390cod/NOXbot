"""Custom cart and registration flow handlers."""

import json
from datetime import datetime

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.admin import payment_review_keyboard
from bot.keyboards.common import back_button
from bot.keyboards.custom_keyboard import custom_cart_keyboard
from bot.models.payment import PaymentMethod
from bot.models.user import User
from bot.services.custom import CustomService
from bot.services.custom_cart import CustomCartService
from bot.services.notification import NotificationService
from bot.services.payment import PaymentService
from bot.services.settings import SettingsService
from bot.states import CustomCartStates, PaymentStates
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="custom_cart")


async def _show_custom_cart(callback: CallbackQuery, uow, user: User) -> None:
    custom_cart_service = CustomCartService(uow)
    summary = await custom_cart_service.get_cart_summary(user.id)
    if not summary["items"]:
        text = "🎯 <b>سبد کاستوم شما خالی است.</b>"
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[[back_button("menu:home")]]
        )
        await safe_edit_text(callback, text, reply_markup=kb)
        await callback.answer()
        return

    lines = []
    for item in summary["items"]:
        c = item.custom
        if not c:
            continue
        fee = "رایگان" if c.type.value == "free" else f"{format_price(c.entry_fee)} تومان"
        lines.append(f"• {c.title} — {fee}")
    text = (
        "🎯 <b>سبد کاستوم شما</b>\n\n"
        + "\n".join(lines)
        + f"\n\n💰 مبلغ کل: <b>{format_price(summary['total_price'])} تومان</b>"
    )
    kb = custom_cart_keyboard(summary["items"])
    await safe_edit_text(callback, text, reply_markup=kb)
    await callback.answer()


def price_format(n):
    return format_price(n)


@router.callback_query(F.data == "menu:custom_cart")
async def cb_custom_cart(callback: CallbackQuery, uow, user: User) -> None:
    await _show_custom_cart(callback, uow, user)


@router.callback_query(F.data == "customcart:clear")
async def cb_custom_cart_clear(callback: CallbackQuery, uow, user: User) -> None:
    custom_cart_service = CustomCartService(uow)
    await custom_cart_service.clear_cart(user.id)
    await callback.answer("سبد کاستوم خالی شد")
    await _show_custom_cart(callback, uow, user)


@router.callback_query(F.data.startswith("ccart_view:"))
async def cb_custom_cart_view(callback: CallbackQuery, uow, user: User) -> None:
    """View a custom in the cart; allow remove."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("آیتم یافت نشد", show_alert=True)
        return
    item_id = parts[2]
    custom_cart_service = CustomCartService(uow)
    cart = await custom_cart_service.get_cart(user.id)
    items = await custom_cart_service.get_items(user.id)
    item = next((i for i in items if i.id == item_id), None)
    if not item:
        await callback.answer("آیتم یافت نشد", show_alert=True)
        return
    await custom_cart_service.remove_item(user.id, item_id)
    await callback.answer("حذف شد")
    await _show_custom_cart(callback, uow, user)


@router.callback_query(F.data == "customcart:register")
async def cb_custom_cart_register(
    callback: CallbackQuery,
    uow, user: User,
    state: FSMContext,
) -> None:
    """Begin registration: ask for CODM username."""
    custom_cart_service = CustomCartService(uow)
    items = await custom_cart_service.get_items(user.id)
    if not items:
        await callback.answer("سبد کاستوم خالی است", show_alert=True)
        return

    # Verify all customs still can register
    for item in items:
        if not (item.custom and item.custom.can_register):
            await callback.answer(
                f"ثبت‌نام '{item.custom.title if item.custom else '? '}' بسته شده یا ظرفیت پر است. ",
                show_alert=True,
            )
            return

    await state.set_data({"custom_items": [i.id for i in items]})
    from bot.states import CustomCartStates
    await state.set_state(CustomCartStates.waiting_codm_username)
    await callback.message.answer(
        "👤 <b>ثبت‌نام در کاستوم</b>\n\n"
        "لطفاً نام کاربری CODM خود را وارد کنید:"
    )
    await callback.answer()


@router.message(CustomCartStates.waiting_codm_username)
async def collect_codm_username(
    message: Message,
    uow, user: User,
    state: FSMContext,
) -> None:
    username = message.text.strip()
    if not username or len(username) > 100:
        await message.answer("⚠️ لطفاً یک نام کاربری معتبر (حداکثر 100 کاراکتر) وارد کنید:")
        return
    await state.update_data(codm_username=username)
    await state.set_state(CustomCartStates.waiting_confirmation)

    data = await state.get_data()
    item_ids = data.get("custom_items", [])
    custom_cart_service = CustomCartService(uow)
    items = await custom_cart_service.get_items(user.id)
    selected = [i for i in items if i.id in item_ids]

    lines = []
    total = 0
    for item in selected:
        if not item.custom:
            continue
        lines.append(f"• {item.custom.title}")
        total += 0  # will recompute

    # Recompute total
    total = sum(
        (i.custom.entry_fee if i.custom and i.custom.type.value == "paid" else 0)
        for i in selected
    )

    text = (
        "📋 <b>تایید ثبت‌نام در کاستوم</b>\n\n"
        "کاستوم‌های انتخابی:\n"
        + "\n".join(lines)
        + f"\n\n👤 نام CODM: <code>{username}</code>"
        + (f"\n💰 مبلغ قابل پرداخت: <b>{format_price(total)} تومان</b>" if total else "\n💰 رایگان")
        + "\n\nآیا اطلاعات صحیح است؟"
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ تایید", callback_data="customreg:confirm"),
         types.InlineKeyboardButton(text="❌ انصراف", callback_data="action:cancel")]
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "customreg:confirm")
async def confirm_custom_registration(
    callback: CallbackQuery,
    uow, user: User,
    bot,
    state: FSMContext,
) -> None:
    """Finalize custom registration. Free → done; paid → payment + receipt."""
    data = await state.get_data()
    codm_username = data.get("codm_username")
    item_ids = data.get("custom_items", [])
    custom_cart_service = CustomCartService(uow)
    items = await custom_cart_service.get_items(user.id)
    selected = [i for i in items if i.id in item_ids]

    custom_service = CustomService(uow)
    total = sum(
        (i.custom.entry_fee if i.custom and i.custom.type.value == "paid" else 0)
        for i in selected
    )

    # Register each custom (status depends on paid/free handled below)
    registrations = []
    for item in selected:
        if not item.custom:
            continue
        reg = await custom_service.register_user(
            user_id=user.id,
            custom_id=item.custom.id,
            codm_username=codm_username,
            status="confirmed" if item.custom.type.value == "free" else "pending",
        )
        registrations.append(reg)
    await uow.flush()

    # If all free → done
    paid_items = [i for i in selected if i.custom and i.custom.type.value == "paid"]
    if not paid_items:
        await state.clear()
        text = "🎉 ثبت‌نام شما در کاستوم با موفقیت انجام شد!"
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("menu:customs")]])
        await safe_edit_text(callback, text, reply_markup=kb)
        await callback.answer()
        return

    # Paid → create one payment (attach first registration), ask for receipt
    settings_service = SettingsService(uow)
    payment_info = await settings_service.get_payment_info()
    payment_service = PaymentService(uow)

    first_reg = registrations[0] if registrations else None
    payment = await payment_service.create_payment(
        user_id=user.id,
        amount=total,
        method=PaymentMethod.CARD,
        custom_registration_id=first_reg.id if first_reg else None,
    )
    await uow.flush()

    text = (
        "💳 <b>پرداخت برای ثبت‌نام</b>\n\n"
        f"💰 مبلغ: <b>{format_price(total)} تومان</b>\n\n"
    )
    if payment_info["card_number"]:
        text += (
            f"🏦 بانک: {payment_info['bank_name'] or '-'}\n"
            f"💳 شماره کارت: <code>{payment_info['card_number']}</code>\n"
            f"👤 به نام: {payment_info['card_holder'] or '-'}\n\n"
        )
    text += "پس از پرداخت، تصویر رسید را ارسال کنید."

    await state.set_data({"payment_id": payment.id, **data})
    from bot.states import CustomCartStates
    await state.set_state(CustomCartStates.waiting_payment_receipt)

    await safe_edit_text(callback, 
        text,
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="❌ انصراف", callback_data="action:cancel")]]
        ),
    )
    await callback.answer()


@router.message(CustomCartStates.waiting_payment_receipt, F.photo)
async def custom_payment_receipt(
    message: Message,
    uow, user: User,
    bot,
    state: FSMContext,
) -> None:
    """Receive custom payment receipt and notify admin."""
    data = await state.get_data()
    payment_id = data.get("payment_id")
    payment_service = PaymentService(uow)
    if payment_id:
        await payment_service.update_receipt(payment_id, message.photo[-1].file_id)
        await uow.flush()
        payment = await payment_service.get_payment(payment_id)
        amount = payment.amount if payment else 0
    else:
        amount = 0

    _now = datetime.now()
    text = (
        "💳 <b>رسید پرداخت کاستوم</b>\n\n"
        f"🆔 آیدی تلگرام: <code>{user.telegram_id}</code>\n"
        f"🆔 چت آیدی: <code>{user.telegram_id}</code>\n"
        f"👤 نام کاربری: @{user.username or '-'}\n"
        f"👤 نام: {user.first_name or ''} {user.last_name or ''}\n\n"
        f"💰 مبلغ: <b>{format_price(amount)} تومان</b>\n\n"
        f"📅 تاریخ: {_now.strftime('%Y-%m-%d')}\n"
        f"🕒 زمان: {_now.strftime('%H:%M:%S')}\n"
        f"🏷 نوع درخواست: پرداخت کاستوم"
    )
    notifier = NotificationService(bot, uow)
    await notifier.send_to_admins(
        text=text,
        photo=message.photo[-1].file_id,
        reply_markup=payment_review_keyboard(payment_id) if payment_id else None,
    )
    await state.clear()
    await message.answer("✅ رسید شما ارسال شد. پس از تایید ادمین، ثبت‌نام شما تایید خواهد شد.")


@router.message(CustomCartStates.waiting_payment_receipt)
async def custom_receipt_invalid(message: Message) -> None:
    await message.answer("⚠️ لطفاً تصویر رسید پرداخت را ارسال کنید.")

# The next step of this flow is driven by inline buttons. Without this handler a
# typed answer was silently ignored and the flow looked frozen.
@router.message(CustomCartStates.waiting_confirmation)
async def _hint_customcartstates_waiting_confirmation(message: Message) -> None:
    await message.answer("برای ادامه، دکمه «✅ تایید» یا «❌ انصراف» را بزنید 👆")
