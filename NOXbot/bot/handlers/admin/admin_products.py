"""Admin product management handlers."""

import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.admin import (
    admin_products_keyboard,
    product_edit_fields_keyboard,
    product_management_keyboard,
)
from bot.keyboards.common import back_button, single_button_kb
from bot.models.log import LogAction
from bot.models.product import Product
from bot.models.user import User
from bot.services.admin import AdminService
from bot.services.category import CategoryService
from bot.services.product import ProductService
from bot.states import ProductStates
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="admin_products")
logger = logging.getLogger(__name__)

ITEMS_PER_PAGE = 10


def _product_text(product: Product) -> str:
    stock = "نامحدود" if product.unlimited_stock else str(product.stock)
    vis = "✅" if product.is_visible else "❌"
    act = "🟢" if product.status.value == "active" else "🔴"
    cat = product.category.name if product.category else "بدون دسته"
    return (
        f"📦 <b>{product.title}</b>\n\n"
        f"📝 توضیحات: {product.description or '—'}\n"
        f"💰 قیمت: {format_price(product.price)} تومان\n"
        f"📦 موجودی: {stock}\n"
        f"📂 دسته: {cat}\n"
        f"👁 نمایش: {vis}\n"
        f"📊 وضعیت: {act}\n"
        f"🛒 فروش: {product.purchase_count}\n"
    )


@router.callback_query(F.data == "admin:products")
async def cb_admin_products(callback: CallbackQuery) -> None:
    """Show product management menu."""
    await safe_edit_text(callback, 
        "📦 <b>مدیریت محصولات</b>\n\nانتخاب گزینه:",
        reply_markup=admin_products_keyboard(),
    )
    await callback.answer()


# --- Create product flow ---
@router.callback_query(F.data == "aprod:add")
async def cb_product_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProductStates.waiting_title)
    await callback.message.answer("📝 <b>افزودن محصول جدید</b>\n\nعنوان محصول را ارسال کنید:")
    await callback.answer()


