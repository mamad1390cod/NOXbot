"""Dynamic settings registry — the single source of truth for every editable key.

Each entry defines the default value, value type, category (for the admin
editor), and a Persian label/description. The registry drives seeding,
the admin editor, and the runtime cache.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SettingSpec:
    """Specification for one editable setting."""

    key: str
    default: str
    value_type: str = "string"  # string | integer | boolean | json | media
    category: str = "general"
    label: str = ""
    description: str = ""
    is_public: bool = False


# Categories (order they appear in the admin editor)
CATEGORIES: list[str] = [
    "general",
    "payment",
    "support",
    "content",
    "messages",
    "templates",
    "media",
    "buttons",
    "toggles",
]

CATEGORY_LABELS: dict[str, str] = {
    "general": "عمومی",
    "payment": "پرداخت",
    "support": "پشتیبانی",
    "content": "محتوا",
    "messages": "پیام‌ها",
    "templates": "قالب اعلان‌ها",
    "media": "رسانه",
    "buttons": "دکمه‌ها",
    "toggles": "کلیدهای ویژگی‌ها",
}

REGISTRY: list[SettingSpec] = [
    # --- General ---
    SettingSpec("welcome_message", "🎮 <b>به فروشگاه گیمینگ NOXbot خوش آمدید!</b>", "string", "general", "پیام خوش‌آمد", "پیام /start", is_public=True),
    SettingSpec("main_menu_text", "🎮 <b>منوی اصلی فروشگاه</b>\n\nگزینه مورد نظر خود را انتخاب کنید:", "string", "general", "متن منوی اصلی", "متن بالای منوی اصلی"),
    SettingSpec("footer_text", "—", "string", "general", "متن پانوشت", "متن انتهای پیام‌های عمومی"),
    SettingSpec("terms_of_service", "قوانین فروشگاه:\n—", "string", "general", "قوانین و مقررات", "متن قوانین"),
    SettingSpec("privacy_policy", "حریم خصوصی:\n—", "string", "general", "سیاست حفظ حریم خصوصی", "متن حریم خصوصی"),
    SettingSpec("maintenance_message", "🚧 <b>ربات در حال تعمیر است.</b>\nلطفاً بعداً مراجعه کنید.", "string", "general", "پیام تعمیرات", "وقتی حالت تعمیرات فعال است"),
    SettingSpec("language_pack", "fa", "string", "general", "بسته زبان", "زبان فعلی (fa/en)"),
    SettingSpec("support_username", "", "string", "general", "یوزرنیم پشتیبانی", "مثلاً @support"),
    SettingSpec("contact_info", "📞 ارتباط با ما:\n—", "string", "general", "اطلاعات تماس", "متن اطلاعات تماس"),

    # --- Payment ---
    SettingSpec("card_number", "", "string", "payment", "شماره کارت", "شماره کارت برای پرداخت"),
    SettingSpec("card_holder", "", "string", "payment", "نام دارنده کارت", "نام روی کارت"),
    SettingSpec("bank_name", "", "string", "payment", "نام بانک", "بانک صادرکننده"),
    SettingSpec("payment_instructions", "پس از پرداخت، تصویر رسید را ارسال کنید.", "string", "payment", "راهنمای پرداخت", "دستورالعمل پرداخت"),
    SettingSpec("payment_approved_message", "✅ پرداخت شما تایید شد.\n\nادمین محصول شما را به زودی ارسال خواهد کرد.", "string", "payment", "پیام تایید پرداخت", "بعد از تایید ادمین"),
    SettingSpec("payment_rejected_message", "❌ پرداخت شما تایید نشد.\n\nلطفاً برای اطلاعات بیشتر به پشتیبانی پیام دهید.", "string", "payment", "پیام رد پرداخت", "بعد از رد ادمین"),

    # --- Support ---
    SettingSpec("support_text", "برای پشتیبانی با ادمین تماس بگیرید.", "string", "support", "متن پشتیبانی", "متن صفحه پشتیبانی", is_public=True),

    # --- Content ---
    SettingSpec("rules_text", "📜 قوانین:\n—", "string", "content", "متن قوانین بازی", "قوانین عمومی"),

    # --- Messages ---
    SettingSpec("msg_cart_empty", "🛒 سبد خرید شما خالی است.", "string", "messages", "سبد خالی", "پیام سبد خرید خالی"),
    SettingSpec("msg_cart_added", "✅ محصول به سبد خرید اضافه شد.", "string", "messages", "افزودن به سبد", "پیام افزودن محصول"),
    SettingSpec("msg_cart_removed", "✅ آیتم از سبد خرید حذف شد.", "string", "messages", "حذف از سبد", "پیام حذف آیتم"),
    SettingSpec("msg_cart_cleared", "✅ سبد خرید شما خالی شد.", "string", "messages", "پاک کردن سبد", "پیام خالی کردن سبد"),
    SettingSpec("msg_product_not_found", "❌ محصول مورد نظر یافت نشد.", "string", "messages", "محصول یافت نشد", "خطای محصول"),
    SettingSpec("msg_product_out_of_stock", "❌ متاسفانه موجودی این محصول تمام شده است.", "string", "messages", "ناموجود", "خطای ناموجودی"),
    SettingSpec("msg_custom_registered", "🎉 ثبت‌نام شما در کاستوم با موفقیت انجام شد!", "string", "messages", "ثبت کاستوم", "پیام ثبت موفق"),
    SettingSpec("msg_custom_full", "❌ ظرفیت این کاستوم پر شده است.", "string", "messages", "ظرفیت پر", "خطای ظرفیت"),
    SettingSpec("msg_custom_already", "⚠️ شما قبلاً در این کاستوم ثبت‌نام کرده‌اید.", "string", "messages", "تکراری", "خطای ثبت تکراری"),
    SettingSpec("msg_ticket_created", "✅ تیکت شما با موفقیت ثبت شد.\n\nپشتیبانی در اولین فرصت پاسخ خواهد داد.", "string", "messages", "تیکت ثبت شد", "پیام تیکت جدید"),
    SettingSpec("msg_ticket_closed", "✅ تیکت شما بررسی و بسته شد.", "string", "messages", "تیکت بسته شد", "پیام بستن تیکت"),
    SettingSpec("msg_ticket_not_found", "❌ تیکت یافت نشد.", "string", "messages", "تیکت یافت نشد", "خطای تیکت"),

    # --- Order lifecycle messages (support {order_number} interpolation) ---
    SettingSpec("msg_order_approved", "✅ <b>پرداخت شما تایید شد!</b>\n🧾 سفارش {order_number} در حال آماده‌سازی است.", "string", "messages", "سفارش تایید شد", "قالب: {order_number}"),
    SettingSpec("msg_order_preparing", "🔧 سفارش {order_number} در حال آماده‌سازی است.", "string", "messages", "سفارش در آماده‌سازی", "قالب: {order_number}"),
    SettingSpec("msg_order_delivered", "📦 سفارش {order_number} ارسال شد!", "string", "messages", "سفارش ارسال شد", "قالب: {order_number}"),
    SettingSpec("msg_order_completed", "🎉 سفارش {order_number} با موفقیت تکمیل شد. ممنون از خرید شما!", "string", "messages", "سفارش تکمیل شد", "قالب: {order_number}"),
    SettingSpec("msg_order_cancelled", "🚫 سفارش {order_number} لغو شد.", "string", "messages", "سفارش لغو شد", "قالب: {order_number}"),
    SettingSpec("msg_order_rejected", "❌ پرداخت سفارش {order_number} رد شد. لطفاً با پشتیبانی تماس بگیرید.", "string", "messages", "سفارش رد شد", "قالب: {order_number}"),
    SettingSpec("msg_order_refunded", "💰 وجه سفارش {order_number} بازگردانده شد.", "string", "messages", "بازگشت وجه", "قالب: {order_number}"),

    # --- Winning messages ---
    SettingSpec("msg_winner_congratulations", "🎉🎊 <b>تبریک!</b>\n\n🏆 شما برنده شدید!\n\nبرای دریافت جایزه، لطفاً از قسمت <b>پشتیبانی</b> یک تیکت با موضوع \"دریافت جایزه\" ثبت نمایید.", "string", "messages", "تبریک برنده", "پیام برنده"),
    SettingSpec("msg_tournament_ended", "🏁 <b>مسابقه پایان یافت.</b>\n\nبرنده مشخص شد.", "string", "messages", "پایان مسابقه", "پیام پایان مسابقه"),

    # --- Admin notification templates ---
    SettingSpec("tpl_payment_receipt", "💳 <b>رسید پرداخت جدید</b>\n\n🆔 آیدی: <code>{telegram_id}</code>\n👤 نام: {name}\n🧾 سفارش: <code>{order_number}</code>\n💰 مبلغ: {amount} تومان", "string", "templates", "قالب رسید پرداخت", "اعلان به ادمین"),
    SettingSpec("tpl_ticket_new", "🎫 <b>تیکت جدید</b>\n\n🆔 آیدی: <code>{telegram_id}</code>\n👤 نام: {name}\n📝 پیام: {message}", "string", "templates", "قالب تیکت جدید", "اعلان به ادمین"),
    SettingSpec("tpl_ticket_reply", "💬 <b>پاسخ جدید به تیکت #{ticket_id}</b>\n\n{message}", "string", "templates", "قالب پاسخ تیکت", "اعلان به ادمین"),

    # --- Media (Telegram file_ids) ---
    SettingSpec("bot_logo", "", "media", "media", "لوگوی ربات", "تصویر لوگو (file_id)"),
    SettingSpec("home_banner", "", "media", "media", "بنر خانه", "تصویر منوی اصلی (file_id)"),
    SettingSpec("product_banner", "", "media", "media", "بنر محصولات", "تصویر بخش محصولات (file_id)"),
    SettingSpec("tournament_banner", "", "media", "media", "بنر کاستوم‌ها", "تصویر بخش کاستوم (file_id)"),

    # --- Buttons (title + emoji combined label string) ---
    SettingSpec("btn_account", "👤 حساب من", "string", "buttons", "دکمه حساب من", "عنوان دکمه منو"),
    SettingSpec("btn_products", "🛠 محصولات", "string", "buttons", "دکمه محصولات", "عنوان دکمه منو"),
    SettingSpec("btn_customs", "🎮 کاستوم‌ها", "string", "buttons", "دکمه کاستوم‌ها", "عنوان دکمه منو"),
    SettingSpec("btn_configs", "⚡ خرید کانفیگ", "string", "buttons", "دکمه کانفیگ", "عنوان دکمه منو"),
    SettingSpec("btn_cart", "🛒 سبد خرید", "string", "buttons", "دکمه سبد خرید", "عنوان دکمه منو"),
    SettingSpec("btn_custom_cart", "🎯 سبد کاستوم", "string", "buttons", "دکمه سبد کاستوم", "عنوان دکمه منو"),
    SettingSpec("btn_orders", "📦 سفارش‌های من", "string", "buttons", "دکمه سفارش‌های من", "عنوان دکمه منو"),
    SettingSpec("btn_support", "📨 پشتیبانی", "string", "buttons", "دکمه پشتیبانی", "عنوان دکمه منو"),
    SettingSpec("btn_admin", "👑 مدیریت", "string", "buttons", "دکمه مدیریت", "عنوان دکمه ادمین"),
    SettingSpec("btn_back", "🔙 بازگشت", "string", "buttons", "دکمه بازگشت", "دکمه عمومی"),
    SettingSpec("btn_cancel", "❌ انصراف", "string", "buttons", "دکمه انصراف", "دکمه عمومی"),
    SettingSpec("btn_confirm", "✅ تایید", "string", "buttons", "دکمه تایید", "دکمه عمومی"),
    SettingSpec("btn_home", "🏠 منوی اصلی", "string", "buttons", "دکمه منوی اصلی", "دکمه عمومی"),

    # --- Feature toggles ---
    SettingSpec("feature_products", "true", "boolean", "toggles", "محصولات", "فعال/غیرفعال کردن بخش محصولات"),
    SettingSpec("feature_configs", "true", "boolean", "toggles", "کانفیگ‌ها", "فعال/غیرفعال کردن بخش کانفیگ"),
    SettingSpec("feature_customs", "true", "boolean", "toggles", "کاستوم‌ها", "فعال/غیرفعال کردن بخش کاستوم"),
    SettingSpec("feature_orders", "true", "boolean", "toggles", "سفارش‌ها", "فعال/غیرفعال کردن سفارش‌ها"),
    SettingSpec("feature_support", "true", "boolean", "toggles", "پشتیبانی", "فعال/غیرفعال کردن پشتیبانی"),
    SettingSpec("feature_referral", "false", "boolean", "toggles", "سیستم معرفی", "فعال/غیرفعال کردن رفرال"),
    SettingSpec("feature_discounts", "false", "boolean", "toggles", "تخفیف‌ها", "فعال/غیرفعال کردن کد تخفیف"),
    SettingSpec("feature_card_payment", "true", "boolean", "toggles", "پرداخت کارتی", "فعال/غیرفعال کردن پرداخت با کارت"),
    SettingSpec("feature_maintenance_mode", "false", "boolean", "toggles", "حالت تعمیرات", "بستن ربات برای کاربران عادی"),
]

# Fast lookups
BY_KEY: dict[str, SettingSpec] = {s.key: s for s in REGISTRY}

# Well-known media keys
MEDIA_KEYS = ["bot_logo", "home_banner", "product_banner", "tournament_banner"]

# Well-known button keys
BUTTON_KEYS = [
    "btn_account", "btn_products", "btn_customs", "btn_configs", "btn_cart",
    "btn_custom_cart", "btn_orders", "btn_support", "btn_admin",
    "btn_back", "btn_cancel", "btn_confirm", "btn_home",
]

# Well-known feature-toggle keys
TOGGLE_KEYS = [
    "feature_products", "feature_configs", "feature_customs", "feature_orders",
    "feature_support", "feature_referral", "feature_discounts",
    "feature_card_payment", "feature_maintenance_mode",
]


def spec_for(key: str) -> SettingSpec | None:
    return BY_KEY.get(key)


def specs_in_category(category: str) -> list[SettingSpec]:
    return [s for s in REGISTRY if s.category == category]