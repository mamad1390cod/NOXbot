"""Custom tournament browsing handlers (user side)."""

from aiogram import F, Router, types
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import back_button
from bot.keyboards.custom_keyboard import custom_detail_keyboard, custom_panel_keyboard
from bot.services.custom import CustomService
from bot.services.custom_cart import CustomCartService
from bot.models.user import User
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="customs")


@router.callback_query(F.data == "menu:customs")
async def cb_customs(callback: CallbackQuery, uow, user: User) -> None:
    """Show custom tournament categories."""
    custom_service = CustomService(uow)
    categories = await custom_service.get_active_categories()
    keyboard = []
    for cat in categories:
        keyboard.append(
            [types.InlineKeyboardButton(text=cat.name, callback_data=f"custom_cat:{cat.id}")]
        )
    keyboard.append([back_button("menu:home")])
    kb = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await safe_edit_text(callback, 
        "🎮 <b>کاستوم‌ها</b>\n\nانتخاب دسته‌بندی:",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("custom_cat:"))
async def cb_custom_category(callback: CallbackQuery, uow, user: User) -> None:
    """Show customs in a category."""
    category_id = callback.data.split(":", 1)[1]
    custom_service = CustomService(uow)
    customs = await custom_service.get_by_category(category_id)
    kb = custom_panel_keyboard(customs)
    await safe_edit_text(callback, "🎮 <b>لیست کاستوم‌ها</b>", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("custom_sel:"))
async def cb_custom_detail(callback: CallbackQuery, uow, user: User) -> None:
    """Show custom tournament details."""
    custom_id = callback.data.split(":", 1)[1]
    custom_service = CustomService(uow)
    custom = await custom_service.get_custom(custom_id)
    if not custom or not custom.is_visible:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return

    await custom_service.uow.customs.increment_view_count(custom_id)

    # Build detail text
    fee = "رایگان" if custom.type.value == "free" else f"{format_price(custom.entry_fee)} تومان"
    capacity = f"{custom.current_players}/{custom.max_capacity}" if custom.max_capacity else str(custom.current_players)
    reg_status = "🟢 باز" if custom.can_register else "🔴 بسته"

    text = (
        f"🎮 <b>{custom.title}</b>\n\n"
        f"📝 توضیحات:\n{custom.description or '—'}\n\n"
        f"📜 قوانین:\n{custom.rules or '—'}\n\n"
        f"📅 تاریخ: {custom.event_date.strftime('%Y-%m-%d') if custom.event_date else '—'} "
        f"{custom.event_time or ''}\n"
        f"🏆 جایزه: {custom.prize or '—'}\n"
        f"💰 هزینه ورود: {fee}\n"
        f"👥 بازیکنان: {capacity}\n"
        f"📊 وضعیت ثبت‌نام: {reg_status}\n"
    )

    is_registered = await custom_service.is_user_registered(user.id, custom_id)
    kb = custom_detail_keyboard(custom_id, is_registered=is_registered)

    if custom.banner_url:
        await callback.message.edit_media(
            types.InputMediaPhoto(media=custom.banner_url, caption=text),
            reply_markup=kb,
        )
    else:
        await safe_edit_text(callback, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("custom_add:"))
async def cb_custom_add(callback: CallbackQuery, uow, user: User) -> None:
    """Add custom to custom cart."""
    custom_id = callback.data.split(":", 1)[1]
    custom_service = CustomService(uow)
    custom = await custom_service.get_custom(custom_id)
    if not custom or not custom.can_register:
        await callback.answer("ثبت‌نام این کاستوم فعال نیست یا ظرفیت پر شده", show_alert=True)
        return

    custom_cart_service = CustomCartService(uow)
    try:
        await custom_cart_service.add_custom(user.id, custom_id)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return

    await callback.answer("به سبد کاستوم اضافه شد")

    summary = await custom_cart_service.get_cart_summary(user.id)
    from bot.keyboards.custom_keyboard import custom_cart_keyboard
    text = (
        "🎯 <b>سبد کاستوم شما</b>\n\n"
        f"تعداد کاستوم‌ها: {summary['total_items']}\n"
        f"💰 مبلغ کل: <b>{format_price(summary['total_price'])} تومان</b>"
    )
    await safe_edit_text(callback, text, reply_markup=custom_cart_keyboard(summary["items"]))
    await callback.answer()