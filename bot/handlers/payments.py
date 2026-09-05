"""Checkout and payment handlers."""

from datetime import datetime

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import back_button
from bot.models.payment import PaymentMethod
from bot.models.user import User
from bot.services.cart import CartService
from bot.services.notification import NotificationService
from bot.services.order import OrderService
from bot.services.payment import PaymentService
from bot.services.settings import SettingsService
from bot.states import PaymentStates
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="payments")


@router.callback_query(F.data == "checkout:confirm")
async def cb_checkout_confirm(
    callback: CallbackQuery,
    uow, user: User,
) -> None:
    """Create the order and show payment instructions."""
    cart_service = CartService(uow)
    summary = await cart_service.get_cart_summary(user.id)
    if not summary["items"]:
        await callback.answer("سبد خرید خالی است", show_alert=True)
        return

    settings_service = SettingsService(uow)
    payment_info = await settings_service.get_payment_info()

    order_service = OrderService(uow, notifier=NotificationService(callback.bot, uow))
    try:
        order = await order_service.create_order_from_cart(
            user_id=user.id,
            payment_method=PaymentMethod.CARD,
        )
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return

    await uow.flush()

    text = (
        "💳 <b>پرداخت سفارش</b>\n\n"
        f"🧾 کد سفارش: <code>{order.order_number}</code>\n"
        f"💰 مبلغ قابل پرداخت: <b>{format_price(order.final_amount)} تومان</b>\n\n"
    )
    if payment_info["card_number"]:
        text += (
            f"🏦 بانک: {payment_info['bank_name'] or '-'}\n"
            f"💳 شماره کارت: <code>{payment_info['card_number']}</code>\n"
            f"👤 به نام: {payment_info['card_holder'] or '-'}\n\n"
        )
    text += "📤 پس از پرداخت، تصویر رسید را ارسال کنید."

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📤 ارسال رسید", callback_data=f"pay:submit:{order.id}")],
        [back_button("menu:home")],
    ])
    await safe_edit_text(callback, text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("pay:submit:"))
async def cb_payment_submit(
    callback: CallbackQuery,
    uow, user: User,
    state: FSMContext,
) -> None:
    """Begin receipt submission for an order."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("سفارش یافت نشد", show_alert=True)
        return
    order_id = parts[2]
    order_service = OrderService(uow)
    order = await order_service.get_order(order_id)
    if not order:
        await callback.answer("سفارش یافت نشد", show_alert=True)
        return

    payment_service = PaymentService(uow)
    payments = await payment_service.get_user_payments(user.id)
    payment = next((p for p in payments if p.order_id == order_id), None)
    if not payment:
        payment = await payment_service.create_payment(
            user_id=user.id,
            amount=order.final_amount,
            method=PaymentMethod.CARD,
            order_id=order_id,
        )
        await uow.flush()

    await state.set_data({"payment_id": payment.id, "order_id": order_id})
    await state.set_state(PaymentStates.waiting_receipt)

    await safe_edit_text(callback, 
        "📤 <b>ارسال رسید پرداخت</b>\n\n"
        "لطفاً تصویر رسید پرداخت خود را ارسال کنید.\n"
        "برای انصراف روی دکمه زیر بزنید.",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="❌ انصراف", callback_data="action:cancel")]]
        ),
    )
    await callback.answer()


@router.message(PaymentStates.waiting_receipt, F.photo)
async def payment_receipt_received(
    message: Message,
    uow, user: User,
    bot,
    state: FSMContext,
) -> None:
    """Receive the payment receipt image from the user."""
    data = await state.get_data()
    payment_id = data.get("payment_id")
    order_id = data.get("order_id")
    if not payment_id:
        await state.clear()
        return

    photo = message.photo[-1]

    payment_service = PaymentService(uow)

    # Anti-abuse: receipt reuse — same file_id already linked to another payment.
    from sqlalchemy import select
    from bot.models.payment import Payment
    existing_receipt = (await uow.session.execute(
        select(Payment.id).where(Payment.receipt_url == photo.file_id).limit(1)
    )).scalar_one_or_none()
    if existing_receipt and existing_receipt != payment_id:
        from bot.services.abuse import AntiAbuseService
        from bot.models.abuse import AbuseType
        await AntiAbuseService(uow).record(
            AbuseType.RECEIPT_REUSE, user=user,
            event_data=f"file_id={photo.file_id} reused from payment {existing_receipt}",
            source="payment",
        )

    await payment_service.update_receipt(payment_id, photo.file_id)
    await uow.flush()

    payment = await payment_service.get_payment(payment_id)
    amount = payment.amount if payment else 0

    # Advance the order lifecycle: WAITING_PAYMENT -> PAYMENT_UPLOADED.
    order_service = OrderService(uow, notifier=NotificationService(bot, uow))
    order = await order_service.get_order(order_id) if order_id else None
    if order:
        try:
            await order_service.submit_payment(order, photo.file_id, is_system=False)
        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.exception("submit_payment failed: %s", e)

    _now = datetime.now()
    number = order.order_number if order else (order_id or "—")
    text = (
        "💳 <b>رسید پرداخت جدید</b>\n\n"
        f"🆔 آیدی تلگرام: <code>{user.telegram_id}</code>\n"
        f"🆔 چت آیدی: <code>{user.telegram_id}</code>\n"
        f"👤 نام کاربری: @{user.username or '-'}\n"
        f"👤 نام: {user.first_name or ''} {user.last_name or ''}\n\n"
        f"🧾 کد سفارش: <code>{number}</code>\n"
        f"💰 مبلغ: <b>{format_price(amount)} تومان</b>\n\n"
        f"📅 تاریخ: {_now.strftime('%Y-%m-%d')}\n"
        f"🕒 زمان: {_now.strftime('%H:%M:%S')}\n"
        f"🏷 نوع درخواست: پرداخت"
    )

    notifier = NotificationService(bot, uow)
    from bot.keyboards.admin import payment_review_keyboard
    await notifier.send_to_admins(
        text=text,
        photo=photo.file_id,
        reply_markup=payment_review_keyboard(payment_id),
    )

    await state.clear()
    await message.answer(
        "✅ رسید شما ارسال شد. پس از تایید ادمین، محصول شما ارسال خواهد شد."
    )


@router.message(PaymentStates.waiting_receipt)
async def payment_receipt_invalid(message: Message) -> None:
    """Handle non-photo messages while waiting for receipt."""
    await message.answer("⚠️ لطفاً تصویر رسید پرداخت را ارسال کنید.")