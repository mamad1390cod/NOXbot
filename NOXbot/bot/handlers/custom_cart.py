"""Custom cart and registration flow handlers."""

import json
import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import back_button
from bot.keyboards.custom_keyboard import custom_cart_keyboard
from bot.models.payment import PaymentMethod, PaymentStatus
from bot.models.user import User
from bot.services.custom import CustomService
from bot.services.custom_cart import CustomCartService
from bot.services.payment import PaymentService
from bot.services.wallet_payment import WalletPaymentService, WalletPaymentError
from bot.states import CustomCartStates
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="custom_cart")
logger = logging.getLogger(__name__)


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
    """Finalize custom registration. Free → done; paid → wallet payment."""
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

    # Check wallet balance for paid customs
    paid_items = [i for i in selected if i.custom and i.custom.type.value == "paid"]
    if paid_items:
        wallet_balance = user.wallet_balance or 0
        if wallet_balance < total:
            # Insufficient balance
            shortage = total - wallet_balance
            await state.clear()
            text = (
                "❌ <b>موجودی کیف پول کافی نیست</b>\n\n"
                f"💰 مبلغ مورد نیاز: <b>{format_price(total)} تومان</b>\n"
                f"💳 موجودی فعلی: <b>{format_price(wallet_balance)} تومان</b>\n"
                f"📉 کسری: <b>{format_price(shortage)} تومان</b>\n\n"
                "لطفاً ابتدا کیف پول خود را شارژ کنید."
            )
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="💰 شارژ حساب", callback_data="tu:menu")],
                [types.InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu:custom_cart")],
            ])
            await safe_edit_text(callback, text, reply_markup=kb)
            await callback.answer()
            return

    # Register each custom (as pending for paid, confirmed for free)
    registrations = []
    for item in selected:
        if not item.custom:
            continue
        # Free customs: confirm immediately
        # Paid customs: register as pending, confirm after payment
        reg_status = "confirmed" if item.custom.type.value == "free" else "pending"
        reg = await custom_service.register_user(
            user_id=user.id,
            custom_id=item.custom.id,
            codm_username=codm_username,
            status=reg_status,
        )
        registrations.append(reg)
    await uow.flush()

    await uow.commit()

    # If all free → done
    if not paid_items:
        # Clear the custom cart after successful free registration
        await custom_cart_service.clear_cart(user.id)
        await uow.flush()

        await uow.commit()
        await state.clear()
        text = "🎉 ثبت‌نام شما در کاستوم با موفقیت انجام شد!"
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("menu:customs")]])
        await safe_edit_text(callback, text, reply_markup=kb)
        await callback.answer()
        return

    # Paid → deduct from wallet
    from bot.services.wallet_payment import WalletPaymentService, WalletPaymentError
    from bot.models.user_dashboard import TransactionType
    import json
    import uuid
    
    wallet_service = WalletPaymentService(uow)
    
    # Create a payment record for tracking
    payment_service = PaymentService(uow)
    reg_ids = [reg.id for reg in registrations]
    notes = json.dumps({"registration_ids": reg_ids, "type": "custom_registration"})
    
    # Use a unique reference ID for idempotency
    temp_ref_id = f"custom_{registrations[0].id if registrations else str(uuid.uuid4())}"
    
    try:
        # Deduct from wallet with CUSTOM_REGISTRATION transaction type
        updated_user, wallet_txn = await wallet_service.deduct_wallet(
            user_id=user.id,
            amount=total,
            ref_id=temp_ref_id,
            notes=notes,
            transaction_type=TransactionType.CUSTOM_REGISTRATION,
        )
        await uow.flush()

        await uow.commit()
        
        # Create payment record
        payment = await payment_service.create_payment(
            user_id=user.id,
            amount=total,
            method=PaymentMethod.BALANCE,
            status=PaymentStatus.APPROVED,
            custom_registration_id=registrations[0].id if registrations else None,
            notes=notes,
            transaction_id=wallet_txn.id,
        )
        await uow.flush()

        await uow.commit()
        
        # Now confirm all paid registrations after successful payment
        for reg in registrations:
            if reg.status == "pending":
                await custom_service.approve_registration(reg.id, admin_id=user.id)
        await uow.flush()

        await uow.commit()
        
    except WalletPaymentError as e:
        # Payment failed - registrations stay pending, no confirmation
        logger.warning(f"Wallet payment failed for user {user.id}: {e}")
        await callback.answer(f"خطا در پرداخت: {e}", show_alert=True)
        return
    except Exception as e:
        logger.exception("Custom wallet payment failed: %s", e)
        # Payment failed - registrations stay pending
        await callback.answer("خطا در پردازش پرداخت", show_alert=True)
        return

    # Clear the custom cart after successful paid registration
    await custom_cart_service.clear_cart(user.id)
    await uow.flush()

    await uow.commit()
    await state.clear()

    # Show success message
    text = (
        "✅ <b>ثبت‌نام و پرداخت موفق!</b>\n\n"
        f"💰 مبلغ پرداخت‌شده: <b>{format_price(total)} تومان</b>\n"
        f"💳 موجودی جدید: <b>{format_price(updated_user.wallet_balance)} تومان</b>\n\n"
        "🎉 ثبت‌نام شما در کاستوم تایید شد!"
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [back_button("menu:customs")],
    ])
    await safe_edit_text(callback, text, reply_markup=kb)
    await callback.answer("ثبت‌نام موفق")