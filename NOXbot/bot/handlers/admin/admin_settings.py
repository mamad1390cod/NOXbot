"""Admin settings handlers — dynamic, registry-backed settings editor.

Includes backward-compatible legacy flows (aset:card/support/welcome/admins)
and a generic editor driven by the settings registry (aset:cat / aset:view /
aset:edit / aset:media / aset:toggle) with instant apply (cache is busted).
"""

import json
import logging

from aiogram import F, Router, types
from bot.utils.editing import safe_edit_text
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.admin import admin_settings_keyboard
from bot.keyboards.common import back_button, single_button_kb
from bot.keyboards.settings import (
    settings_categories_keyboard,
    settings_detail_keyboard,
    settings_specs_keyboard,
)
from bot.models.log import LogAction
from bot.models.user import User
from bot.services.admin import AdminService
from bot.services.settings import SettingsService, SETTING_CARD_NUMBER, SETTING_CARD_HOLDER, SETTING_BANK_NAME, SETTING_SUPPORT_TEXT, SETTING_WELCOME_MESSAGE, SETTING_ADMIN_IDS
from bot.services.settings_registry import spec_for, specs_in_category
from bot.states import SettingsStates

router = Router(name="admin_settings")
logger = logging.getLogger(__name__)


def _fmt_value(spec, value: str | None) -> str:
    if not value:
        return "خالی"
    if spec.value_type == "boolean":
        return "✅ فعال" if value.lower() in ("true", "1") else "❌ غیرفعال"
    if spec.value_type == "media":
        return "🖼 تصویر تنظیم شده" if value else "خالی"
    if len(value) > 120:
        return value[:120] + "…"
    return value


# --- Legacy entry (kept) -------------------------------------------------- #
@router.callback_query(F.data == "admin:settings")
async def cb_admin_settings(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, 
        "⚙️ <b>تنظیمات</b>\n\nانتخاب دسته:",
        reply_markup=settings_categories_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "aset:settings")
async def cb_settings_again(callback: CallbackQuery) -> None:
    await cb_admin_settings(callback)


# --- Category browsing ---------------------------------------------------- #
@router.callback_query(F.data.startswith("aset:cat:"))
async def cb_category(callback: CallbackQuery) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("دسته‌بندی یافت نشد", show_alert=True)
        return
    cat = parts[2]
    specs = specs_in_category(cat)
    if not specs:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:settings")]])
        await safe_edit_text(callback, "⚙️ در این دسته تنظیمی نیست.", reply_markup=kb)
        await callback.answer()
        return
    await safe_edit_text(callback, 
        "⚙️ <b>تنظیمات</b>\n\nانتخاب مورد:",
        reply_markup=settings_specs_keyboard(specs),
    )
    await callback.answer()


