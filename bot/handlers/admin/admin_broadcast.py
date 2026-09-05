"""Smart broadcast admin handlers — compose, audience, schedule, send, stats."""

import json
import logging

from aiogram import F, Router, types
from bot.utils.editing import safe_edit_text
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.broadcast import (
    broadcast_audience_keyboard,
    broadcast_main_keyboard,
    broadcast_send_keyboard,
    broadcast_type_keyboard,
)
from bot.keyboards.common import back_button, single_button_kb
from bot.models.broadcast import Broadcast, BroadcastStatus, MediaType
from bot.models.log import LogAction
from bot.models.user import User
from bot.services.admin import AdminService
from bot.services.broadcast import BroadcastService
from bot.states import BroadcastStates

router = Router(name="admin_broadcast")
logger = logging.getLogger(__name__)

# Draft store: admin telegram id -> dict
_DRAFTS: dict[int, dict] = {}


def _draft(tg_id: int) -> dict:
    d = _DRAFTS.setdefault(tg_id, {"title": "", "media_type": "text", "audience": {"groups": []}})
    return d


def _audience_label(draft: dict) -> str:
    groups = draft.get("audience", {}).get("groups", [])
    return ", ".join(groups) if groups else "تنظیم نشده"


@router.callback_query(F.data == "admin:broadcast")
async def cb_admin_broadcast(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, 
        "📣 <b>سیستم پیام‌رسانی هوشمند</b>\n\nانتخاب گزینه:",
        reply_markup=broadcast_main_keyboard(),
    )
    await callback.answer()


# --- Compose -------------------------------------------------------------- #
@router.callback_query(F.data == "abroad:compose")
async def cb_compose(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, "📝 نوع پیام را انتخاب کنید:", reply_markup=broadcast_type_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("abroad:type:"))
async def cb_type(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("نوع پیام نامعتبر", show_alert=True)
        return
    mt = parts[2]
    draft = _draft(callback.from_user.id)
    draft["media_type"] = mt
    if mt == "text":
        await state.set_state(BroadcastStates.waiting_text)
        await callback.message.answer("📝 متن پیام را ارسال کنید:")
    elif mt == "poll":
        await state.set_state(BroadcastStates.waiting_poll_question)
        await callback.message.answer("📊 سوال نظرسنجی را ارسال کنید:")
    else:
        await state.set_state(BroadcastStates.waiting_media)
        await callback.message.answer(f"🎬 فایل پیام ({mt}) را ارسال کنید:")
    await callback.answer()


@router.message(BroadcastStates.waiting_text)
async def do_text(message: Message, state: FSMContext, uow, user: User) -> None:
    draft = _draft(user.telegram_id)
    draft["text"] = message.text.strip()
    await _next_step(message, state, user)


@router.message(BroadcastStates.waiting_media, F.photo)
async def do_photo(message: Message, state: FSMContext, user: User) -> None:
    _draft(user.telegram_id)["media_file_id"] = message.photo[-1].file_id
    await state.set_state(BroadcastStates.waiting_caption)
    await message.answer("کپشن را ارسال کنید (یا /skip):")


@router.message(BroadcastStates.waiting_caption)
async def do_caption(message: Message, state: FSMContext, user: User) -> None:
    draft = _draft(user.telegram_id)
    draft["caption"] = "" if message.text.strip() == "/skip" else message.text.strip()
    await _next_step(message, state, user)


@router.message(BroadcastStates.waiting_poll_question)
async def do_poll_q(message: Message, state: FSMContext, user: User) -> None:
    draft = _draft(user.telegram_id)
    draft["poll"] = {"question": message.text.strip(), "options": []}
    await state.set_state(BroadcastStates.waiting_poll_options)
    await message.answer("گزینه‌ها را با خط جدید جدا کنید (هر خط یک گزینه):")


@router.message(BroadcastStates.waiting_poll_options)
async def do_poll_opts(message: Message, state: FSMContext, user: User) -> None:
    draft = _draft(user.telegram_id)
    options = [line.strip() for line in message.text.splitlines() if line.strip()]
    draft["poll"]["options"] = options
    await _next_step(message, state, user)


async def _next_step(message: Message, state: FSMContext, user: User) -> None:
    await state.clear()
    draft = _draft(user.telegram_id)
    draft["status"] = "draft"
    await message.answer(
        "👥 <b>انتخاب مخاطب</b>\n\n"
        f"🔹 نوع پیام: {draft['media_type']}\n🔹 مخاطب فعلی: {_audience_label(draft)}\n\n"
        "یکی از گروه‌ها را اضافه کنید (چندتایی ممکن است):",
        reply_markup=broadcast_audience_keyboard(),
    )


# --- Audience ------------------------------------------------------------- #
@router.callback_query(F.data.startswith("abroad:aud:"))
async def cb_audience(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("دسته‌بندی گروه نامعتبر", show_alert=True)
        return
    group = parts[2]
    draft = _draft(user.telegram_id)
    groups = draft["audience"].setdefault("groups", [])
    groups.append(group)
    draft["audience"]["groups"] = list(dict.fromkeys(groups))  # dedupe
    await safe_edit_text(callback, 
        f"👥 مخاطب: <b>{_audience_label(draft)}</b>\n\n"
        "می‌توانید گروه دیگری اضافه کنید یا ادامه دهید.",
        reply_markup=broadcast_audience_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "abroad:done")
async def cb_done(callback: CallbackQuery, uow, user: User) -> None:
    draft = _draft(user.telegram_id)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⏰ زمان‌بندی", callback_data="abroad:schedule")],
        [types.InlineKeyboardButton(text="👁 پیش‌نمایش", callback_data="abroad:preview")],
        [types.InlineKeyboardButton(text="🚀 ارسال", callback_data="abroad:finalize")],
        [types.InlineKeyboardButton(text="🩺 تست", callback_data="abroad:test")],
    ])
    await safe_edit_text(callback, 
        f"📋 <b>تنظیمات پیام</b>\n\n"
        f"نوع: {draft['media_type']}\nمخاطب: {_audience_label(draft)}\n"
        f"متن: {(draft.get('text') or draft.get('caption') or '—')[:60]}\n\n"
        "ادامه دهید:",
        reply_markup=kb,
    )
    await callback.answer()


