# NOXbot Shop

A complete, production-ready **Telegram Shop Bot for gaming services** (Persian).

Built with **Clean Architecture**: handlers → services → repositories → database.

## Features

- **Home menu** — محصولات، کاستوم‌ها، خرید کانفیگ، سبد خرید، سبد کاستوم، پشتیبانی، مدیریت (only for the owner)
- **Product system** — unlimited categories/products, stock, unlimited stock, visibility, move, duplicate, delete, account-info collection (CODM username / email / password) with confirmation
- **Config shop** — separate section with categories & products, shares the same cart & checkout
- **Shopping cart** — quantity +/-, delete, clear, continue shopping, checkout, total price
- **Custom (tournament) system** — free/paid, banner, rules, date/time, prize, entry fee, capacity, player list, open/close registration, cancel, delete, notify participants, pick winner (player or team) + winner congratulations
- **Custom cart** — add customs, remove, clear, register (CODM username + confirmation; free → done, paid → receipt)
- **Support tickets** — categories (create/edit/delete/enable/disable/sort), user flow (category → message → confirm), admin panel (open/closed/search/delete/export CSV), admin replies, close ticket → user notified
- **Payment system** — card number/holder/bank shown, receipt image upload, admin review (✅ تایید / ❌ رد / 🔁 رسید مجدد), order auto-marked PAID on approval
- **Admin panel** — dashboard with stats (users, orders, revenue, products, configs, customs, tickets, pending/approved/rejected payments), broadcast (text/photo/video/file), user search/ban/unban/delete/details, settings (card, support text, welcome message, admin IDs), logs
- **Security** — password gate for admin, throttling middleware, ban blocking, duplicate registration & payment prevention, input validation, DB transactions

## Tech stack

- Python 3.12+
- aiogram 3.x
- SQLAlchemy 2.x (async) + aiosqlite (SQLite, PostgreSQL-ready)
- Alembic (migrations)
- APScheduler (background scheduler)
- Pydantic v2 / pydantic-settings (config)

## Quick start

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # then edit BOT_TOKEN and OWNER_ID
alembic upgrade head     # create schema
python main.py           # run the bot
```

## Project structure

```
main.py                     # entry point: DB init, middleware, routers, polling
alembic.ini                 # Alembic config
migrations/                 # Alembic migration scripts
bot/
├── config.py               # Pydantic settings (.env)
├── loader.py               # shared Bot/Dispatcher
├── texts.py                # Persian UI strings
├── models/                 # SQLAlchemy ORM models (20 tables)
├── database/               # engine, session, UnitOfWork
├── repositories/           # repository pattern (data access)
├── services/               # service layer (business logic)
├── keyboards/              # inline keyboard builders
├── handlers/               # aiogram routers (user + admin/)
├── middlewares/            # user-context (registration/ban) + throttling
├── filters/                # IsAdmin etc.
├── states/                 # FSM states
└── utils/                  # format, pagination, backup/export
```

## Architecture flow

```
aiogram handler → Service → Repository → ORM model → SQLite/PostgreSQL
```

- Handlers contain **no SQL** and **no inline keyboard markup** (keyboards live in `keyboards/`).
- Services hold business rules (stock checks, duplicate prevention, payment approval).
- Repositories encapsulate all query logic.
- Every request from a user notifies all admins with full context (IDs, username, name, date/time, type).
- Every important admin action writes an `AdminLog` entry.

## Admin access

- The **👑 مدیریت** button appears only when the Telegram ID equals `OWNER_ID`.
- Normal admins can unlock the panel via `/admin` + the password (`ADMIN_PASSWORD`, default `mamd`).
- Extra admin IDs can be added in Admin Panel → تنظیمات → ادمین‌ها.

## Database & backups

- SQLite by default; to move to PostgreSQL just change `DATABASE_URL`.
- `bot/utils/backup.py` provides DB backup/restore and CSV/JSON export (wired to ticket export in the admin panel).

## Notes

- The admin delivers products manually after approving a payment (as designed).
- The `ADMIN_PASSWORD` is temporary; rotate it in `.env` when needed.