# --- View a setting ------------------------------------------------------- #
@router.callback_query(F.data.startswith("aset:view:"))
async def cb_view(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("تنظیم ناشناخته", show_alert=True)
        return
    key = parts[2]
    spec = spec_for(key)
    if not spec:
        await callback.answer("تنظیم ناشناخته", show_alert=True)
        return
    ss = SettingsService(uow)
    value = await ss.get(key, spec.default)
    text = (
        f"⚙️ <b>{spec.label}</b>\n\n"
        f"📝 توضیحات: {spec.description}\n"
        f"🔑 کلید: <code>{key}</code>\n"
        f"📄 مقدار: {_fmt_value(spec, value)}\n"
    )
    await safe_edit_text(callback, text, reply_markup=settings_detail_keyboard(spec))
    await callback.answer()


# --- Edit value (string/integer/json) ------------------------------------- #
@router.callback_query(F.data.startswith("aset:edit:"))
async def cb_edit(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("تنظیم ناشناخته", show_alert=True)
        return
    key = parts[2]
    spec = spec_for(key)
    if not spec:
        await callback.answer("ناشناخته", show_alert=True)
        return
    await state.set_data({"settings_key": key})
    await state.set_state(SettingsStates.waiting_value)
    await callback.message.answer(
        f"✏️ مقدار جدید <b>{spec.label}</b> را ارسال کنید:\n(برای انصراف از دکمه استفاده کنید)"
    )
    await callback.answer()


@router.message(SettingsStates.waiting_value)
async def do_set_value(message: Message, state: FSMContext, uow, user: User) -> None:
    data = await state.get_data()
    key = data.get("settings_key")
    spec = spec_for(key)
    if not spec or not message.text:
        await state.clear()
        return
    ss = SettingsService(uow)
    value = message.text.strip()
    if spec.value_type == "integer":
        try:
            int(value)
        except ValueError:
            await message.answer("⚠️ مقدار باید عدد باشد:")
            return
    await ss.set(key, value)
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.SETTINGS_CHANGE, target_type="settings",
                         target_id=key, description=f"تغییر تنظیم {spec.label}",
                         old_data=None, new_data=json.dumps({key: value}, ensure_ascii=False))
    await uow.flush()

    await uow.commit()
    await state.clear()
    await message.answer(
        f"✅ تنظیم «{spec.label}» به‌روزرسانی شد.",
        reply_markup=single_button_kb(back_button(f"aset:cat:{spec.category}")),
    )


# --- Media upload --------------------------------------------------------- #
@router.callback_query(F.data.startswith("aset:media:"))
async def cb_media(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("تنظیم ناشناخته", show_alert=True)
        return
    key = parts[2]
    await state.set_data({"settings_key": key})
    await state.set_state(SettingsStates.waiting_media)
    await callback.message.answer("🖼 تصویر را ارسال کنید:")
    await callback.answer()


@router.message(SettingsStates.waiting_media, F.photo)
async def do_set_media(message: Message, state: FSMContext, uow, user: User) -> None:
    data = await state.get_data()
    key = data.get("settings_key")
    spec = spec_for(key)
    if not spec:
        await state.clear()
        return
    file_id = message.photo[-1].file_id
    ss = SettingsService(uow)
    await ss.set(key, file_id, value_type="media")
    await state.clear()
    api = AdminService(uow)
    await api.log_action(user, LogAction.SETTINGS_CHANGE, target_type="media",
                         target_id=key, description=f"تغییر رسانه {spec.label}")
    await uow.flush()

    await uow.commit()
    await message.answer(
        f"✅ رسانه «{spec.label}» ذخیره شد.",
        reply_markup=single_button_kb(back_button(f"aset:cat:{spec.category}")),
    )


# --- Boolean toggle ------------------------------------------------------- #
@router.callback_query(F.data.startswith("aset:toggle:"))
async def cb_toggle(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("تنظیم ناشناخته", show_alert=True)
        return
    key = parts[2]
    spec = spec_for(key)
    if not spec:
        await callback.answer("ناشناخته", show_alert=True)
        return
    ss = SettingsService(uow)
    current = (await ss.get_bool(key, False))
    await ss.set_bool(key, not current)
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.SETTINGS_CHANGE, target_type="setting",
                         target_id=key, description=f"تغییر کلید {spec.label} به {'روشن' if not current else 'خاموش'}")
    await uow.flush()

    await uow.commit()
    await callback.answer("تغییر کرد")
    await cb_view(callback, uow, user)


@router.message(SettingsStates.waiting_media)
async def cb_media_invalid(message: Message) -> None:
    await message.answer("⚠️ لطفاً یک تصویر ارسال کنید.")


# ================= Legacy flows (kept working) ============================= #
@router.callback_query(F.data == "aset:card")
async def cb_set_card(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.waiting_card_number)
    await callback.message.answer("💳 شماره کارت جدید را ارسال کنید (بدون خط تیره):")
    await callback.answer()


@router.message(SettingsStates.waiting_card_number)
async def do_set_card_number(message: Message, state: FSMContext, uow, user: User) -> None:
    card = message.text.strip() if message.text else ""
    ss = SettingsService(uow)
    await ss.set(SETTING_CARD_NUMBER, card)
    await uow.flush()

    await uow.commit()
    await state.set_state(SettingsStates.waiting_card_holder)
    await message.answer("✅ شماره کارت ذخیره شد.\nنام دارنده کارت را ارسال کنید (یا /skip):")


@router.message(SettingsStates.waiting_card_holder)
async def do_set_card_holder(message: Message, state: FSMContext, uow, user: User) -> None:
    holder = message.text.strip() if message.text and not message.text.startswith("/skip") else ""
    ss = SettingsService(uow)
    await ss.set(SETTING_CARD_HOLDER, holder)
    await uow.flush()

    await uow.commit()
    await state.set_state(SettingsStates.waiting_bank_name)
    await message.answer("🏦 نام بانک را ارسال کنید (یا /skip):")


@router.message(SettingsStates.waiting_bank_name)
async def do_set_bank_name(message: Message, state: FSMContext, uow, user: User) -> None:
    bank = message.text.strip() if message.text and not message.text.startswith("/skip") else ""
    ss = SettingsService(uow)
    await ss.set(SETTING_BANK_NAME, bank)
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.SETTINGS_CHANGE, description="تغییر اطلاعات کارت")
    await uow.flush()

    await uow.commit()
    await state.clear()
    await message.answer("✅ اطلاعات کارت به‌روزرسانی شد.", reply_markup=settings_categories_keyboard())


@router.callback_query(F.data == "aset:support")
async def cb_set_support(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.waiting_support_text)
    await callback.message.answer("📨 متن پشتیبانی جدید را ارسال کنید:")
    await callback.answer()


@router.message(SettingsStates.waiting_support_text)
async def do_set_support(message: Message, state: FSMContext, uow, user: User) -> None:
    text = message.text.strip() if message.text else ""
    await SettingsService(uow).set(SETTING_SUPPORT_TEXT, text)
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.SETTINGS_CHANGE, description="تغییر متن پشتیبانی")
    await uow.flush()

    await uow.commit()
    await state.clear()
    await message.answer("✅ متن پشتیبانی به‌روزرسانی شد.", reply_markup=settings_categories_keyboard())


