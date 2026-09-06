"""Product browsing handlers (user side)."""

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.cart_keyboard import confirm_cancel_keyboard
from bot.keyboards.common import back_button
from bot.keyboards.shop import products_list_keyboard, products_menu_keyboard
from bot.services.cart import CartService
from bot.services.category import CategoryService
from bot.services.product import ProductService
from bot.states import ProductStates
from bot.texts import CART_ADDED
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text
from bot.models.user import User

router = Router(name="products")

ITEMS_PER_PAGE = 8


@router.callback_query(F.data == "menu:products")
async def cb_products(
    callback: CallbackQuery,
    uow, user: User,
) -> None:
    """Show product categories."""
    category_service = CategoryService(uow)
    categories = await category_service.get_visible_categories("product")
    kb = products_menu_keyboard(categories)
    await safe_edit_text(callback, 
        "🛠 <b>انتخاب دسته‌بندی محصول</b>",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("prod_cat:"))
async def cb_product_category(
    callback: CallbackQuery,
    uow, user: User,
) -> None:
    """Show products in a category."""
    category_id = callback.data.split(":", 1)[1]
    product_service = ProductService(uow)
    products = await product_service.get_by_category(category_id, limit=ITEMS_PER_PAGE)
    total = await product_service.count_by_category(category_id)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    kb = products_list_keyboard(products, page=0, total_pages=total_pages)
    await safe_edit_text(callback, 
        "🛍 <b>لیست محصولات</b>",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("prod_sel:"))
async def cb_product_detail(
    callback: CallbackQuery,
    uow, user: User,
) -> None:
    """Show product details."""
    product_id = callback.data.split(":", 1)[1]
    product_service = ProductService(uow)
    product = await product_service.get_product(product_id)
    if not product or not product.is_visible:
        await callback.answer("محصول یافت نشد", show_alert=True)
        return

    await product_service.increment_view(product_id)

    price = format_price(product.discounted_price)
    stock_text = "نامحدود" if product.unlimited_stock else str(product.stock)
    text = (
        f"📦 <b>{product.title}</b>\n\n"
        f"{product.description or ''}\n\n"
        f"💰 قیمت: <b>{price} تومان</b>\n"
        f"📦 موجودی: {stock_text}\n"
    )

    keyboard = [
        [types.InlineKeyboardButton(text="➕ افزودن به سبد", callback_data=f"prod_add:{product.id}")],
        [back_button("menu:products")],
    ]
    kb = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    if product.image_url:
        await callback.message.edit_media(
            types.InputMediaPhoto(
                media=product.image_url,
                caption=text,
            ),
            reply_markup=kb,
        )
    else:
        await safe_edit_text(callback, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("prod_add:"))
async def cb_product_add(
    callback: CallbackQuery,
    uow, user: User,
    state: FSMContext,
) -> None:
    """Add product to cart (with account info if required)."""
    product_id = callback.data.split(":", 1)[1]
    product_service = ProductService(uow)
    product = await product_service.get_product(product_id)
    if not product or not product.is_visible:
        await callback.answer("محصول یافت نشد", show_alert=True)
        return

    if not product.is_in_stock:
        await callback.answer("موجودی محصول تمام شده", show_alert=True)
        return

    # If the product requires account info, collect it via FSM
    if product.requires_account_info:
        from bot.states import AccountInfoStates
        await state.set_data({"pending_product_id": product_id, "product_id": product_id})
        await state.set_state(AccountInfoStates.waiting_codm_username)
        await callback.message.answer(
            f"برای ثبت محصول <b>{product.title}</b> لطفاً اطلاعات زیر را وارد کنید.\n\n"
            "👤 نام کاربری CODM خود را ارسال کنید:"
        )
        await callback.answer()
        return

    # Check if customer info is collected
    if not user.email or not user.password or not user.customer_name:
        # Start customer info collection flow
        from bot.states import CustomerInfoStates
        await state.update_data(product_id=product_id, quantity=1)
        await state.set_state(CustomerInfoStates.waiting_email)
        await callback.message.answer(
            "📋 <b>اطلاعات مشتری</b>\n\n"
            "برای اولین خرید، لطفاً اطلاعات زیر را وارد کنید.\n\n"
            "📧 <b>ایمیل</b>\n"
            "ایمیل خود را وارد کنید:\n"
            "مثال: user@example.com"
        )
        await callback.answer()
        return
    
    # Simple product: add directly
    cart_service = CartService(uow)
    try:
        await cart_service.add_product(user.id, product_id, quantity=1)
        await callback.answer(CART_ADDED(), show_alert=False)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return

    # Show cart status
    summary = await cart_service.get_cart_summary(user.id)
    text = (
        f"🛒 <b>سبد خرید شما</b>\n\n"
        f"تعداد آیتم: {summary['total_items']}\n"
        f"مبلغ کل: <b>{format_price(summary['total_price'])} تومان</b>"
    )
    from bot.keyboards.cart_keyboard import cart_keyboard
    await safe_edit_text(callback, text, reply_markup=cart_keyboard(summary["items"]))
    await callback.answer()