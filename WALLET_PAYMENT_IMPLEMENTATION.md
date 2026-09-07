# سیستم پرداخت کیف پول — مستندات پیاده‌سازی

## خلاصه

سیستم پرداخت کیف پول به‌صورت کامل پیاده‌سازی شد و با تمام سیستم‌های خرید بات یکپارچه گردید. از این پس، کیف پول کاربر روش پرداخت اصلی برای تمام خریدها (محصولات و کانفیگ‌ها) است.

---

## معماری سیستم

```
                  ┌─────────────────┐
                  │   💰 Wallet     │
                  │  (wallet_balance)│
                  └────────┬────────┘
                           │
             ┌─────────────┴─────────────┐
             │                           │
             ▼                           ▼
       🛒 محصولات                  ⚡ کانفیگ‌ها
             │                           │
             └─────────────┬─────────────┘
                           │
                    🛒 سبد خرید مشترک
                           │
                    بررسی موجودی
                           │
                    ┌──────┴──────┐
                    │             │
                 کافی            ناکافی
                    │             │
                    ▼             ▼
             کسر از Wallet   💰 شارژ حساب
                    │             │
                    ▼             ▼
             ثبت تراکنش       سیستم Top-Up
                    │             │
                    ▼             ▼
                  سفارش       کارت‌به‌کارت
                  تایید           │
                                  ▼
                                رسید
                                  │
                                  ▼
                              تأیید ادمین
                                  │
                                  ▼
                            افزایش Wallet
```

---

## فایل‌های تغییر یافته

### 1. `bot/services/wallet_payment.py` (جدید)
سرویس اصلی پرداخت کیف پول با قابلیت‌های:
- **بررسی موجودی**: `check_balance(user_id)`
- **پرداخت اتمی**: `pay_order_with_wallet(user_id, order_id, amount)`
- **جلوگیری از پرداخت مجدد**: Idempotency check
- **جلوگیری از Race Condition**: SELECT FOR UPDATE
- **ثبت تراکنش**: TransactionType.PURCHASE

### 2. `bot/handlers/cart.py` (تغییر یافته)
تابع `cb_cart_checkout` به‌روزرسانی شد:
- بررسی موجودی کیف پول قبل از نمایش صفحه پرداخت
- نمایش پیام "موجودی کافی" با دکمه پرداخت
- نمایش پیام "موجودی ناکافی" با دکمه شارژ حساب

### 3. `bot/handlers/payments.py` (تغییر یافته)
تابع `cb_checkout_confirm` به‌روزرسانی شد:
- استفاده از `WalletPaymentService` برای کسر موجودی
- ایجاد سفارش با `PaymentMethod.BALANCE`
- تایید خودکار سفارش (approve_payment)
- نمایش پیام موفقیت با موجودی جدید

### 4. `bot/keyboards/cart_keyboard.py` (تغییر یافته)
دو کیبورد جدید اضافه شد:
- `wallet_checkout_keyboard()`: برای موجودی کافی
- `insufficient_balance_keyboard()`: برای موجودی ناکافی

---

## جریان خرید — مرحله به مرحله

### 1. مشتری سبد خرید را باز می‌کند
```
callback: menu:cart
handler: cb_cart (cart.py)
```

### 2. مشتری روی "پرداخت" کلیک می‌کند
```
callback: cart:checkout
handler: cb_cart_checkout (cart.py)
```

**بررسی موجودی:**
```python
wallet_balance = user.wallet_balance or 0
has_sufficient_balance = wallet_balance >= total_price
```

### 3a. اگر موجودی کافی بود:
```
نمایش پیام:
  💰 مبلغ پرداختی: X تومان
  💳 موجودی کیف پول: Y تومان
  ✅ موجودی کافی است!

دکمه‌ها:
  [💳 پرداخت از کیف پول]  → checkout:confirm
  [❌ انصراف]              → menu:cart
```

### 3b. اگر موجودی ناکافی بود:
```
نمایش پیام:
  ❌ موجودی کیف پول کافی نیست
  
  💰 مبلغ سفارش: X تومان
  💳 موجودی فعلی: Y تومان
  📉 کسری: Z تومان
  
  لطفاً ابتدا کیف پول خود را شارژ کنید.

دکمه‌ها:
  [💰 شارژ حساب]         → tu:menu
  [🔙 بازگشت به سبد]     → menu:cart
```

### 4. مشتری روی "پرداخت از کیف پول" کلیک می‌کند
```
callback: checkout:confirm
handler: cb_checkout_confirm (payments.py)
```

**مراحل اجرا:**
1. بررسی مجدد موجودی (double-check)
2. ایجاد سفارش: `order_service.create_order_from_cart(payment_method=BALANCE)`
3. کسر موجودی: `wallet_service.pay_order_with_wallet()`
   - SELECT FOR UPDATE برای lock ردیف کاربر
   - بررسی موجودی
   - کسر مبلغ
   - آپدیت Payment record به APPROVED
   - ثبت Transaction (PURCHASE)
4. تایید سفارش: `order_service.approve_payment()`
   - تغییر وضعیت: WAITING_PAYMENT → PAYMENT_UPLOADED → PAYMENT_REVIEWING → APPROVED
   - کاهش موجودی محصولات (decrement_items_stock)
5. نمایش پیام موفقیت

