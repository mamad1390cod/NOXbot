# گزارش نهایی رفع اشکال — NOXbot

تاریخ: ۲۰۲۶-۰۹-۰۵ · شاخه: `arena/01a0726c-noxbot` · کامیت: `159e347`

---

## ۱) Root Cause — علت‌های ریشه‌ای

| # | علت ریشه‌ای | نشانه‌ای که تو دیدی |
|---|---|---|
| ۱ | **ساختار Router**: هر ساب‌روتر یک شیء ماژول‌سطح است و فقط **یک بار** می‌تواند parent بگیرد، ولی `_build_admin_router()` مموایز نشده بود و هیچ «ریشهٔ ترکیب» واحدی وجود نداشت. با دومین اجرا (یا دومین محل چسباندن) aiogram خطا می‌داد. | `RuntimeError: Router is already attached to <Router 'admin_router'>` |
| ۲ | **۶۳ فراخوانی `callback.annex(...)`** به‌جای `callback.answer(...)` در ۱۷ فایل. متد `annex` وجود ندارد → هر کلیک `AttributeError`. | «خیلی از دکمه‌ها کار نمی‌کنن» |
| ۳ | مدل `User` نه `display_name` داشت نه `full_name`، ولی کد از هر دو استفاده می‌کرد. | `AttributeError: 'User' object has no attribute 'display_name'` (`admin_roles.py:163`) |
| ۴ | **`callback_data` بلندتر از ۶۴ بایت** (دو UUID در یک کال‌بک). تلگرام کل پیام/ویرایش را رد می‌کند، پس **همهٔ** دکمه‌های آن کیبورد از کار می‌افتند. | `Bad Request: BUTTON_DATA_INVALID` |
| ۵ | **`ThrottlingMiddleware` بی‌صدا** رویدادها را دور می‌ریخت: بیش از ۵ رویداد در ۳ ثانیه = drop بدون هیچ پاسخ و لاگی. ناوبری عادی پنل ادمین همیشه از این سقف رد می‌شود. | دکمه‌ها «تصادفی» کار می‌کردند، لاگ تمیز بود |
| ۶ | در `bot/services/payment.py` یک تابع ماژول‌سطح **وسط بدنهٔ کلاس** تعریف شده بود؛ در نتیجه ۸ متد بعدی از کلاس بیرون افتاده و اصلاً تعریف نمی‌شدند. | کل بخش «مدیریت پرداخت‌ها» مرده بود |
| ۷ | `LogAction.CHANGE_SETTINGS` در enum وجود ندارد (نامش `SETTINGS_CHANGE` است) → ۹ عملیات ادمین کرش می‌کرد. | دکمه‌های فعال/غیرفعال/حذف ادمین |
| ۸ | ستون `Broadcast.status` از نوع `String` بود ولی تایپ پایتونی enum → مقدار برگشتی `str` و `status.value` خطا می‌داد. | خطای بخش آمار/سابقهٔ پیام همگانی |
| ۹ | **هندلرهای غایب**: `acat:edit:` (ویرایش دسته)، `dash:orders:view/page`، `abroad:finalize`، `abroad:schedule` (FSM بن‌بست)، `/menu`، `action:noop`. روتر `account.py` هم هرگز mount نشده بود. | «چند دکمه هم اضاف نشده» |
| ۱۰ | `safe_edit_text` روی پیام‌های مدیادار (عکس محصول/بنر کاستوم) شکست می‌خورد و فقط warning می‌داد → کاربر هیچ تغییری نمی‌دید. | دکمه‌های «بازگشت/خانه» روی صفحات عکس‌دار |
| ۱۱ | `UserContextMiddleware` استثناها را لاگ می‌کرد ولی به کاربر **هیچ** پاسخی نمی‌داد. | چرخش بی‌پایان اسپینر دکمه |