@router.message(ProductStates.waiting_title)
async def collect_product_title(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip():
        await message.answer("⚠️ عنوان خالی است. دوباره ارسال کنید:")
        return
    await state.update_data(title=message.text.strip())
    await state.set_state(ProductStates.waiting_description)
    await message.answer("📝 توضیحات محصول را ارسال کنید (یا /skip برای رد کردن):")


@router.message(ProductStates.waiting_description)
async def collect_product_desc(message: Message, state: FSMContext) -> None:
    desc = message.text.strip() if message.text and not message.text.startswith("/skip") else ""
    await state.update_data(description=desc)
    await state.set_state(ProductStates.waiting_price)
    await message.answer("💰 قیمت محصول را به تومان ارسال کنید:")


@router.message(ProductStates.waiting_price)
async def collect_product_price(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("⚠️ عدد معتبر وارد کنید:")
        return
    try:
        price = int(message.text.strip().replace(",", ""))
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ لطفاً یک عدد معتبر وارد کنید:")
        return
    await state.update_data(price=price)
    await state.set_state(ProductStates.waiting_stock)
    await message.answer("📦 موجودی محصول را ارسال کنید (عدد) — برای موجودی نامحدود 0 بنویسید:")


@router.message(ProductStates.waiting_stock)
async def collect_product_stock(message: Message, state: FSMContext, uow, user: User) -> None:
    if not message.text:
        await message.answer("⚠️ عدد معتبر وارد کنید:")
        return
    try:
        stock = int(message.text.strip())
        if stock < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ لطفاً یک عدد صحیح وارد کنید:")
        return
    await state.update_data(stock=stock, unlimited_stock=(stock == 0))
    await state.set_state(ProductStates.waiting_category)
    # Show the category picker as inline buttons (not free text) so the item
    # is always linked to a real category.
    from bot.keyboards.selectors import category_picker_keyboard
    from bot.services.category import CategoryService
    cats = await CategoryService(uow).get_by_type("product", active_only=True)
    await message.answer(
        "📂 <b>انتخاب دسته‌بندی</b>\n\nروی یکی از دسته‌های موجود بزنید:",
        reply_markup=category_picker_keyboard(
            cats,
            callback_prefix="pickcat_prod",
            back_to="admin:products",
        ),
    )


@router.callback_query(F.data.startswith("pickcat_prod:"))
async def pick_product_category(
    callback: CallbackQuery,
    state: FSMContext,
    uow, user: User,
) -> None:
    """Called when admin taps a category button during product creation."""
    parts = callback.data.split(":", 1)
    if len(parts) < 2:
        await callback.answer("دسته‌بندی یافت نشد", show_alert=True)
        return
    raw = parts[1]
    category_id = None if raw == "none" else raw

    data = await state.get_data()
    product_service = ProductService(uow)
    product = await product_service.create_product(
        title=data.get("title"),
        description=data.get("description") or "",
        price=data.get("price", 0),
        stock=data.get("stock", 0),
        unlimited_stock=data.get("unlimited_stock", False),
        category_id=category_id,
        is_visible=True,
    )
    await uow.flush()

    await uow.commit()

    api = AdminService(uow)
    await api.log_action(user, LogAction.PRODUCT_CREATE, target_id=product.id, description=f"ایجاد محصول {product.title}")
    await uow.flush()

    await uow.commit()

    await state.clear()
    text = (
        "✅ <b>محصول ایجاد شد</b>\n\n"
        f"📦 عنوان: {product.title}\n"
        f"💰 قیمت: {format_price(product.price)} تومان\n"
        f"📦 موجودی: {'نامحدود' if product.unlimited_stock else product.stock}"
    )
    await safe_edit_text(callback, text, reply_markup=product_management_keyboard(product))
    await callback.answer("محصول ایجاد شد")


# --- List products ---
@router.callback_query(F.data == "aprod:list")
async def cb_product_list(callback: CallbackQuery, uow, user: User) -> None:
    product_service = ProductService(uow)
    products = await product_service.get_all_for_admin(limit=ITEMS_PER_PAGE)

    if not products:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="➕ افزودن محصول", callback_data="aprod:add")],
            [back_button("admin:products")],
        ])
        await safe_edit_text(callback, "📦 هنوز محصولی ثبت نشده است.", reply_markup=keyboard)
        await callback.answer()
        return

    keyboard = []
    for p in products:
        status = "🟢" if p.status.value == "active" else "🔴"
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"{status} {p.title} — {format_price(p.price)}",
                callback_data=f"aprod:detail:{p.id}",
            )
        ])
    keyboard.append([back_button("admin:products")])
    await safe_edit_text(callback, 
        "📦 <b>لیست محصولات</b>",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
    )
    await callback.answer()