# "🚀 ارسال" on the compose screen: confirm before sending (the button used
# to emit abroad:finalize, for which no handler existed at all).
@router.callback_query(F.data == "abroad:finalize")
async def cb_finalize(callback: CallbackQuery, uow, user: User) -> None:
    draft = _draft(user.telegram_id)
    if not draft.get("audience", {}).get("groups"):
        await callback.answer("لطفاً ابتدا مخاطب را انتخاب کنید", show_alert=True)
        return
    await cb_preview(callback, uow, user)


@router.callback_query(F.data == "abroad:preview")
async def cb_preview(callback: CallbackQuery, uow, user: User) -> None:
    draft = _draft(user.telegram_id)
    text = f"📋 <b>پیش‌نمایش</b>\n\nنوع: {draft['media_type']}\nمخاطب: {_audience_label(draft)}\nمتن:\n{draft.get('text') or draft.get('caption') or '(بدون متن)'}"
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🚀 تایید و ارسال", callback_data="abroad:final_now")],
        [types.InlineKeyboardButton(text="➖ توقف", callback_data="abroad:done")],
    ])
    await safe_edit_text(callback, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "abroad:test")
async def cb_test(callback: CallbackQuery, uow, user: User) -> None:
    draft = _draft(user.telegram_id)
    bs = BroadcastService(uow)
    b = await _persist_draft(uow, user, draft)
    b.status = BroadcastStatus.PENDING
    b.scheduled_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    await uow.flush()
    # Send only to the caller.
    bs.bot = callback.bot
    sent = 0
    try:
        if await bs._send(user.telegram_id, b):
            sent = 1
    except Exception as e:
        logger.exception("test send: %s", e)
    await callback.answer("تست ارسال شد" if sent else "تست ناموفق", show_alert=True)