> نکتهٔ مهم دربارهٔ خطای Router: نسخهٔ داخل زیپ با یک بار import کرش نمی‌کرد؛ بازتولید دقیق تریس‌بک تو فقط با **فراخوانی دوم** `_build_admin_router()` ممکن شد. یعنی در کپی محلی تو یک محل ترکیب دوم (یا اجرای دوبارهٔ بدنهٔ ماژول) وجود داشته. به همین دلیل درمان، «حذف یک خط تکراری» نبود؛ ساختار طوری عوض شد که ترکیب دوباره **غیرممکن یا بی‌ضرر** شود و هر تخلف با پیام دقیق fail کند.

---

## ۲) Affected Files — فایل‌های تغییر یافته

**هستهٔ ساختار روتر**
- `bot/handlers/__init__.py` — بازنویسی کامل: تنها ریشهٔ ترکیب، مموایز، تشخیص تکرار، بررسی کامل بودن رجیستری.
- `bot/handlers/admin/__init__.py` — بازنویسی: فقط «اعلان» (`ADMIN_ROUTER_SPECS`) بدون هیچ چسباندنی + `verify_registry_complete()`.
- `bot/loader.py` — `register_middlewares()` idempotent + `mount_routers()` امن.
- `main.py` — استفاده از `mount_routers` + پیام خطای فارسی به‌جای تریس‌بک خام.

**فایل جدید**
- `bot/utils/callback_data.py` — `cb()`، `ValueCodec`، `permission_codec()`، مخزن توکن.
- `bot/middlewares/callback_token.py` — باز کردن توکن قبل از اجرای فیلترها (outer middleware).
- `tools/audit_buttons.py` — ممیزی ایستا دکمه‌ها/هندلرها.
- `tests/` — `conftest.py`, `mocked_bot.py`, `test_routers.py`, `test_callback_data.py`, `test_flows.py`, `test_startup.py`, `test_zz_button_smoke.py`.

**اصلاح باگ (۳۶ فایل)**
`bot/models/user.py`، `bot/models/broadcast.py`، `bot/services/payment.py`، `bot/services/notification.py`، `bot/services/settings.py`، `bot/utils/editing.py`، `bot/utils/backup.py`، `bot/keyboards/rbac.py`، `bot/middlewares/{throttling,user_context,abuse}.py`، `bot/handlers/{menu,account,my_account,custom_cart,configs,support,user_orders,notify_prefs}.py`، `bot/handlers/admin/{admin_roles,admin_categories,admin_customs,admin_products,admin_payments,admin_orders,admin_broadcast,admin_settings,admin_tickets,admin_users,admin_configs,admin_abuse,admin_finance}.py`.

---

## ۳) Fix — چه کاری انجام شد

