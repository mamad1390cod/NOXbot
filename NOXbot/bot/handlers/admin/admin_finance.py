"""Financial dashboard — analytics overview, filters, and report export."""

import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import back_button, single_button_kb
from bot.keyboards.finance import finance_filter_keyboard, finance_menu_keyboard
from bot.models.log import LogAction
from bot.models.user import User
from bot.services.admin import AdminService
from bot.services.financial import FinancialService
from bot.services import reporting
from bot.states import FinancialStates
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="admin_finance")
logger = logging.getLogger(__name__)

# Active filter store keyed by admin telegram_id.
_ACTIVE_FILTERS: dict[int, dict] = {}


def _empty() -> dict:
    return {}


def _filter_desc(f: dict) -> str:
    parts = []
    if f.get("date_from"):
        parts.append(f"📅 از {f['date_from']} تا {f.get('date_to', '...')}")
    if f.get("t_user"):
        parts.append(f"👤 کاربر: {f['t_user']}")
    if f.get("t_product"):
        parts.append(f"📦 محصول: {f['t_product']}")
    if f.get("t_admin"):
        parts.append(f"👨💼 ادمین: {f['t_admin']}")
    return "\n".join(parts) if parts else "فیلتر فعالی ندارد"


def _dashboard_text(data: dict, admin_tg_id: int) -> str:
    p = data["periods"]
    lines = [
        "💵 <b>گزارش مالی</b>\n",
        f"📅 درآمد امروز: <b>{format_price(p['today'])} تومان</b> ({p['today_orders']} سفارش)",
        f"📅 درآمد دیروز: {format_price(p['yesterday'])} تومان",
        f"🗓 درآمد هفته: {format_price(p['week'])} تومان",
        f"📆 درآمد ماه: {format_price(p['month'])} تومان",
        f"🌟 درآمد سال: {format_price(p['year'])} تومان",
        "",
        f"💰 درآمد کل: <b>{format_price(data['total_revenue'])} تومان</b>",
        f"🧾 سفارش پرداختی: {data['paid_orders']}",
        f"🎯 میانگین ارزش سفارش: {format_price(data['avg_order_value'])} تومان",
        f"💹 نرخ تبدیل: {round(data['conversion'] * 100, 1)}٪",
        f"⏳ پرداخت در انتظار: {data['pending_payments']}",
        "",
        "📊 <b>محصولات پرفروش:</b>",
    ]
    for item in data["by_product"][:5]:
        lines.append(f"• {item['label']} — {format_price(item['revenue'])} تومان ({item['units']} واحد)")
    lines.append("\n👤 <b>بهترین مشتریان:</b>")
    for c in data["top_customers"][:3]:
        lines.append(f"• @{c.get('username') or c.get('telegram_id')} — {format_price(c['spend'])} تومان")
    lines += ["", f"🎚 {_filter_desc(_ACTIVE_FILTERS.get(admin_tg_id, {}))}"]
    return "\n".join(lines)


@router.callback_query(F.data == "admin:finance")
async def cb_finance(callback: CallbackQuery, uow, user: User) -> None:
    await cb_finance_home(callback, uow, user)


@router.callback_query(F.data == "fin:home")
async def cb_finance_home(callback: CallbackQuery, uow, user: User) -> None:
    fin = FinancialService(uow)
    data = await fin.dashboard(_ACTIVE_FILTERS.get(user.telegram_id, {}))
    text = _dashboard_text(data, user.telegram_id)
    await safe_edit_text(callback, text, reply_markup=finance_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "fin:clear")
async def cb_finance_clear(callback: CallbackQuery, uow, user: User) -> None:
    _ACTIVE_FILTERS[user.telegram_id] = {}
    await callback.answer("فیلتر پاک شد")
    await cb_finance_home(callback, uow, user)


# --- Filters ------------------------------------------------------------ #
@router.callback_query(F.data == "fin:filter")
async def cb_filter_menu(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, "🔍 <b>فیلتر گزارش</b>", reply_markup=finance_filter_keyboard())
    await callback.answer()


@router.callback_query(F.data == "fin:f_date")
async def cb_f_date(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FinancialStates.waiting_date_from)
    await callback.message.answer("🗓 تاریخ شروع را ارسال کنید (YYYY-MM-DD):")
    await callback.answer()


@router.message(FinancialStates.waiting_date_from)
async def do_date_from(message: Message, state: FSMContext, uow, user: User) -> None:
    from datetime import datetime as _dt
    raw = message.text.strip()
    try:
        _dt.strptime(raw, "%Y-%m-%d")
    except ValueError:
        await message.answer("⚠️ فرمت اشتباه. مثال: 2026-08-01")
        return
    await state.update_data(date_from=raw)
    await state.set_state(FinancialStates.waiting_date_to)
    await message.answer("📅 تاریخ پایان را ارسال کنید (YYYY-MM-DD):")


@router.message(FinancialStates.waiting_date_to)
async def do_date_to(message: Message, state: FSMContext, uow, user: User) -> None:
    from datetime import datetime as _dt
    raw = message.text.strip()
    try:
        _dt.strptime(raw, "%Y-%m-%d")
    except ValueError:
        await message.answer("⚠️ فرمت اشتباه. مثال: 2026-08-31")
        return
    data = await state.get_data()
    f = _ACTIVE_FILTERS.setdefault(user.telegram_id, {})
    f["date_from"] = data["date_from"]
    f["date_to"] = raw
    await state.clear()
    await message.answer("✅ بازه تاریخ اعمال شد.", reply_markup=single_button_kb(back_button("fin:home")))