# --- Product detail ---
@router.callback_query(F.data.startswith("aprod:detail:"))
async def cb_product_detail(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("محصول یافت نشد", show_alert=True)
        return
    product_id = parts[2]
    ps = ProductService(uow)
    product = await ps.get_product_with_category(product_id)
    if not product:
        await callback.answer("محصول یافت نشد", show_alert=True)
        return
    await safe_edit_text(callback, _product_text(product), reply_markup=product_management_keyboard(product))
    await callback.answer()


# --- Edit fields ---
@router.callback_query(F.data.startswith("aprod:edit:"))
async def cb_product_edit(callback: CallbackQuery) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("محصول یافت نشد", show_alert=True)
        return
    product_id = parts[2]
    await safe_edit_text(callback, 
        "✏️ <b>انتخاب فیلد برای ویرایش</b>",
        reply_markup=product_edit_fields_keyboard(product_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pedit:title:"))
async def cb_edit_title_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = callback.data.split(":", 2)[2]
    await state.update_data(editing_product_id=product_id)
    await state.set_state(ProductStates.waiting_edit_title)
    await callback.message.answer("📝 عنوان جدید را ارسال کنید:")
    await callback.answer()


@router.message(ProductStates.waiting_edit_title)
async def do_edit_title(message: Message, state: FSMContext, uow, user: User) -> None:
    if not message.text:
        return
    import json
    data = await state.get_data()
    ps = ProductService(uow)
    product_id = data["editing_product_id"]
    product = await ps.get_product_with_category(product_id)
    old_title = product.title if product else None
    new_title = message.text.strip()
    await ps.update_product(product_id, title=new_title)
    await uow.flush()

    await uow.commit()
    # Audit: log before/after.
    api = AdminService(uow)
    await api.log_action(
        user, LogAction.PRODUCT_EDIT, target_type="product", target_id=product_id,
        description=f"تغییر عنوان محصول از «{old_title}» به «{new_title}»",
        old_data=json.dumps({"title": old_title}, ensure_ascii=False),
        new_data=json.dumps({"title": new_title}, ensure_ascii=False),
    )
    await uow.flush()

    await uow.commit()
    await state.clear()
    await message.answer("✅ عنوان به‌روزرسانی شد.")


@router.callback_query(F.data.startswith("pedit:desc:"))
async def cb_edit_desc_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = callback.data.split(":", 2)[2]
    await state.update_data(editing_product_id=product_id)
    await state.set_state(ProductStates.waiting_edit_description)
    await callback.message.answer("📝 توضیحات جدید را ارسال کنید:")
    await callback.answer()


@router.message(ProductStates.waiting_edit_description)
async def do_edit_desc(message: Message, state: FSMContext, uow, user: User) -> None:
    if not message.text:
        return
    data = await state.get_data()
    ps = ProductService(uow)
    await ps.update_product(data["editing_product_id"], description=message.text.strip())
    await uow.flush()

    await uow.commit()
    await state.clear()
    await message.answer("✅ توضیحات به‌روزرسانی شد.")


@router.callback_query(F.data.startswith("pedit:price:"))
async def cb_edit_price_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = callback.data.split(":", 2)[2]
    await state.update_data(editing_product_id=product_id)
    await state.set_state(ProductStates.waiting_edit_price)
    await callback.message.answer("💰 قیمت جدید را ارسال کنید:")
    await callback.answer()


@router.message(ProductStates.waiting_edit_price)
async def do_edit_price(message: Message, state: FSMContext, uow, user: User) -> None:
    if not message.text:
        return
    try:
        price = int(message.text.strip().replace(",", ""))
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ عدد معتبر وارد کنید:")
        return
    data = await state.get_data()
    ps = ProductService(uow)
    await ps.update_product(data["editing_product_id"], price=price)
    await uow.flush()

    await uow.commit()
    await state.clear()
    await message.answer("✅ قیمت به‌روزرسانی شد.")


@router.callback_query(F.data.startswith("pedit:stock:"))
async def cb_edit_stock_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = callback.data.split(":", 2)[2]
    await state.update_data(editing_product_id=product_id)
    await state.set_state(ProductStates.waiting_edit_stock)
    await callback.message.answer("🎦 موجودی جدید را ارسال کنید:")
    await callback.answer()


@router.message(ProductStates.waiting_edit_stock)
async def do_edit_stock(message: Message, state: FSMContext, uow, user: User) -> None:
    if not message.text:
        return
    try:
        stock = int(message.text.strip())
        if stock < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ عدد معتبر وارد کنید:")
        return
    data = await state.get_data()
    ps = ProductService(uow)
    await ps.update_product(data["editing_product_id"], stock=stock, unlimited_stock=(stock == 0))
    await uow.flush()

    await uow.commit()
    await state.clear()
    await message.answer("✅ موجودی به‌روزرسانی شد.")


@router.callback_query(F.data.startswith("pedit:unlim:"))
async def cb_toggle_unlimited(callback: CallbackQuery, uow, user: User) -> None:
    product_id = callback.data.split(":", 2)[2]
    ps = ProductService(uow)
    product = await ps.get_product_with_category(product_id)
    if product:
        await ps.update_product(product_id, unlimited_stock=not product.unlimited_stock)
        await uow.flush()

        await uow.commit()
        await safe_edit_text(callback, _product_text(product), reply_markup=product_management_keyboard(product))
    await callback.answer()


# --- Status / visibility / duplicate / move / delete ---
@router.callback_query(F.data.startswith("aprod:toggle:"))
async def cb_product_toggle_status(callback: CallbackQuery, uow, user: User) -> None:
    product_id = callback.data.split(":", 2)[2]
    ps = ProductService(uow)
    product = await ps.toggle_status(product_id)
    await uow.flush()

    await uow.commit()
    if product:
        await safe_edit_text(callback, _product_text(product), reply_markup=product_management_keyboard(product))
    await callback.answer()


@router.callback_query(F.data.startswith("aprod:vis:"))
async def cb_toggle_visibility(callback: CallbackQuery, uow, user: User) -> None:
    product_id = callback.data.split(":", 2)[2]
    ps = ProductService(uow)
    product = await ps.toggle_visibility(product_id)
    await uow.flush()

    await uow.commit()
    if product:
        await safe_edit_text(callback, _product_text(product), reply_markup=product_management_keyboard(product))
    await callback.answer()


@router.callback_query(F.data.startswith("aprod:dup:"))
async def cb_duplicate_product(callback: CallbackQuery, uow, user: User) -> None:
    product_id = callback.data.split(":", 2)[2]
    ps = ProductService(uow)
    new_product = await ps.duplicate_product(product_id)
    await uow.flush()

    await uow.commit()
    if new_product:
        await safe_edit_text(callback, "🔄 <b>محصول کپی شد</b>\n" + _product_text(new_product),
                                          reply_markup=product_management_keyboard(new_product))
    await callback.answer()


@router.callback_query(F.data.startswith("aprod:del:"))
async def cb_delete_product(callback: CallbackQuery) -> None:
    product_id = callback.data.split(":", 2)[2]
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⚠️ تایید حذف", callback_data=f"aprod:confirm_del:{product_id}"),
         types.InlineKeyboardButton(text="❌ انصراف", callback_data="admin:products")]
    ])
    await safe_edit_text(callback, f"⚠️ آیا از حذف محصول #{product_id[:8]} مطمئن هستید؟", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("aprod:confirm_del:"))