1. **ترکیب روترها (Architecture A)**: `bot.handlers` تنها ریشهٔ ترکیب است و `admin/__init__.py` فقط رجیستری. `build_admin_router()`/`build_user_router()` نتیجه را کش می‌کنند (پس اجرای دوباره امن است)، قبل از هر تغییری صحت را می‌سنجند و در صورت تکرار یا parent بیگانه `RouterCompositionError` با پیام دقیق پرتاب می‌کنند. نام‌های قدیمی `_build_admin_router`/`_build_user_router` به‌عنوان alias حفظ شدند.
2. **رجیستری کامل**: اگر ماژولی در `bot/handlers/**` یک `router` تعریف کند و در لیست نباشد، برنامه با پیام صریح بالا نمی‌آید (به‌جای اینکه بخش بی‌صدا مرده بماند). همین کار روتر فراموش‌شدهٔ `account.py` را پیدا و mount کرد.
3. **۶۳ مورد `annex` → `answer`** (اسکریپتی + بازبینی + تست).
4. **`display_name` / `full_name` / `mention`** به مدل `User` اضافه شد.
5. **محدودیت ۶۴ بایتی**: `cb()` هر پیلود را می‌سنجد؛ اگر بلند باشد توکن کوتاه `ct:<hash>` می‌سازد و میدل‌ور بیرونی قبل از فیلترها آن را باز می‌کند (هندلرها دست‌نخورده). برای دسترسی‌ها هم کد کوتاه پایدار (۶ کاراکتر) جای نام بلند مجوز نشست. دکمهٔ برندهٔ کاستوم به‌جای دو UUID فقط `registration_id` می‌فرستد.
6. **Throttling**: بودجهٔ جدا برای پیام (۱۲/۳ث) و کال‌بک (۳۰/۳ث)، معافیت مالک/ادمین، و **همیشه پاسخ دادن** به کاربر.
7. **PaymentService** ترمیم شد (۸ متد برگشت) و باگ enum پیام همگانی و `LogAction` اصلاح شد.
8. **هندلرهای جاافتاده** پیاده شدند: ویرایش دستهٔ ‌بندی، مشاهده/صفحه‌بندی سفارش‌ها در داشبورد، `abroad:finalize`، زمان‌بندی پیام همگانی، لغو سراسری، `/menu`، `action:noop`، و پیام راهنما در شش state دکمه‌محور که قبلاً ورودی متنی را بی‌صدا نادیده می‌گرفتند.
9. **`safe_edit_text`** حالا زنجیرهٔ `edit_text → edit_caption → ارسال پیام جدید` دارد؛ دکمه روی صفحات عکس‌دار هم جواب می‌دهد.
10. **بدون سرکوب خطا**: هیچ `try/except: pass` جدیدی اضافه نشد؛ شش مورد قدیمی به لاگ debug ارتقا یافتند و هیچ روتری حذف/غیرفعال/کامنت نشد.

---

## ۴) Router Architecture — معماری نهایی

```
Dispatcher
├── CallbackTokenMiddleware        (outer, callback_query — باز کردن ct:<hash>)
├── UserContext → Maintenance → Abuse → Rbac → Throttling   (inner)
│
├── user_router  = Router("user_root")
│   └── menu, profile, products, configs, cart, customs, custom_cart,
│       account, support, payments, user_orders, my_account, notify_prefs   (۱۳)
│
└── admin_router = Router("admin_root")   ← IsAdmin() روی message و callback_query
    └── admin_panel, admin_products, admin_categories, admin_configs,
        admin_customs, admin_tickets, admin_payments, admin_users,
        admin_broadcast, admin_settings, admin_orders, admin_roles,
        admin_finance, admin_abuse, orphans                                  (۱۵)
        └── هر کدام HasPermission([...]) مخصوص خودش
```

قواعد تضمین‌شده (هر کدام یک تست دارد):
- هر روتر دقیقاً **یک** parent در کل عمر پروسه دارد.
- ترکیب **idempotent** است؛ اجرای دوباره همان درخت را برمی‌گرداند.
- تکرار یا parent بیگانه = خطای صریح، نه خطای مبهم aiogram و نه سکوت.
- هیچ ماژول هندلری بدون ثبت باقی نمی‌ماند.

---

## ۵) Regression Check — بازبینی بخش‌ها

