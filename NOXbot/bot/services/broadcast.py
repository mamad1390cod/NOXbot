"""Smart broadcast service — audience targeting, sending, scheduling, stats."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import get_settings
from bot.models.broadcast import Broadcast, BroadcastStatus, MediaType
from bot.models.user import User
from bot.services.base import BaseService
from bot.database.uow import UnitOfWork

logger = logging.getLogger(__name__)

DEFAULT_PREFS = {"promos": "on", "orders": "on", "system": "on"}


class BroadcastService(BaseService):
    """Create, target, send, schedule and report broadcasts."""

    def __init__(self, uow: UnitOfWork, bot: Bot | None = None) -> None:
        super().__init__(uow)
        self.bot = bot

    # --- Audience resolution ---------------------------------------------- #
    async def resolve_users(self, audience: dict) -> list[User]:
        """Return the list of User objects matching the audience config."""
        groups = audience.get("groups", []) or []
        users: dict[int, User] = {}
        owner_id = get_settings().admin_id

        def _add(u: User | None):
            if u and not u.is_banned and u.telegram_id != owner_id:
                users[u.id] = u

        if "all" in groups:
            all_users = await self.uow.users.get_all(limit=10000)
            for u in all_users:
                _add(u)

        if "active" in groups:
            now = datetime.now(timezone.utc)
            active = await self.uow.users.get_all(limit=10000)
            for u in active:
                if u.last_activity and (now - _aware(u.last_activity)).days <= 7:
                    _add(u)

        if "inactive" in groups:
            now = datetime.now(timezone.utc)
            inactive = await self.uow.users.get_all(limit=10000)
            for u in inactive:
                if not u.last_activity or (now - _aware(u.last_activity)).days > 7:
                    _add(u)

        if "vip" in groups:
            # VIP: top spenders (total_spent >= 500_000) for this demo.
            vips = await self.uow.users.get_all(limit=10000)
            for u in vips:
                if (u.total_spent or 0) >= 500_000:
                    _add(u)

        if "customers" in groups:
            orders = await self._orders_all()
            buyer_ids = {o.user_id for o in orders if o.is_paid}
            for uid in buyer_ids:
                _add(await self.uow.users.get(uid))

        if "tournament_participants" in groups:
            from bot.models.custom import CustomRegistration
            from sqlalchemy import select
            result = await self.uow.session.execute(select(CustomRegistration.user_id))
            for (uid,) in result.all():
                _add(await self.uow.users.get(uid))

        if "product_buyers" in groups:
            from bot.models.order import OrderItem
            from sqlalchemy import select
            result = await self.uow.session.execute(
                select(OrderItem.order_id).where(OrderItem.product_id.isnot(None))
            )
            order_ids = {r[0] for r in result.all()}
            orders = await self.uow.orders.get_all(limit=5000)
            for o in orders:
                if o.id in order_ids and o.is_paid:
                    _add(await self.uow.users.get(o.user_id))

        if "config_buyers" in groups:
            from bot.models.order import OrderItem
            from sqlalchemy import select
            result = await self.uow.session.execute(
                select(OrderItem.order_id).where(OrderItem.config_product_id.isnot(None))
            )
            order_ids = {r[0] for r in result.all()}
            orders = await self.uow.orders.get_all(limit=5000)
            for o in orders:
                if o.id in order_ids and o.is_paid:
                    _add(await self.uow.users.get(o.user_id))

        # Roles
        roles = audience.get("roles") or []
        if roles:
            from bot.models.user import UserRole
            for role_name in roles:
                try:
                    role = UserRole(role_name)
                except ValueError:
                    continue
                if role == UserRole.ADMIN:
                    from bot.services.rbac import RbacService
                    profiles = await RbacService(self.uow).list_admins(limit=500)
                    for p in profiles:
                        _add(p.user)
                elif role == UserRole.USER:
                    for u in await self.uow.users.get_all(limit=10000):
                        if u.role == UserRole.USER and not u.is_banned:
                            _add(u)

        # Category
        category = audience.get("category_id")
        if category:
            from sqlalchemy import select, func
            from bot.models.order import OrderItem
            result = await self.uow.session.execute(
                select(OrderItem.order_id).join(OrderItem.product).where(
                    OrderItem.product.has(category_id=category)
                )
            )
            order_ids = {r[0] for r in result.all()}
            orders = await self.uow.orders.get_all(limit=5000)
            for o in orders:
                if o.id in order_ids and o.is_paid:
                    _add(await self.uow.users.get(o.user_id))

        # Date range
        if audience.get("date_from") or audience.get("date_to"):
            orders = await self.uow.orders.get_all(limit=5000)
            for o in orders:
                if o.created_at and o.is_paid:
                    if audience.get("date_from") and _aware(o.created_at) < _aware(audience["date_from"]):
                        continue
                    if audience.get("date_to") and _aware(o.created_at) > _aware(audience["date_to"]):
                        continue
                    _add(await self.uow.users.get(o.user_id))

        return list(users.values())

    async def _orders_all(self):
        return await self.uow.orders.get_all(limit=5000)

    # --- Preferences ------------------------------------------------------- #
    async def get_prefs(self, user: User) -> dict:
        try:
            prefs = json.loads(user.notification_preferences) if user.notification_preferences else {}
        except ValueError:
            prefs = {}
        merged = dict(DEFAULT_PREFS)
        merged.update(prefs)
        return merged

    async def set_pref(self, user: User, category: str, enabled: bool) -> None:
        prefs = await self.get_prefs(user)
        prefs[category] = "on" if enabled else "off"
        user.notification_preferences = json.dumps(prefs)
        await self.uow.flush()

    async def wants(self, user: User, category: str) -> bool:
        prefs = await self.get_prefs(user)
        return prefs.get(category, "on") == "on"

    # --- Send -------------------------------------------------------------- #
    async def send(self, b: Broadcast) -> dict:
        """Send a broadcast to its resolved audience. Returns delivery stats."""
        if not self.bot:
            raise RuntimeError("BroadcastService requires a bot to send")
        audience = json.loads(b.audience or "{}")
        users = await self.resolve_users(audience)
        b.total_target = len(users)
        b.status = BroadcastStatus.SENDING

        sent = failed = blocked = opted = 0
        fail_ids: list[str] = []
        block_ids: list[str] = []
        cat = b.notification_category or "promos"

        for u in users:
            if not await self.wants(u, cat):
                opted += 1
                continue
            try:
                ok = await self._send(u.telegram_id, b)
                if ok:
                    sent += 1
                else:
                    blocked += 1
                    block_ids.append(str(u.telegram_id))
            except Exception as e:
                failed += 1
                fail_ids.append(str(u.telegram_id))
                logger.debug("broadcast failed to %s: %s", u.telegram_id, e)

        b.sent_count = sent
        b.failed_count = failed
        b.blocked_count = blocked
        b.opted_out_count = opted
        b.failed_ids = json.dumps(fail_ids)
        b.blocked_ids = json.dumps(block_ids)
        b.status = BroadcastStatus.SENT
        await self.uow.flush()
        return sent

    async def _build_reply(self, b: Broadcast) -> InlineKeyboardMarkup | None:
        if not b.buttons:
            return None
        try:
            rows = json.loads(b.buttons)
        except (ValueError, TypeError):
            return None
        keyboard = []
        for row in rows:
            btns = []
            for item in row:
                text = item.get("text", "")
                url = item.get("url")
                if url:
                    btns.append(InlineButton(text=text, url=url))
                else:
                    btns.append(InlineButton(text=text, callback_data=item.get("callback_data", "noop")))
            if btns:
                keyboard.append(btns)
        return InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None

    async def _send(self, tg_id: int, b: Broadcast) -> bool:
        kb = await self._build_reply(b)
        mtype = b.media_type
        caption = b.caption or b.text or ""
        try:
            if mtype == MediaType.TEXT:
                await self.bot.send_message(tg_id, b.text or "", reply_markup=kb, parse_mode="HTML")
            elif mtype == MediaType.PHOTO:
                await self.bot.send_photo(tg_id, b.media_file_id, caption=caption, reply_markup=kb)
            elif mtype == MediaType.VIDEO:
                await self.bot.send_video(tg_id, b.media_file_id, caption=caption, reply_markup=kb)
            elif mtype == MediaType.DOCUMENT:
                await self.bot.send_document(tg_id, b.media_file_id, caption=caption, reply_markup=kb)
            elif mtype == MediaType.ANIMATION:
                await self.bot.send_animation(tg_id, b.media_file_id, caption=caption, reply_markup=kb)
            elif mtype == MediaType.VOICE:
                await self.bot.send_voice(tg_id, b.media_file_id, caption=caption, reply_markup=kb)
            elif mtype == MediaType.POLL:
                poll = json.loads(b.poll or "{}")
                await self.bot.send_poll(tg_id, poll.get("question", ""),
                                         options=poll.get("options", []), is_anonymous=poll.get("is_anonymous", True))
            return True
        except Exception:
            return False

    # --- Queue / schedule / lifecycle --------------------------------- ---- #
    async def schedule_due(self) -> int:
        """Send all due broadcasts; re-queue recurring ones. Returns count sent."""
        if not self.bot:
            return 0
        due = await self.uow.broadcasts.due()
        ran = 0
        for b in due:
            try:
                await self.send(b)
                ran += 1
                if b.interval_seconds:
                    # Recurring: reset schedule and pending.
                    b.scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=b.interval_seconds)
                    b.status = BroadcastStatus.PENDING
            except Exception as e:
                logger.exception("schedule_due broadcast %s failed: %s", b.id, e)
        await self.uow.flush()
        return ran

    async def pause(self, broadcast_id: str) -> Broadcast | None:
        return await self.uow.broadcasts.update(broadcast_id, status=BroadcastStatus.PAUSED)

    async def resume(self, broadcast_id: str, scheduled_at: datetime | None = None) -> Broadcast | None:
        return await self.uow.broadcasts.update(
            broadcast_id, status=BroadcastStatus.PENDING,
            scheduled_at=scheduled_at or datetime.now(timezone.utc),
        )

    async def cancel(self, broadcast_id: str) -> Broadcast | None:
        return await self.uow.broadcasts.update(broadcast_id, status=BroadcastStatus.CANCELLED)

    # --- Templates --------------------------------------------------------- #
    async def save_template(self, name: str, b: Broadcast, created_by_id: str | None = None):
        return await self.uow.broadcast_templates.create(
            name=name, media_type=b.media_type, media_file_id=b.media_file_id,
            text=b.text, caption=b.caption, buttons=b.buttons, created_by_id=created_by_id,
        )

    async def list_templates(self, limit: int = 50):
        return await self.uow.broadcast_templates.list_templates(limit)

    async def recent(self, limit: int = 20):
        return await self.uow.broadcasts.recent(limit)

    async def stats(self, b: Broadcast) -> dict:
        return {
            "total": b.total_target, "sent": b.sent_count, "failed": b.failed_count,
            "blocked": b.blocked_count, "opted_out": b.opted_out_count,
        }

    async def failed_report(self, b: Broadcast) -> tuple[list, list]:
        try:
            fail = json.loads(b.failed_ids or "[]")
        except ValueError:
            fail = []
        try:
            block = json.loads(b.blocked_ids or "[]")
        except ValueError:
            block = []
        return fail, block


def _aware(dt) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def InlineButton(text: str, url: str | None = None, callback_data: str | None = None):
    return InlineKeyboardButton(text=text, url=url, callback_data=callback_data)