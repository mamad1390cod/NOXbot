"""Config shop handlers (user side)."""

from aiogram import F, Router, types
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import back_button
from bot.keyboards.shop import config_menu_keyboard
from bot.services.cart import CartService
from bot.services.category import CategoryService
from bot.services.config_shop import ConfigShopService
from bot.models.user import User
from bot.texts import CART_ADDED
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="configs")

ITEMS_PER_PAGE = 8


@router.callback_query(F.data == "menu:configs")
async def cb_configs(callback: CallbackQuery, uow, user: User) -> None:
    """Show config categories."""
    category_service = CategoryService(uow)
    categories = await category_service.get_visible_categories("config")
    kb = config_menu_keyboard(categories)
    await safe_edit_text(callback, 
        "⚡ <b>فروشگاه کانفیگ</b>\n\nانتخاب دسته‌بندی:",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("config_cat:"))
async def cb_config_category(callback: CallbackQuery, uow, user: User) -> None:
    """Show config products in a category."""
    parts = callback.data.split(":", 1)
    if len(parts) < 2:
        await callback.answer("دسته‌بندی یافت نشد", show_alert=True)
        return
    category_id = parts[1]
    config_service = ConfigShopService(uow)
    products = await config_service.get_by_category(category_id, limit=ITEMS_PER_PAGE)
    total = await config_service.count_by_category(category_id)

    keyboard = []
    for product in products:
        keyboard.append(
            [types.InlineKeyboardButton(
                text=product.title, callback_data=f"config_sel:{product.id}"
            )]
        )
    keyboard.append([back_button("menu:configs")])
    kb = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    await safe_edit_text(callback, "⚡ <b>لیست کانفیگ‌ها</b>", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("config_sel:"))
async def cb_config_detail(callback: CallbackQuery, uow, user: User) -> None:
    """Show config product details."""
    product_id = callback.data.split(":", 1)[1]
    config_service = ConfigShopService(uow)
    product = await config_service.get_product(product_id)
    if not product or not product.is_visible:
        await callback.answer("کانفیگ یافت نشد", show_alert=True)
        return

    await config_service.increment_view(product_id)

    price = format_price(product.price)
    stock_text = "نامحدود" if product.unlimited_stock else str(product.stock)
    text = (
        f"⚡ <b>{product.title}</b>\n\n"
        f"{product.description or ''}\n\n"
        f"💰 قیمت: <b>{price} تومان</b>\n"
        f"📦 موجودی: {stock_text}\n"
    )
    keyboard = [
        [types.InlineKeyboardButton(text="➕ افزودن به سبد", callback_data=f"config_add:{product.id}")],
        [back_button("menu:configs")],
    ]
    kb = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    if product.image_url:
        await callback.message.edit_media(
            types.InputMediaPhoto(media=product.image_url, caption=text),
            reply_markup=kb,
        )
    else:
        await safe_edit_text(callback, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("config_add:"))
async def cb_config_add(callback: CallbackQuery, uow, user: User) -> None:
    """Add config product to cart."""
    product_id = callback.data.split(":", 1)[1]
    config_service = ConfigShopService(uow)
    product = await config_service.get_product(product_id)
    if not product or not product.is_visible or not product.is_in_stock:
        await callback.answer("کانفیگ در دسترس نیست", show_alert=True)
        return

    cart_service = CartService(uow)
    try:
        await cart_service.add_config(user.id, product_id, quantity=1)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return

    await callback.answer(CART_ADDED())

    summary = await cart_service.get_cart_summary(user.id)
    from bot.keyboards.cart_keyboard import cart_keyboard
    text = (
        f"🛒 <b>سبد خرید</b>\n\n"
        f"تعداد آیتم: {summary['total_items']}\n"
        f"💰 مبلغ کل: <b>{format_price(summary['total_price'])} تومان</b>"
    )
    await safe_edit_text(callback, text, reply_markup=cart_keyboard(summary["items"]))
    await callback.answer()