@router.callback_query(F.data == "aset:welcome")
async def cb_set_welcome(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.waiting_welcome_message)
    await callback.message.answer("👋 پیام خوش‌آمد جدید را ارسال کنید:")
    await callback.answer()


@router.message(SettingsStates.waiting_welcome_message)
async def do_set_welcome(message: Message, state: FSMContext, uow, user: User) -> None:
    text = message.text.strip() if message.text else ""
    await SettingsService(uow).set(SETTING_WELCOME_MESSAGE, text)
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.SETTINGS_CHANGE, description="تغییر پیام خوش‌آمد")
    await uow.flush()

    await uow.commit()
    await state.clear()
    await message.answer("✅ پیام خوش‌آمد به‌روزرسانی شد.", reply_markup=settings_categories_keyboard())


@router.callback_query(F.data == "aset:admins")
async def cb_set_admins(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.waiting_admin_ids)
    await callback.message.answer(
        "👑 برای افزودن ادمین، آیدی عددی تلگرام را ارسال کنید.\n"
        "برای چند ادمین، با کاما جدا کنید. برای پاک کردن، 0 بنویسید:"
    )
    await callback.answer()


@router.message(SettingsStates.waiting_admin_ids)
async def do_set_admins(message: Message, state: FSMContext, uow, user: User) -> None:
    raw = message.text.strip() if message.text else ""
    ss = SettingsService(uow)
    numbers = [int(p.strip()) for p in raw.split(",") if p.strip().isdigit()]
    await ss.set(SETTING_ADMIN_IDS, str(numbers))
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.SETTINGS_CHANGE, description="تغییر لیست ادمین‌ها")
    await uow.flush()

    await uow.commit()
    await state.clear()
    await message.answer("✅ لیست ادمین‌ها به‌روزرسانی شد.", reply_markup=settings_categories_keyboard())