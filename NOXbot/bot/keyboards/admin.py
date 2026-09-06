"""Admin panel keyboards."""

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import back_button, home_button
from bot.models.product import Product
from bot.models.config_shop import ConfigProduct
from bot.models.custom import Custom
from bot.models.ticket import Ticket, TicketCategory


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Build the admin dashboard keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(text="📊 آمار", callback_data="admin:stats"),
            InlineKeyboardButton(text="📦 محصولات", callback_data="admin:products"),
        ],
        [
            InlineKeyboardButton(text="🏷 دسته‌ها", callback_data="admin:categories"),
            InlineKeyboardButton(text="🎮 کاستوم‌ها", callback_data="admin:customs"),
        ],
        [
            InlineKeyboardButton(text="⚡ کانفیگ‌ها", callback_data="admin:configs"),
            InlineKeyboardButton(text="🎫 تیکت‌ها", callback_data="admin:tickets"),
        ],
        [
            InlineKeyboardButton(text="🎯 سفارش‌ها", callback_data="admin:orders"),
            InlineKeyboardButton(text="💳 پرداخت‌ها", callback_data="admin:payments"),
        ],
        [
            InlineKeyboardButton(text="👥 کاربران", callback_data="admin:users"),
        ],
        [
            InlineKeyboardButton(text="📣 اطلاع‌رسانی", callback_data="admin:broadcast"),
            InlineKeyboardButton(text="⚙️ تنظیمات", callback_data="admin:settings"),
        ],
        [
            InlineKeyboardButton(text="٪ کد تخفیف", callback_data="admin:discounts"),
            InlineKeyboardButton(text="📜 لاگ‌ها", callback_data="admin:logs"),
        ],
        [
            InlineKeyboardButton(text="🛡 نقش‌ها و ادمین‌ها", callback_data="admin:roles"),
            InlineKeyboardButton(text="💵 گزارش مالی", callback_data="admin:finance"),
        ],
        [InlineKeyboardButton(text="🚨 ضد سوءاستفاده", callback_data="admin:abuse")],
        [InlineKeyboardButton(text="🧾 شارژ کیف پول", callback_data="atu:menu")],
        [InlineKeyboardButton(text="💾 بکاپ دیتابیس", callback_data="admin:backup")],
        [home_button("menu:home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_products_keyboard() -> InlineKeyboardMarkup:
    """Product management menu."""
    keyboard = [
        [
            InlineKeyboardButton(text="➕ افزودن محصول", callback_data="aprod:add"),
            InlineKeyboardButton(text="📦 لیست محصولات", callback_data="aprod:list"),
        ],
        [
            InlineKeyboardButton(text="🔍 جستجو", callback_data="aprod:search"),
            InlineKeyboardButton(text="🏷 دسته‌ها", callback_data="acat:list"),
        ],
        [back_button("admin:panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def product_management_keyboard(product: Product) -> InlineKeyboardMarkup:
    """Keyboard for a single product's admin actions."""
    vis_icon = "✅" if product.is_visible else "❌"
    act_icon = "🟢" if product.status.value == "active" else "🔴"
    keyboard = [
        [
            InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"aprod:edit:{product.id}"),
            InlineKeyboardButton(text="🔄 کپی", callback_data=f"aprod:dup:{product.id}"),
        ],
        [
            InlineKeyboardButton(text=f" {act_icon} فعال/غیرفعال", callback_data=f"aprod:toggle:{product.id}"),
            InlineKeyboardButton(text=f" {vis_icon} نمایش", callback_data=f"aprod:vis:{product.id}"),
        ],
        [
            InlineKeyboardButton(text="↪️ انتقال", callback_data=f"aprod:move:{product.id}"),
            InlineKeyboardButton(text="🗑 حذف", callback_data=f"aprod:del:{product.id}"),
        ],
        [back_button("admin:products")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def product_edit_fields_keyboard(product_id: str) -> InlineKeyboardMarkup:
    """Choose which field to edit for a product."""
    keyboard = [
        [InlineKeyboardButton(text="عنوان", callback_data=f"pedit:title:{product_id}")],
        [InlineKeyboardButton(text="توضیحات", callback_data=f"pedit:desc:{product_id}")],
        [InlineKeyboardButton(text="قیمت", callback_data=f"pedit:price:{product_id}")],
        [InlineKeyboardButton(text="موجودی", callback_data=f"pedit:stock:{product_id}")],
        [InlineKeyboardButton(text="موجودی نامحدود", callback_data=f"pedit:unlim:{product_id}")],
        [InlineKeyboardButton(text="تصویر", callback_data=f"pedit:image:{product_id}")],
        [back_button("admin:products")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def category_management_keyboard(prefix: str = "acat") -> InlineKeyboardMarkup:
    """Category management menu."""
    keyboard = [
        [InlineKeyboardButton(text="➕ افزودن دسته", callback_data=f"{prefix}:add")],
        [InlineKeyboardButton(text="📂 لیست دسته‌ها", callback_data=f"{prefix}:list")],
        [back_button("admin:panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def category_list_keyboard(categories: Sequence, prefix: str = "acat") -> InlineKeyboardMarkup:
    """Keyboard for a list of categories."""
    keyboard = []
    for cat in categories:
        active = "🟢" if cat.is_active else "🔴"
        keyboard.append(
            [InlineKeyboardButton(text=f"{active} {cat.name}", callback_data=f"{prefix}:view:{cat.id}")]
        )
    keyboard.append([back_button("admin:categories")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def category_detail_keyboard(cat_id: str, prefix: str = "acat") -> InlineKeyboardMarkup:
    """Keyboard for category admin actions."""
    keyboard = [
        [
            InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"{prefix}:edit:{cat_id}"),
            InlineKeyboardButton(text="🗑 حذف", callback_data=f"{prefix}:del:{cat_id}"),
        ],
        [
            InlineKeyboardButton(text="👁 نمایش", callback_data=f"{prefix}:vis:{cat_id}"),
            InlineKeyboardButton(text="↕ فعال/غیرفعال", callback_data=f"{prefix}:toggle:{cat_id}"),
        ],
        [back_button(f"{prefix}:list")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_tickets_keyboard() -> InlineKeyboardMarkup:
    """Ticket admin menu."""
    keyboard = [
        [
            InlineKeyboardButton(text="🟢 باز", callback_data="atick:open"),
            InlineKeyboardButton(text="🔴 بسته", callback_data="atick:closed"),
        ],
        [
            InlineKeyboardButton(text="🔍 جستجو", callback_data="atick:search"),
            InlineKeyboardButton(text="📤 خروجی", callback_data="atick:export"),
        ],
        [
            InlineKeyboardButton(text="📂 دسته‌بندی‌ها", callback_data="aticat:list"),
        ],
        [back_button("admin:panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_ticket_list_keyboard(tickets: Sequence, page: int = 0) -> InlineKeyboardMarkup:
    """Keyboard for a list of tickets in admin."""
    keyboard = []
    for t in tickets:
        user = t.user
        label = f"#{t.subject} 👤{user.telegram_id if user else '?'}"
        keyboard.append(
            [InlineKeyboardButton(text=label, callback_data=f"atick:view:{t.id}")]
        )
    keyboard.append([back_button("admin:tickets")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def ticket_admin_detail_keyboard(ticket_id: str) -> InlineKeyboardMarkup:
    """Keyboard for admin ticket view."""
    keyboard = [
        [
            InlineKeyboardButton(text="✍️ پاسخ", callback_data=f"atick:reply:{ticket_id}"),
            InlineKeyboardButton(text="✅ تکمیل شد", callback_data=f"ticket:close:{ticket_id}"),
        ],
        [
            InlineKeyboardButton(text="🗑 حذف", callback_data=f"atick:del:{ticket_id}"),
        ],
        [back_button("admin:tickets")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_payments_keyboard() -> InlineKeyboardMarkup:
    """Payment admin menu."""
    keyboard = [
        [
            InlineKeyboardButton(text="⏳ در انتظار", callback_data="apay:pending"),
            InlineKeyboardButton(text="✅ تایید شده", callback_data="apay:approved"),
        ],
        [
            InlineKeyboardButton(text="❌ رد شده", callback_data="apay:rejected"),
            InlineKeyboardButton(text="همه", callback_data="apay:all"),
        ],
        [back_button("admin:panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def payment_review_keyboard(payment_id: str) -> InlineKeyboardMarkup:
    """Keyboard to review a payment."""
    keyboard = [
        [
            InlineKeyboardButton(text="✅ تایید درخواست", callback_data=f"apay:approve:{payment_id}"),
            InlineKeyboardButton(text="❌ رد درخواست", callback_data=f"apay:reject:{payment_id}"),
        ],
        [
            InlineKeyboardButton(text="🔁 درخواست رسید مجدد", callback_data=f"apay:again:{payment_id}"),
        ],
        [back_button("admin:payments")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_users_keyboard() -> InlineKeyboardMarkup:
    """User admin menu."""
    keyboard = [
        [InlineKeyboardButton(text="🔍 جستجو کاربر", callback_data="auser:search")],
        [InlineKeyboardButton(text="📋 لیست کاربران", callback_data="auser:list")],
        [InlineKeyboardButton(text="🚫 بن شدگان", callback_data="auser:banned")],
        [back_button("admin:panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def user_detail_keyboard(user_id: str, is_banned: bool, is_admin: bool) -> InlineKeyboardMarkup:
    """Keyboard for a user's admin actions."""
    keyboard = []
    if is_banned:
        keyboard.append([InlineKeyboardButton(text="✅ رفع بن", callback_data=f"auser:unban:{user_id}")])
    else:
        keyboard.append([InlineKeyboardButton(text="🚫 بن", callback_data=f"auser:ban:{user_id}")])
    if not is_admin:
        keyboard.append([InlineKeyboardButton(text="👑 ادمین", callback_data=f"auser:makeadmin:{user_id}")])
    keyboard.append([InlineKeyboardButton(text="🗑 حذف", callback_data=f"auser:del:{user_id}")])
    if is_admin:
        keyboard.append([InlineKeyboardButton(text="🫳 حذف ادمین", callback_data=f"auser:removeadmin:{user_id}")])
    keyboard.append([back_button("admin:users")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_customs_keyboard() -> InlineKeyboardMarkup:
    """Custom admin menu."""
    keyboard = [
        [InlineKeyboardButton(text="➕ افزودن کاستوم", callback_data="acustom:add")],
        [InlineKeyboardButton(text="📋 لیست کاستوم‌ها", callback_data="acustom:list")],
        [InlineKeyboardButton(text="🏷 دسته‌های کاستوم", callback_data="accat:list")],
        [back_button("admin:panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def custom_admin_list_keyboard(customs: Sequence, page: int = 0) -> InlineKeyboardMarkup:
    keyboard = []
    for c in customs:
        status = {
            "draft": "🔵",
            "registration_open": "🟢",
            "registration_closed": "🟡",
            "in_progress": "🟠",
            "completed": "⚪",
            "cancelled": "🔴",
        }.get(c.status.value, "▫️")
        keyboard.append(
            [InlineKeyboardButton(text=f"{status} {c.title}", callback_data=f"acustom:view:{c.id}")]
        )
    keyboard.append([back_button("admin:customs")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def custom_admin_detail_keyboard(custom_id: str, custom=None) -> InlineKeyboardMarkup:
    """Build keyboard for custom admin detail view.
    
    Args:
        custom_id: The custom ID
        custom: Optional Custom object for dynamic button display
    """
    keyboard = []
    
    # Edit button (always show unless started/completed/cancelled)
    if custom is None or custom.status not in ("started", "completed", "cancelled"):
        keyboard.append([InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"acustom:edit:{custom_id}")])
    
    # Prize management
    if custom and custom.prize_set:
        keyboard.append([
            InlineKeyboardButton(text="👁 مشاهده جایزه", callback_data=f"acustom:view_prize:{custom_id}"),
            InlineKeyboardButton(text="✏️ ویرایش جایزه", callback_data=f"acustom:edit_prize:{custom_id}"),
        ])
        if custom.status not in ("started", "completed", "cancelled"):
            keyboard.append([InlineKeyboardButton(text="🗑 حذف جایزه", callback_data=f"acustom:clear_prize:{custom_id}")])
    else:
        keyboard.append([InlineKeyboardButton(text="🎁 تعیین جایزه", callback_data=f"acustom:set_prize:{custom_id}")])
    
    # Start message management
    if custom and custom.start_message:
        keyboard.append([
            InlineKeyboardButton(text="👁 مشاهده متن شروع", callback_data=f"acustom:view_start_msg:{custom_id}"),
            InlineKeyboardButton(text="✏️ ویرایش متن شروع", callback_data=f"acustom:set_start_msg:{custom_id}"),
        ])
        if custom.status not in ("started", "completed", "cancelled"):
            keyboard.append([InlineKeyboardButton(text="🗑 حذف متن شروع", callback_data=f"acustom:clear_start_msg:{custom_id}")])
    else:
        keyboard.append([InlineKeyboardButton(text="📝 متن شروع کاستوم", callback_data=f"acustom:set_start_msg:{custom_id}")])
    
    # Players button (always show)
    keyboard.append([InlineKeyboardButton(text="👥 بازیکنان", callback_data=f"acustom:players:{custom_id}")])
    
    # Registration controls (only if not started/completed/cancelled)
    if custom is None or custom.status not in ("started", "completed", "cancelled"):
        keyboard.append([
            InlineKeyboardButton(text="🟢 باز ثبت", callback_data=f"acustom:open:{custom_id}"),
            InlineKeyboardButton(text="🔴 بستن ثبت", callback_data=f"acustom:close:{custom_id}"),
        ])
    
    # Start custom button (only if registration was open and not started yet)
    if custom and custom.status in ("registration_open", "registration_closed", "ready"):
        keyboard.append([InlineKeyboardButton(text="🚀 شروع کاستوم", callback_data=f"acustom:start:{custom_id}")])
    
    # Postpone button (only if not started/completed/cancelled)
    if custom and custom.status not in ("started", "completed", "cancelled"):
        keyboard.append([InlineKeyboardButton(text="⏰ عقب انداختن", callback_data=f"acustom:postpone:{custom_id}")])
    
    # Winner selection and notification (show if there are registrations)
    keyboard.append([
        InlineKeyboardButton(text="🏆 انتخاب برنده", callback_data=f"acustom:winner:{custom_id}"),
        InlineKeyboardButton(text="📣 اطلاع به شرکت‌کنندگان", callback_data=f"acustom:notify:{custom_id}"),
    ])
    
    # Delete and Cancel (only if not completed/cancelled)
    if custom is None or custom.status not in ("completed", "cancelled"):
        keyboard.append([
            InlineKeyboardButton(text="🗑 حذف", callback_data=f"acustom:del:{custom_id}"),
            InlineKeyboardButton(text="🚫 لغو", callback_data=f"acustom:cancel:{custom_id}"),
        ])
    
    keyboard.append([back_button("admin:customs")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def broadcast_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="📝 پیام متنی", callback_data="abroad:msg"),
            InlineKeyboardButton(text="🖼 تصویر", callback_data="abroad:photo"),
        ],
        [
            InlineKeyboardButton(text="🎬 ویدیو", callback_data="abroad:video"),
            InlineKeyboardButton(text="📁 فایل", callback_data="abroad:file"),
        ],
        [back_button("admin:panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_settings_keyboard() -> InlineKeyboardMarkup:
    """Deprecated — replaced by the registry-driven settings editor."""
    from bot.keyboards.settings import settings_categories_keyboard
    return settings_categories_keyboard()


def admin_discounts_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="➕ افزودن کد تخفیف", callback_data="adisc:add")],
        [InlineKeyboardButton(text="📋 لیست کدها", callback_data="adisc:list")],
        [back_button("admin:panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_configs_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="➕ افزودن کانفیگ", callback_data="aconf:add")],
        [InlineKeyboardButton(text="📋 لیست کانفیگ‌ها", callback_data="aconf:list")],
        [back_button("admin:panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)