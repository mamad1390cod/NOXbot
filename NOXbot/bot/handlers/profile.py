"""User profile handlers."""

from aiogram import F, Router, types
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import back_button, single_button_kb
from bot.models.user import User
from bot.services.custom import CustomService
from bot.services.order import OrderService
from bot.services.ticket import TicketService
from bot.utils.format import format_price

router = Router(name="profile")


@router.message(F.text == "/profile" or F.text == "/panel")
async def cmd_profile(message: Message, uow, user: User) -> None:
    """Show user profile."""
    text = (
        f"👤 <b>پروفایل شما</b>\n\n"
        f"🆔 آیدی: <code>{user.telegram_id}</code>\n"
        f"👤 نام: {user.first_name or ''} {user.last_name or ''}\n"
        f"💰 کل خریدها: <b>{format_price(user.total_spent)} تومان</b>\n"
    )
    await message.answer(text, reply_markup=single_button_kb(back_button("menu:home")))