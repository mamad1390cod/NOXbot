"""Shopping cart handlers."""

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.keyboards.cart_keyboard import cart_keyboard, checkout_keyboard, confirm_cancel_keyboard
from bot.services.cart import CartService
from bot.services.order import OrderService
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="cart")


async def _show_cart(callback: CallbackQuery, uow, user) -> None:
    """Edit message to show the cart."""
    cart_service = CartService(uow)
    summary = await cart_service.get_cart_summary(user.id)

    if not summary["items"]:
        from bot.texts import CART_EMPTY
        from bot.keyboards.common import back_button
        kb = __import__("aiogram.types", fromlist=["InlineKeyboardMarkup"]).InlineKeyboardMarkup(
            inline_keyboard=[[back_button("menu:home")]]
        )
        await safe_edit_text(callback, CART_EMPTY(), reply_markup=kb)
        await callback.answer()
        return

    lines = []
    for i, item in enumerate(summary["items"], 1):
        title = item.title
        price = format_price(item.price)
        qty = item.quantity
        item_total = format_price(item.price * item.quantity)
        lines.append(f"{i}. {title} × {qty} = <b>{item_total}</b> تومان")

    text = (
        "🛒 <b>سبد خرید شما</b>\n\n"
        + "\n".join(lines)
        + f"\n\n💰 مبلغ کل: <b>{format_price(summary['total_price'])} تومان</b>"
        + f"\n📦 تعداد آیتم: {summary['total_items']}"
    )
    await safe_edit_text(callback, text, reply_markup=cart_keyboard(summary["items"]))
    await callback.answer()


@router.callback_query(F.data == "menu:cart")
async def cb_cart(
    callback: CallbackQuery,
    uow, user,
) -> None:
    """Show the shopping cart."""
    await _show_cart(callback, uow, user)


@router.callback_query(F.data.startswith("cart:view:"))
async def cb_cart_item_view(
    callback: CallbackQuery,
    uow, user,
) -> None:
    """View a single cart item."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("داده‌های نامعتبر", show_alert=True)
        return
    item_id = parts[2]
    cart_service = CartService(uow)
    cart = await cart_service.get_cart(user.id)
    if not cart:
        await callback.answer("سبد خرید خالی است", show_alert=True)
        return
    item = await uow.carts.get_item(item_id)
    if not item or item.cart_id != cart.id:
        await callback.answer("آیتم یافت نشد", show_alert=True)
        return

    from bot.keyboards.cart_keyboard import cart_item_keyboard
    text = (
        f"📦 <b>{item.title}</b>\n\n"
        f"قیمت واحد: <b>{format_price(item.price)} تومان</b>\n"
        f"تعداد: {item.quantity}\n"
        f"جمع: <b>{format_price(item.price * item.quantity)} تومان</b>"
    )
    await safe_edit_text(callback, text, reply_markup=cart_item_keyboard(item))
    await callback.answer()


@router.callback_query(F.data.startswith("cart:inc:"))
async def cb_cart_increment(
    callback: CallbackQuery,
    uow, user,
) -> None:
    """Increment cart item quantity."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("داده‌های نامعتبر", show_alert=True)
        return
    item_id = parts[2]
    cart_service = CartService(uow)
    cart = await cart_service.get_cart(user.id)
    item = await cart_service.uow.carts.get_item(item_id)
    if not item or (cart and item.cart_id != cart.id):
        await callback.answer("آیتم یافت نشد", show_alert=True)
        return
    try:
        await cart_service.update_quantity(user.id, item_id, item.quantity + 1)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    from bot.keyboards.cart_keyboard import cart_item_keyboard
    item = await cart_service.uow.carts.get_item(item_id)
    text = (
        f"📦 <b>{item.title}</b>\n\n"
        f"قیمت واحد: <b>{format_price(item.price)} تومان</b>\n"
        f"تعداد: {item.quantity}\n"
        f"جمع: <b>{format_price(item.price * item.quantity)} تومان</b>"
    )
    await safe_edit_text(callback, text, reply_markup=cart_item_keyboard(item))
    await callback.answer()