| بخش | نتیجه |
|---|---|
| پنل ادمین / کال‌بک‌ها / FSM | ✅ همهٔ ۲۹۲ الگوی دکمه از طریق Dispatcher واقعی اجرا شد |
| کاستوم: ساخت، دسته، جایزه، متن شروع، تاخیر، ثبت‌نام، ظرفیت، شروع | ✅ بدون خطا؛ انتخاب برنده end-to-end تست شد |
| دسته‌بندی‌ها | ✅ ساخت/ویرایش(جدید)/نمایش/فعال‌سازی/حذف — همه با رفرش صفحه |
| پرداخت: کیف پول، شارژ، خرید، پرداخت ثبت‌نام کاستوم، رد/بازگشت | ✅ بخش پرداخت ادمین از حالت مرده خارج شد |
| سبدها (محصول + کاستوم) | ✅ مرور، افزودن، مشاهده، ثبت‌نام |
| امنیت: دسترسی ادمین، اعتبارسنجی کال‌بک، کاربر غیرمجاز | ✅ کاربر عادی روی `admin:panel` → UNHANDLED (تست جدا) |
| لاگ‌ها | ✅ خطاها دیگر بی‌صدا نیستند؛ کاربر هم پیام می‌گیرد |
| جست‌وجوی `include_router(` / `Router(` / `parent_router` | فقط در ریشهٔ ترکیب و `loader.mount_routers` — بدون تکرار |
| `TODO` / `FIXME` | صفر مورد |
| `except:` خالی | صفر مورد؛ `except Exception` ها بازبینی و لاگ‌دار شدند |
| تحلیل رگرسیون گیت | ⚠️ مخزن فقط `NOXbot.zip` + `README.md` را ترک می‌کرد و کد سورس اصلاً کامیت نشده بود؛ پس «تاریخچهٔ گیت» برای `bot/**` وجود نداشت. مبنای مقایسه، اسنپ‌شات دست‌نخوردهٔ همان زیپ بود و کل سورس در این کامیت وارد گیت شد تا از این پس diff واقعی داشته باشی. |

---

## ۶) Tests — نتیجهٔ هر تست (اجرای واقعی)

| # | تست | دستور | نتیجه |
|---|---|---|---|
| ۱ | کامپایل کل پروژه | `python -m compileall .` | **PASS** (exit 0) |
| ۲ | ایمپورت روترها | `python -c "from bot.handlers import admin_router, user_router; print('ROUTERS OK')"` | **PASS** → `ROUTERS OK` |
| ۳ | بوت واقعی | `python main.py` | **PASS تا مرحلهٔ شبکه** — دیتابیس، seed، اسکجولر و mount روترها بدون خطا؛ فقط `get_me()` در این سندباکس به `api.telegram.org` دسترسی ندارد |
| ۴ | idempotency ساخت روتر | `pytest tests/test_routers.py` (۸ تست) | **PASS** |
| ۵ | تشخیص تکرار روتر با پیام دقیق | همان فایل | **PASS** |
| ۶ | کامل بودن رجیستری ادمین/کاربر | همان فایل | **PASS** |
| ۷ | گیت RBAC روی همهٔ ساب‌روترها | همان فایل | **PASS** |
| ۸ | محدودیت ۶۴ بایت + توکن + کد مجوزها | `pytest tests/test_callback_data.py` (۷ تست) | **PASS** |
| ۹ | جریان‌های واقعی (منو، دسته، نقش، کاستوم، حساب) | `pytest tests/test_flows.py` (۱۰ تست) | **PASS** |
| ۱۰ | دنبالهٔ بوت + کش تنظیمات + بن‌بست نداشتن FSM | `pytest tests/test_startup.py` (۳ تست) | **PASS** |
| ۱۱ | کلیک واقعی روی **۲۹۲** الگوی دکمه | `pytest tests/test_zz_button_smoke.py` (۲ تست) | **PASS** — صفر استثنا، صفر دکمهٔ بی‌هندلر |
| ۱۲ | ممیزی ایستای دکمه‌ها | `python tools/audit_buttons.py` | **PASS** — orphan: ۰، oversized: ۰ |
| — | **مجموع** | `pytest tests/ -q` | **۳۰ passed** |

تنها موردی که در این محیط قابل اجرا نبود: **long-polling زنده با توکن واقعی** (سندباکس به `api.telegram.org` راه ندارد). همهٔ مسیرهای بعد از دریافت آپدیت با Dispatcher واقعی و دیتابیس واقعی تست شده‌اند.

---

## ۷) Final Status

```
READY
```

روی سرور خودت:

```bash
pip install -r requirements.txt      # openpyxl / reportlab / matplotlib هم لازم‌اند
python -m pytest tests/ -q           # باید ۳۰ تست سبز شود
python tools/audit_buttons.py        # باید orphan=0 و oversized=0 بدهد
python main.py                       # اجرای واقعی با BOT_TOKEN خودت
```