@router.callback_query(F.data == "fin:f_user")
async def cb_f_user(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FinancialStates.waiting_user)
    await callback.message.answer("👤 آیدی تلگرام یا یوزرنیم کاربر را ارسال کنید:")
    await callback.answer()


@router.message(FinancialStates.waiting_user)
async def do_user(message: Message, state: FSMContext, uow, user: User) -> None:
    from bot.services.user import UserService
    users = await UserService(uow).search_users(message.text.strip(), limit=1)
    if not users:
        await message.answer("❌ کاربری یافت نشد.")
        await state.clear()
        return
    f = _ACTIVE_FILTERS.setdefault(user.telegram_id, {})
    f["user_id"] = users[0].id
    f["t_user"] = users[0].username or str(users[0].telegram_id)
    await state.clear()
    await message.answer("✅ فیلتر کاربر اعمال شد.", reply_markup=single_button_kb(back_button("fin:home")))


@router.callback_query(F.data == "fin:f_product")
async def cb_f_product(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FinancialStates.waiting_product)
    await callback.message.answer("📦 نام محصول/کانفیگ را ارسال کنید:")
    await callback.answer()


@router.message(FinancialStates.waiting_product)
async def do_product(message: Message, state: FSMContext, uow, user: User) -> None:
    f = _ACTIVE_FILTERS.setdefault(user.telegram_id, {})
    f["t_product"] = message.text.strip()
    await state.clear()
    await message.answer("✅ فیلتر محصول اعمال شد.", reply_markup=single_button_kb(back_button("fin:home")))


@router.callback_query(F.data == "fin:f_category")
async def cb_f_category(callback: CallbackQuery, state: FSMContext) -> None:
    # category filter is applied at query time by product title containment; store a text.
    await state.set_state(FinancialStates.waiting_category)
    await callback.message.answer("🏷 نام دسته را ارسال کنید:")
    await callback.answer()


@router.message(FinancialStates.waiting_category)
async def do_category(message: Message, state: FSMContext, uow, user: User) -> None:
    f = _ACTIVE_FILTERS.setdefault(user.telegram_id, {})
    f["t_product"] = message.text.strip()  # reuse product filter by name
    await state.clear()
    await message.answer("✅ فیلتر دسته اعمال شد.", reply_markup=single_button_kb(back_button("fin:home")))


@router.callback_query(F.data == "fin:f_payment")
async def cb_f_payment(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FinancialStates.waiting_payment_status)
    await callback.message.answer("💳 وضعیت پرداخت را ارسال کنید (pending/approved/rejected):")
    await callback.answer()


@router.message(FinancialStates.waiting_payment_status)
async def do_payment(message: Message, state: FSMContext, uow, user: User) -> None:
    f = _ACTIVE_FILTERS.setdefault(user.telegram_id, {})
    f["payment_status"] = message.text.strip().lower()
    await state.clear()
    await message.answer("✅ اعمال شد.", reply_markup=single_button_kb(back_button("fin:home")))


@router.callback_query(F.data == "fin:f_admin")
async def cb_f_admin(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FinancialStates.waiting_admin)
    await callback.message.answer("👨💼 نام ادمین (یوزرنیم) را ارسال کنید:")
    await callback.answer()


@router.message(FinancialStates.waiting_admin)
async def do_admin(message: Message, state: FSMContext, uow, user: User) -> None:
    f = _ACTIVE_FILTERS.setdefault(user.telegram_id, {})
    f["t_admin"] = message.text.strip()
    await state.clear()
    await message.answer("✅ فیلتر ادمین اعمال شد.", reply_markup=single_button_kb(back_button("fin:home")))


# --- Export ---------------------------------------------------------------- #
async def _export(callback: CallbackQuery, uow, user: User, fmt: str) -> None:
    fin = FinancialService(uow)
    f = _ACTIVE_FILTERS.get(user.telegram_id, {})
    makers = {
        "csv": reporting.make_csv,
        "excel": reporting.make_excel,
        "pdf": reporting.make_pdf,
        "chart": reporting.make_chart,
    }
    if fmt == "all":
        for name, maker in makers.items():
            try:
                path = await maker(fin, f)
                await callback.message.answer_document(types.FSInputFile(path), caption=f"خروجی {name}")
            except Exception as e:
                logger.exception("export %s failed: %s", name, e)
        await callback.answer("خروجی کامل ارسال شد")
        return

    maker = makers.get(fmt)
    if not maker:
        await callback.answer("قالب ناشناخته", show_alert=True)
        return
    try:
        path = await maker(fin, f)
    except Exception as e:
        logger.exception("export failed: %s", e)
        await callback.answer("❌ خطا در ساخت خروجی", show_alert=True)
        return
    from bot.services.admin import AdminService
    api = AdminService(uow)
    await api.log_action(user, LogAction.EXPORT_REPORTS, target_type="finance",
                       description=f"خروجی {fmt} از گزارش مالی")
    await callback.message.answer_document(types.FSInputFile(path), caption=f"گزارش مالی ({fmt})")
    await callback.answer("خروجی ارسال شد")


@router.callback_query(F.data.startswith("fin:export:"))
async def cb_export(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("فرمت انتخابی نامعتبر", show_alert=True)
        return
    fmt = parts[2]
    await _export(callback, uow, user, fmt)