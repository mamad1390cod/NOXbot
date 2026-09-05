"""Account info collection handlers (for account-type products).

Flow: CODM Username → Email → Password → Confirmation → Add to cart.
"""

import json

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.cart_keyboard import cart_keyboard, confirm_cancel_keyboard
from bot.services.cart import CartService
from bot.states import AccountInfoStates
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="account")


async def _get_pending(state: FSMContext) -> dict:
    data = await state.get_data()
    return data


@router.message(AccountInfoStates.waiting_codm_username)
async def collect_codm_username(
    message: Message,
    state: FSMContext,
    uow, user,
) -> None:
    """Collect CODM username."""
    codm_username = message.text.strip()
    if not codm_username:
        await message.answer("⚠️ لطفاً یک نام کاربری معتبر وارد کنید:")
        return
    if len(codm_username) > 100:
        await message.answer("⚠️ نام کاربری خیلی طولانی است. حداکثر 100 کاراکتر:")
        return

    await state.update_data(codm_username=codm_username)
    await state.set_state(AccountInfoStates.waiting_email)
    await message.answer("📧 ایمیل خود را وارد کنید:")


@router.message(AccountInfoStates.waiting_email)
async def collect_email(
    message: Message,
    state: FSMContext,
    uow, user,
) -> None:
    """Collect email address."""
    email = message.text.strip()
    if not email or "@" not in email:
        await message.answer("⚠️ ایمیل معتبر نیست. مثال: example@mail.com")
        return

    await state.update_data(email=email)
    await state.set_state(AccountInfoStates.waiting_password)
    await message.answer("🔑 رمز عبور را وارد کنید:")


@router.message(AccountInfoStates.waiting_password)
async def collect_password(
    message: Message,
    state: FSMContext,
    uow, user,
) -> None:
    """Collect password."""
    password = message.text.strip()
    if not password:
        await message.answer("⚠️ رمز عبور را وارد کنید:")
        return

    await state.update_data(password=password)
    await state.set_state(AccountInfoStates.waiting_confirmation)
    data = await state.get_data()

    text = (
        "📋 <b>تایید اطلاعات</b>\n\n"
        f"👤 CODM: <code>{data['codm_username']}</code>\n"
        f"📧 ایمیل: <code>{data['email']}</code>\n"
        f"🔑 رمز: <code>{data['password']}</code>\n\n"
        "آیا اطلاعات صحیح است؟"
    )
    kb = confirm_cancel_keyboard(
        "account:confirm",
        "action:cancel",
    )
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "account:confirm")
async def confirm_account(
    callback: CallbackQuery,
    state: FSMContext,
    uow, user,
) -> None:
    """Confirm account info and add to cart."""
    data = await state.get_data()
    product_id = data.get("product_id") or data.get("pending_product_id")
    if not product_id:
        await state.clear()
        await callback.answer("خطا در ثبت اطلاعات", show_alert=True)
        return

    account_data = json.dumps({
        "codm_username": data.get("codm_username"),
        "email": data.get("email"),
        "password": data.get("password"),
    }, ensure_ascii=False)

    cart_service = CartService(uow)
    try:
        await cart_service.add_product(
            user.id,
            product_id,
            quantity=1,
            account_data=account_data,
        )
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        await state.clear()
        return

    await state.clear()
    summary = await cart_service.get_cart_summary(user.id)
    text = (
        "✅ محصول به سبد خرید اضافه شد!\n\n"
        f"🛒 تعداد آیتم: {summary['total_items']}\n"
        f"💰 مبلغ کل: <b>{format_price(summary['total_price'])} تومان</b>"
    )
    await safe_edit_text(callback, 
        text,
        reply_markup=cart_keyboard(summary["items"]),
    )
    await callback.answer("محصول اضافه شد")


# NOTE: the global "action:cancel" handler lives in bot/handlers/menu.py so a
# cancelled flow always lands back on the main menu.

# The next step of this flow is driven by inline buttons. Without this handler a
# typed answer was silently ignored and the flow looked frozen.
@router.message(AccountInfoStates.waiting_confirmation)
async def _hint_accountinfostates_waiting_confirmation(message: Message) -> None:
    await message.answer("برای ادامه، دکمه «✅ تایید» یا «❌ انصراف» را بزنید 👆")