@router.callback_query(F.data == "abroad:final_now")
async def cb_final(callback: CallbackQuery, uow, user: User, state: FSMContext) -> None:
    draft = _draft(user.telegram_id)
    if not draft.get("audience", {}).get("groups"):
        await callback.answer("لطفاً ابتدا مخاطب را انتخاب کنید", show_alert=True)
        return
    b = await _persist_draft(uow, user, draft)
    b.status = BroadcastStatus.PENDING
    from datetime import datetime, timezone
    b.scheduled_at = datetime.now(timezone.utc)
    await uow.flush()

    bs = BroadcastService(uow, bot=callback.bot)
    sent = await bs.send(b)
    await uow.flush()
    api = AdminService(uow)
    await api.log_action(user, LogAction.BROADCAST_SEND, target_type="broadcast",
                         target_id=b.id, description=f"send to {draft['audience']}")
    await uow.flush()
    _DRAFTS.pop(user.telegram_id, None)
    await safe_edit_text(callback, f"✅ ارسال شد. موفق: {sent}، کل: {b.total_target}",
                                     reply_markup=single_button_kb(back_button("admin:broadcast")))
    await callback.answer()


# --- Scheduling ----------------------------------------------------------- #
# orphans.py puts the admin into BroadcastStates.waiting_schedule and asks for a
# date; nothing consumed the answer, so the flow dead-ended right there.
@router.message(BroadcastStates.waiting_schedule)
async def do_schedule(message: Message, state: FSMContext, uow, user: User) -> None:
    from datetime import datetime, timezone

    raw = (message.text or "").strip()
    draft = _draft(user.telegram_id)

    if raw.lower() in {"now", "الان", "فوری"}:
        when = datetime.now(timezone.utc)
    else:
        when = None
        for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                when = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        if when is None:
            await message.answer(
                "⚠️ فرمت تاریخ نامعتبر است.\n"
                "نمونه درست: <code>2026-09-10 21:30</code>\n"
                "یا کلمه <code>now</code> برای ارسال فوری:"
            )
            return

    if not draft.get("audience", {}).get("groups"):
        await state.clear()
        await message.answer(
            "⚠️ ابتدا مخاطب پیام را انتخاب کنید.",
            reply_markup=single_button_kb(back_button("admin:broadcast")),
        )
        return

    broadcast = await _persist_draft(uow, user, draft)
    broadcast.status = BroadcastStatus.PENDING
    broadcast.scheduled_at = when
    await uow.flush()
    api = AdminService(uow)
    await api.log_action(
        user, LogAction.BROADCAST_SEND, target_type="broadcast", target_id=broadcast.id,
        description=f"scheduled for {when.isoformat()}",
    )
    await uow.flush()
    await state.clear()
    _DRAFTS.pop(user.telegram_id, None)
    await message.answer(
        f"⏰ پیام برای <b>{when.strftime('%Y-%m-%d %H:%M')}</b> (UTC) زمان‌بندی شد.",
        reply_markup=single_button_kb(back_button("admin:broadcast")),
    )


async def _persist_draft(uow, user: User, draft: dict) -> Broadcast:
    return await uow.broadcasts.create(
        title=draft.get("title") or "پیام همگانی",
        status=BroadcastStatus.DRAFT,
        audience=json.dumps(draft.get("audience", {})),
        media_type=MediaType(draft["media_type"]),
        media_file_id=draft.get("media_file_id"),
        text=draft.get("text"),
        caption=draft.get("caption"),
        poll=json.dumps(draft.get("poll")) if draft.get("poll") else None,
        created_by_id=user.id,
    )


# --- Stats / history ------------------------------------------------------ #
@router.callback_query(F.data == "abroad:stats")
async def cb_stats(callback: CallbackQuery, uow, user: User) -> None:
    bs = BroadcastService(uow)
    recent = await bs.recent(10)
    if not recent:
        await safe_edit_text(callback, "سابقه‌ای موجود نیست.", reply_markup=single_button_kb(back_button("admin:broadcast")))
        await callback.answer()
        return
    lines = ["📊 <b>سابقه ارسال‌ها</b>\n"]
    for b in recent:
        lines.append(f"• {b.title} — {b.status.value} | ارسال {b.sent_count}/{b.total_target}")
    await safe_edit_text(callback, "\n".join(lines), reply_markup=single_button_kb(back_button("admin:broadcast")))
    await callback.answer()


@router.callback_query(F.data == "abroad:history")
async def cb_history(callback: CallbackQuery, uow, user: User) -> None:
    await cb_stats(callback, uow, user)


# minimal guard