### 5. نمایش پیام موفقیت
```
✅ پرداخت موفق!

🧾 کد سفارش: NOX-2026-XXXXXX
💰 مبلغ پرداخت‌شده: X تومان
💳 موجودی جدید: Y تومان

سفارش شما در حال پردازش است.

دکمه‌ها:
  [📦 پیگیری سفارش]  → orders:view:{order_id}
  [🏠 منوی اصلی]     → menu:home
```

---

## Idempotency (جلوگیری از پرداخت مجدد)

### مشکل
اگر کاربر چند بار روی دکمه پرداخت کلیک کند یا درخواست Telegram دوباره ارسال شود، نباید مبلغ دوبار کسر شود.

### راه‌حل
در `WalletPaymentService.pay_order_with_wallet()`:

```python
# بررسی اینکه آیا سفارش قبلاً پرداخت شده
existing_payment = await self._get_approved_wallet_payment(order_id)
if existing_payment:
    raise AlreadyPaidError(
        f"Order {order_id} already paid via wallet"
    )
```

این بررسی قبل از کسر موجودی انجام می‌شود و از پرداخت مجدد جلوگیری می‌کند.

---

## Race Condition Prevention

### مشکل
دو خرید همزمان نباید بتوانند از یک موجودی دوبار استفاده کنند.

### راه‌حل
استفاده از `SELECT FOR UPDATE` برای قفل کردن ردیف کاربر:

```python
stmt = (
    select(User)
    .where(User.id == user_id)
    .with_for_update(skip_locked=False)
)
```

این قفل تا پایان تراکنش دیتابیس باقی می‌ماند و از race condition جلوگیری می‌کند.

---

## تراکنش‌ها (Transactions)

هر بار که مبلغی از کیف پول کسر می‌شود، یک `Transaction` ثبت می‌شود:

```python
txn = await uow.transactions.add(
    user_id=user_id,
    type_=TransactionType.PURCHASE,
    amount=-amount,  # منفی برای کسر
    balance_before=balance_before,
    balance_after=balance_after,
    ref_id=order_id,
    note=f"خرید سفارش {order_number}",
)
```

### اطلاعات ثبت شده:
- **User ID**: شناسه کاربر
- **Type**: PURCHASE
- **Amount**: مبلغ کسر شده (منفی)
- **Balance Before**: موجودی قبل از کسر
- **Balance After**: موجودی بعد از کسر
- **Ref ID**: شناسه سفارش
- **Note**: توضیحات
- **Created At**: زمان ایجاد

---

## تست‌های انجام شده

تمام 10 سناریوی تست با موفقیت پاس شدند:

1. ✅ افزودن محصول به سبد
2. ✅ بررسی موجودی کیف پول
3. ✅ ایجاد سفارش از سبد
4. ✅ پرداخت با موجودی کافی
5. ✅ ثبت تراکنش PURCHASE
6. ✅ Idempotency (جلوگیری از پرداخت مجدد)
7. ✅ موجودی ناکافی (InsufficientBalanceError)
8. ✅ خرید کانفیگ
9. ✅ سبد ترکیبی (محصول + کانفیگ)
10. ✅ بررسی رکوردهای Payment

---

## نکات مهم

### 1. سبد خرید مشترک
محصولات و کانفیگ‌ها از یک سبد خرید مشترک استفاده می‌کنند. کاربر می‌تواند همزمان محصول و کانفیگ بخرد.

### 2. کارت‌به‌کارت فقط برای شارژ
پرداخت کارت‌به‌کارت فقط در سیستم شارژ حساب (Top-Up) استفاده می‌شود، نه برای خرید مستقیم.

### 3. تایید خودکار
سفارش‌های پرداخت شده با کیف پول به‌صورت خودکار تایید می‌شوند (نیاز به تایید ادمین ندارند).

### 4. موجودی مشترک
همه خریدها از یک `wallet_balance` مشترک استفاده می‌کنند.

### 5. Backward Compatibility
هندلرهای قدیمی پرداخت کارتی (`pay:submit:`) هنوز در کد هستند برای سازگاری با سفارش‌های قدیمی که ممکن است هنوز در وضعیت WAITING_PAYMENT باشند.

---

## خطاها و استثناها

### InsufficientBalanceError
زمانی که موجودی کافی نیست:
```python
raise InsufficientBalanceError(required=amount, available=current_balance)
```

### AlreadyPaidError
زمانی که سفارش قبلاً پرداخت شده:
```python
raise AlreadyPaidError(f"Order {order_id} already paid via wallet")
```

---

## جمع‌بندی

سیستم پرداخت کیف پول به‌صورت کامل پیاده‌سازی شد و تمام نیازمندی‌های مطرح شده برآورده شدند:

✅ کیف پول روش پرداخت اصلی تمام خریدها  
✅ موجودی کافی → پرداخت مستقیم  
✅ موجودی ناکافی → هدایت به شارژ حساب  
✅ جلوگیری از پرداخت مجدد (Idempotency)  
✅ جلوگیری از Race Condition  
✅ ثبت تراکنش برای تمام خریدها  
✅ پشتیبانی از محصولات و کانفیگ‌ها  
✅ سبد خرید مشترک  
✅ کارت‌به‌کارت فقط برای شارژ  
✅ 10/10 تست موفق  