async def cb_confirm_delete(callback: CallbackQuery, uow, user: User) -> None:
    product_id = callback.data.split(":", 2)[2]
    ps = ProductService(uow)
    await ps.delete_product(product_id)
    await uow.flush()

    await uow.commit()
    await safe_edit_text(callback, "✅ محصول حذف شد.")
    await callback.answer()


@router.callback_query(F.data.startswith("aprod:move:"))
async def cb_move_product(callback: CallbackQuery, state: FSMContext, uow, user: User) -> None:
    product_id = callback.data.split(":", 2)[2]
    cats = await CategoryService(uow).get_visible_categories("product")
    # Store product_id in FSM state to avoid callback_data > 64 bytes
    await state.set_state(ProductStates.waiting_move_category)
    await state.update_data(move_product_id=product_id)
    keyboard = []
    for c in cats:
        keyboard.append([types.InlineKeyboardButton(text=c.name, callback_data=f"pmv:{c.id}")])
    keyboard.append([back_button("admin:products")])
    await safe_edit_text(callback, "↪️ انتخاب دسته جدید:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@router.callback_query(F.data.startswith("pmv:"))
async def do_move_product(callback: CallbackQuery, state: FSMContext, uow, user: User) -> None:
    category_id = callback.data.split(":", 1)[1]
    data = await state.get_data()
    product_id = data.get("move_product_id")
    if not product_id:
        await callback.answer("خطا: اطلاعات جلسه یافت نشد", show_alert=True)
        return
    ps = ProductService(uow)
    await ps.move_product(product_id, category_id)
    await uow.flush()

    await uow.commit()
    await state.clear()
    await safe_edit_text(callback, "✅ محصول منتقل شد.", reply_markup=single_button_kb(back_button("admin:products")))
    await callback.answer()