@router.callback_query(F.data.startswith("cart:dec:"))
async def cb_cart_decrement(
    callback: CallbackQuery,
    uow, user,
) -> None:
    """Decrement cart item quantity."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("داده‌های نامعتبر", show_alert=True)
        return
    item_id = parts[2]
    cart_service = CartService(uow)
    cart = await cart_service.get_cart(user.id)
    item = await cart_service.uow.carts.get_item(item_id)
    if not item or (cart and item.cart_id != cart.id):
        await callback.answer("آیتم یافت نشد", show_alert=True)
        return
    try:
        item = await cart_service.update_quantity(user.id, item_id, item.quantity - 1)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    if item is None:
        await _show_cart(callback, uow, user)
        return
    from bot.keyboards.cart_keyboard import cart_item_keyboard
    text = (
        f"📦 <b>{item.title}</b>\n\n"
        f"قیمت واحد: <b>{format_price(item.price)} تومان</b>\n"
        f"تعداد: {item.quantity}\n"
        f"جمع: <b>{format_price(item.price * item.quantity)} تومان</b>"
    )
    await safe_edit_text(callback, text, reply_markup=cart_item_keyboard(item))
    await callback.answer()


@router.callback_query(F.data.startswith("cart:del:"))
async def cb_cart_delete_item(
    callback: CallbackQuery,
    uow, user,
) -> None:
    """Delete a cart item."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("داده‌های نامعتبر", show_alert=True)
        return
    item_id = parts[2]
    cart_service = CartService(uow)
    try:
        await cart_service.remove_item(user.id, item_id)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await callback.answer("آیتم حذف شد")
    await _show_cart(callback, uow, user)


@router.callback_query(F.data == "cart:clear")
async def cb_cart_clear(
    callback: CallbackQuery,
    uow, user,
) -> None:
    """Clear the cart."""
    cart_service = CartService(uow)
    await cart_service.clear_cart(user.id)
    await callback.answer("سبد خرید خالی شد")
    await _show_cart(callback, uow, user)


@router.callback_query(F.data == "cart:checkout")
async def cb_cart_checkout(
    callback: CallbackQuery,
    uow, user,
) -> None:
    """Start checkout with wallet balance check."""
    cart_service = CartService(uow)
    summary = await cart_service.get_cart_summary(user.id)
    if not summary["items"]:
        await callback.answer("سبد خرید خالی است", show_alert=True)
        return

    total_price = summary['total_price']
    wallet_balance = user.wallet_balance or 0
    has_sufficient_balance = wallet_balance >= total_price

    if has_sufficient_balance:
        # Show wallet payment option
        text = (
            "🧾 <b>تایید نهایی سفارش</b>\n\n"
            f"📦 تعداد آیتم: {summary['total_items']}\n"
            f"💰 مبلغ پرداختی: <b>{format_price(total_price)} تومان</b>\n\n"
            f"💳 موجودی کیف پول: <b>{format_price(wallet_balance)} تومان</b>\n"
            f"✅ موجودی کافی است!\n\n"
            "پرداخت مستقیم از کیف پول انجام خواهد شد."
        )
        from bot.keyboards.cart_keyboard import wallet_checkout_keyboard
        await safe_edit_text(callback, text, reply_markup=wallet_checkout_keyboard())
    else:
        # Insufficient balance - show topup option
        shortage = total_price - wallet_balance
        text = (
            "❌ <b>موجودی کیف پول کافی نیست</b>\n\n"
            f"💰 مبلغ سفارش: <b>{format_price(total_price)} تومان</b>\n"
            f"💳 موجودی فعلی: <b>{format_price(wallet_balance)} تومان</b>\n"
            f"📉 کسری: <b>{format_price(shortage)} تومان</b>\n\n"
            "لطفاً ابتدا کیف پول خود را شارژ کنید."
        )
        from bot.keyboards.cart_keyboard import insufficient_balance_keyboard
        await safe_edit_text(callback, text, reply_markup=insufficient_balance_keyboard())
    
    await callback.answer()