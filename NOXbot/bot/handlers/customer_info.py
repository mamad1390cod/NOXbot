"""Customer info collection handlers."""

import logging
import re
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import back_button, single_button_kb
from bot.models.user import User
from bot.services.cart import CartService
from bot.services.user import UserService
from bot.states import CustomerInfoStates
from bot.utils.editing import safe_edit_text

router = Router(name="customer_info")
logger = logging.getLogger(__name__)


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


@router.message(CustomerInfoStates.waiting_email)
async def collect_customer_email(message: Message, state: FSMContext) -> None:
    """Collect customer email."""
    email = message.text.strip() if message.text else ""
    
    if not validate_email(email):
        await message.answer(
            "⚠️ ایمیل نامعتبر است.\n"
            "لطفاً یک ایمیل معتبر وارد کنید:\n"
            "مثال: user@example.com"
        )
        return
    
    await state.update_data(email=email)
    await state.set_state(CustomerInfoStates.waiting_password)
    await message.answer(
        "🔐 <b>رمز عبور</b>\n\n"
        "رمز عبور خود را وارد کنید (حداقل 6 کاراکتر):"
    )


@router.message(CustomerInfoStates.waiting_password)
async def collect_customer_password(message: Message, state: FSMContext) -> None:
    """Collect customer password."""
    password = message.text.strip() if message.text else ""
    
    if len(password) < 6:
        await message.answer(
            "⚠️ رمز عبور باید حداقل 6 کاراکتر باشد.\n"
            "دوباره وارد کنید:"
        )
        return
    
    await state.update_data(password=password)
    await state.set_state(CustomerInfoStates.waiting_customer_name)
    await message.answer(
        "👤 <b>نام و نام خانوادگی</b>\n\n"
        "نام کامل خود را وارد کنید:"
    )


@router.message(CustomerInfoStates.waiting_customer_name)
async def collect_customer_name(message: Message, state: FSMContext, uow, user: User) -> None:
    """Collect customer name and save all info, then continue with cart."""
    customer_name = message.text.strip() if message.text else ""
    
    if not customer_name or len(customer_name) < 2:
        await message.answer(
            "⚠️ نام نامعتبر است.\n"
            "لطفاً نام کامل خود را وارد کنید:"
        )
        return
    
    data = await state.get_data()
    email = data.get("email")
    password = data.get("password")
    product_id = data.get("product_id")
    quantity = data.get("quantity", 1)
    
    # Save customer info
    user_service = UserService(uow)
    try:
        await user_service.update_user(
            user.id,
            email=email,
            password=password,
            customer_name=customer_name,
        )
        await uow.commit()
        
        # Now add to cart
        cart_service = CartService(uow)
        await cart_service.add_product(user.id, product_id, quantity=quantity)
        await uow.commit()
        
        await state.clear()
        
        # Show cart
        summary = await cart_service.get_cart_summary(user.id)
        text = (
            f"✅ <b>اطلاعات ذخیره و محصول به سبد خرید اضافه شد</b>\n\n"
            f"👤 نام: {customer_name}\n"
            f"📧 ایمیل: {email}\n\n"
            f"🛒 <b>سبد خرید شما</b>\n\n"
        )
        
        for item in summary["items"]:
            text += f"• {item['product'].title} × {item['quantity']}\n"
        
        text += f"\n💰 مجموع: {summary['total_price']} تومان"
        
        await message.answer(
            text,
            reply_markup=single_button_kb(back_button("cart:view"))
        )
    except Exception as e:
        logger.exception(f"Failed to save customer info: {e}")
        await state.clear()
        await message.answer(
            f"❌ خطا در ذخیره اطلاعات: {e}",
            reply_markup=single_button_kb(back_button("menu:home"))
        )
