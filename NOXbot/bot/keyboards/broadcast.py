"""Smart broadcast admin keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import back_button


def broadcast_main_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="✍️ ساخت پیام جدید", callback_data="abroad:compose")],
        [InlineKeyboardButton(text="👥 انتخاب مخاطب", callback_data="abroad:audience")],
        [InlineKeyboardButton(text="⏰ زمان‌بندی", callback_data="abroad:schedule")],
        [InlineKeyboardButton(text="👁 پیش‌نمایش", callback_data="abroad:preview")],
        [InlineKeyboardButton(text="🚀 ارسال", callback_data="abroad:send")],
        [InlineKeyboardButton(text="🩺 تست ارسال", callback_data="abroad:test")],
        [InlineKeyboardButton(text="📊 آمار و گزارش", callback_data="abroad:stats")],
        [InlineKeyboardButton(text="📂 قالب‌ها", callback_data="abroad:templates")],
        [InlineKeyboardButton(text="🕘 تاریخچه", callback_data="abroad:history")],
        [back_button("admin:panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def broadcast_type_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="📝 متن", callback_data="abroad:type:text")],
        [InlineKeyboardButton(text="🖼 عکس", callback_data="abroad:type:photo")],
        [InlineKeyboardButton(text="🎬 ویدیو", callback_data="abroad:type:video")],
        [InlineKeyboardButton(text="📄 سند", callback_data="abroad:type:document")],
        [InlineKeyboardButton(text="🎞 انیمیشن", callback_data="abroad:type:animation")],
        [InlineKeyboardButton(text="🎙 صدا", callback_data="abroad:type:voice")],
        [InlineKeyboardButton(text="📊 نظرسنجی", callback_data="abroad:type:poll")],
        [back_button("abroad:compose")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def broadcast_audience_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="همه", callback_data="abroad:aud:all")],
        [InlineKeyboardButton(text="فعال", callback_data="abroad:aud:active")],
        [InlineKeyboardButton(text="غیرفعال", callback_data="abroad:aud:inactive")],
        [InlineKeyboardButton(text="VIP", callback_data="abroad:aud:vip")],
        [InlineKeyboardButton(text="مشتریان", callback_data="abroad:aud:customers")],
        [InlineKeyboardButton(text="شرکت‌کنندگان کاستوم", callback_data="abroad:aud:tournament_participants")],
        [InlineKeyboardButton(text="خریداران محصول", callback_data="abroad:aud:product_buyers")],
        [InlineKeyboardButton(text="خریداران کانفیگ", callback_data="abroad:aud:config_buyers")],
        [InlineKeyboardButton(text="⚠️ تنظیم گروه‌ها کامل شد", callback_data="abroad:done")],
        [back_button("admin:broadcast")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def broadcast_send_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="🚀 ارسال نهایی", callback_data="abroad:send_now")],
        [InlineKeyboardButton(text="➖ توقف", callback_data="abroad:pause")],
        [InlineKeyboardButton(text="❌ لغو", callback_data="abroad:cancel")],
        [back_button("admin:broadcast")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)