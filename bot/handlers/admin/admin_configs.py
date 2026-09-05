"""Admin config product management handlers."""

import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.admin import admin_configs_keyboard
from bot.keyboards.common import back_button, single_button_kb
from bot.models.log import LogAction
from bot.models.user import User
from bot.services.admin import AdminService
from bot.services.config_shop import ConfigShopService
from bot.services.category import CategoryService
from bot.states import ConfigProductStates
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="admin_configs")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "admin:configs")
async def cb_admin_configs(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, "⚡ <b>مدیریت کانفیگ‌ها</b>", reply_markup=admin_configs_keyboard())
    await callback.answer()


@router.callback_query(F.data == "aconf:add")
async def cb_config_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ConfigProductStates.waiting_title)
    await callback.message.answer("📝 عنوان کانفیگ را ارسال کنید:")
    await callback.answer()


@router.message(ConfigProductStates.waiting_title)
async def collect_config_title(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("⚠️ عنوان خالی است:")
        return
    await state.update_data(title=message.text.strip())
    await state.set_state(ConfigProductStates.waiting_description)
    await message.answer("📝 توضیحات کانفیگ را ارسال کنید (یا /skip):")


@router.message(ConfigProductStates.waiting_description)
async def collect_config_desc(message: Message, state: FSMContext) -> None:
    desc = message.text.strip() if message.text and not message.text.startswith("/skip") else ""
    await state.update_data(description=desc)
    await state.set_state(ConfigProductStates.waiting_price)
    await message.answer("💰 قیمت کانفیگ را به تومان ارسال کنید:")


@router.message(ConfigProductStates.waiting_price)
async def collect_config_price(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("⚠️ عدد معتبر وارد کنید:")
        return
    try:
        price = int(message.text.strip().replace(",", ""))
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ لطفاً عدد معتبر وارد کنید:")
        return
    await state.update_data(price=price)
    await state.set_state(ConfigProductStates.waiting_stock)
    await message.answer("📦 موجودی (عدد، 0 = نامحدود):")


@router.message(ConfigProductStates.waiting_stock)
async def collect_config_stock(message: Message, state: FSMContext, uow, user: User) -> None:
    if not message.text:
        await message.answer("⚠️ عدد معتبر وارد کنید:")
        return
    try:
        stock = int(message.text.strip())
        if stock < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ لطفاً عدد صحیح وارد کنید:")
        return
    await state.update_data(stock=stock, unlimited_stock=(stock == 0))
    await state.set_state(ConfigProductStates.waiting_category)
    from bot.keyboards.selectors import category_picker_keyboard
    cats = await CategoryService(uow).get_by_type("config", active_only=True)
    await message.answer(
        "📂 <b>انتخاب دسته کانفیگ</b>\n\nروی یکی از دسته‌های موجود بزنید:",
        reply_markup=category_picker_keyboard(
            cats,
            callback_prefix="pickcat_config",
            back_to="admin:configs",
        ),
    )


@router.callback_query(F.data.startswith("pickcat_config:"))
async def collect_config_category(callback: CallbackQuery, state: FSMContext, uow, user: User) -> None:
    parts = callback.data.split(":", 1)
    if len(parts) < 2:
        await callback.answer("دسته‌بندی یافت نشد", show_alert=True)
        return
    raw = parts[1]
    category_id = None if raw == "none" else raw
    data = await state.get_data()
    if not data.get("title"):
        # The FSM data is gone (bot restarted, or the admin re-tapped an old
        # keyboard). Creating the row anyway crashed with a NOT NULL error and
        # poisoned the whole transaction.
        await state.clear()
        await callback.answer(
            "⚠️ اطلاعات این مرحله از بین رفته است. لطفاً دوباره از ابتدا شروع کنید.",
            show_alert=True,
        )
        return
    cs = ConfigShopService(uow)
    product = await cs.create_product(
        title=data.get("title"),
        description=data.get("description") or "",
        price=data.get("price", 0),
        stock=data.get("stock", 0),
        unlimited_stock=data.get("unlimited_stock", False),
        category_id=category_id,
        is_visible=True,
    )
    await uow.flush()
    api = AdminService(uow)
    await api.log_action(user, LogAction.CONFIG_CREATE, target_id=product.id, description=f"ایجاد کانفیگ {product.title}")
    await uow.flush()
    await state.clear()
    text = (
        "✅ <b>کانفیگ ایجاد شد</b>\n\n"
        f"⚡ عنوان: {product.title}\n"
        f"💰 قیمت: {format_price(product.price)} تومان\n"
        f"📦 موجودی: {'نامحدود' if product.unlimited_stock else product.stock}"
    )
    await safe_edit_text(callback, text, reply_markup=single_button_kb(back_button("admin:configs")))
    await callback.answer("کانفیگ ایجاد شد")


@router.callback_query(F.data == "aconf:list")
async def cb_config_list(callback: CallbackQuery, uow, user: User) -> None:
    cs = ConfigShopService(uow)
    products = await cs.get_all_for_admin(limit=50)
    if not products:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:configs")]])
        await safe_edit_text(callback, "⚡ کانفیگی ثبت نشده است.", reply_markup=kb)
        await callback.answer()
        return
    keyboard = []
    for p in products:
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"{p.title} — {format_price(p.price)}",
                callback_data=f"aconf:detail:{p.id}",
            )
        ])
    keyboard.append([back_button("admin:configs")])
    await safe_edit_text(callback, "⚡ <b>لیست کانفیگ‌ها</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@router.callback_query(F.data.startswith("aconf:detail:"))
async def cb_config_detail(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کانفیگ یافت نشد", show_alert=True)
        return
    product_id = parts[2]
    cs = ConfigShopService(uow)
    product = await cs.get_product(product_id)
    if not product:
        await callback.answer("کانفیگ یافت نشد", show_alert=True)
        return
    stock = "نامحدود" if product.unlimited_stock else str(product.stock)
    text = (
        f"⚡ <b>{product.title}</b>\n\n"
        f"📝 توضیحات: {product.description or '—'}\n"
        f"💰 قیمت: {format_price(product.price)} تومان\n"
        f"📦 موجودی: {stock}\n"
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔴 حذف", callback_data=f"aconf:del:{product.id}")],
        [types.InlineKeyboardButton(text="👁 تغییر نمایش", callback_data=f"aconf:vis:{product.id}")],
        [back_button("admin:configs")],
    ])
    await safe_edit_text(callback, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("aconf:del:"))
async def cb_config_delete(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کانفیگ یافت نشد", show_alert=True)
        return
    product_id = parts[2]
    await ConfigShopService(uow).delete_product(product_id)
    await uow.flush()
    await callback.answer("حذف شد")
    await safe_edit_text(callback, "✅ کانفیگ حذف شد.", reply_markup=single_button_kb(back_button("admin:configs")))


@router.callback_query(F.data.startswith("aconf:vis:"))
async def cb_config_set_visible(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کانفیگ یافت نشد", show_alert=True)
        return
    product_id = parts[2]
    await ConfigShopService(uow).toggle_visibility(product_id)
    await uow.flush()
    await callback.answer("تغییر کرد")

# The next step of this flow is driven by inline buttons. Without this handler a
# typed answer was silently ignored and the flow looked frozen.
@router.message(ConfigProductStates.waiting_category)
async def _hint_configproductstates_waiting_category(message: Message) -> None:
    await message.answer("برای انتخاب دسته‌بندی، روی یکی از دکمه‌های بالا بزنید 👆")
