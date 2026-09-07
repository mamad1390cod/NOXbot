"""Anti-abuse service — detection, auto-actions, and management."""

from datetime import datetime, timedelta, timezone
from typing import Sequence

from bot.models.abuse import (
    AbuseType,
    AutoActionType,
    Severity,
)
from bot.models.user import User
from bot.services.base import BaseService
from bot.database.uow import UnitOfWork

# Auto-action thresholds (violation counts within a window → action).
# Keyed by AbuseType.
THRESHOLDS: dict[AbuseType, tuple[tuple[int, AutoActionType, int], ...]] = {
    # (count, action, duration_seconds)
    AbuseType.FLOOD: ((3, AutoActionType.MUTE, 3600),),
    AbuseType.MESSAGE_FLOOD: ((5, AutoActionType.RATE_LIMIT, 1800),),
    AbuseType.DUPLICATE_ORDER: ((2, AutoActionType.TEMP_BAN, 86400),),
    AbuseType.DUPLICATE_PAYMENT: ((2, AutoActionType.TEMP_BAN, 86400),),
    AbuseType.FAKE_RECEIPT: ((1, AutoActionType.TEMP_BAN, 86400),),
    AbuseType.RECEIPT_REUSE: ((1, AutoActionType.TEMP_BAN, 604800),),
    AbuseType.MASS_REGISTRATION: ((5, AutoActionType.TEMP_BAN, 86400),),
    AbuseType.CALLBACK_MANIPULATION: ((3, AutoActionType.TEMP_BAN, 3600),),
    AbuseType.UNAUTHORIZED_ACCESS: ((3, AutoActionType.TEMP_BAN, 3600),),
    AbuseType.ADMIN_ABUSE: ((1, AutoActionType.TEMP_BAN, 86400),),
    AbuseType.SPAM: ((5, AutoActionType.MUTE, 7200),),
}

SEVERITY_BY_TYPE: dict[AbuseType, Severity] = {
    AbuseType.SPAM: Severity.LOW,
    AbuseType.FLOOD: Severity.MEDIUM,
    AbuseType.DUPLICATE_ORDER: Severity.MEDIUM,
    AbuseType.DUPLICATE_PAYMENT: Severity.MEDIUM,
    AbuseType.FAKE_RECEIPT: Severity.HIGH,
    AbuseType.RECEIPT_REUSE: Severity.HIGH,
    AbuseType.MASS_REGISTRATION: Severity.HIGH,
    AbuseType.CALLBACK_MANIPULATION: Severity.HIGH,
    AbuseType.UNAUTHORIZED_ACCESS: Severity.HIGH,
    AbuseType.ADMIN_ABUSE: Severity.CRITICAL,
    AbuseType.BRUTE_FORCE_LOGIN: Severity.HIGH,
    AbuseType.MESSAGE_FLOOD: Severity.MEDIUM,
    AbuseType.BOT_ATTACK: Severity.CRITICAL,
    AbuseType.SUSPICIOUS: Severity.MEDIUM,
}


class AntiAbuseService(BaseService):
    """Detect abuse, apply thresholds/auto-actions, alert the owner, and manage
    whitelist/blacklist."""

    def __init__(self, uow: UnitOfWork, notifier=None) -> None:
        super().__init__(uow)
        self.notifier = notifier  # NotificationService or None (tests)

    # --- Recording + evaluation ------------------------------------------- #
    async def record(
        self,
        type_: AbuseType,
        user: User | None = None,
        event_data: str | None = None,
        source: str | None = None,
        severity: Severity | None = None,
    ) -> None:
        sev = severity or SEVERITY_BY_TYPE.get(type_, Severity.MEDIUM)
        user_id = user.id if user else None
        await self.uow.abuse.add_event(
            user_id=user_id,
            type_=type_,
            severity=sev,
            event_data=event_data,
            source=source,
        )
        if user:
            user.violation_count = (user.violation_count or 0) + 1
        await self.uow.flush()
        await self._evaluate(type_, user, sev)
        if sev in (Severity.HIGH, Severity.CRITICAL):
            await self._alert_owner(sev, type_, user)

    async def _evaluate(self, type_: AbuseType, user: User | None, sev: Severity) -> None:
        """Apply a threshold action if the user crossed it."""
        if not user:
            return
        thresholds = THRESHOLDS.get(type_)
        if not thresholds:
            return
        window_min = 1440  # look back over the last 24h
        count = await self.uow.abuse.count_for_user(user.id, type_, window_min)
        applied = False
        for floor, action, duration in thresholds:
            if count >= floor:
                await self._apply(action, user, reason=f"{type_.value} x{count}")
                applied = True
                break
        if applied and sev == Severity.CRITICAL:
            # Harder response for critical evens: permanent ban.
            await self._apply(AutoActionType.PERM_BAN, user, reason=f"critical {type_.value}")

    async def _apply(self, action: AutoActionType, user: User, reason: str) -> None:
        await self.uow.abuse.add_action(
            user_id=user.id,
            action=action,
            reason=reason,
            duration_seconds=86400 if action != AutoActionType.PERM_BAN else None,
        )
        now = datetime.now(timezone.utc)
        if action == AutoActionType.MUTE:
            user.muted_until = now + timedelta(hours=1)
        elif action == AutoActionType.TEMP_BAN:
            user.abuse_suspended_until = now + timedelta(days=1)
        elif action == AutoActionType.PERM_BAN:
            user.is_banned = True
            user.ban_reason = reason
        await self.uow.flush()

    async def _alert_owner(self, sev: Severity, type_: AbuseType, user: User | None) -> None:
        if not self.notifier:
            return
        name = f"@{user.username}" if user and user.username else (user.telegram_id if user else "؟")
        await self.notifier.send_to_admins(
            f"🚨 <b>هشدار امنیتی</b>\n"
            f"شدت: {sev.value}\nنوع: {type_.value}\nکاربر: {name}"
        )

    # --- Specific detectors ------------------------------------------------ #
    async def fail_login(self, user: User | None) -> int:
        """Record a failed login attempt; return count. Locks after N fails."""
        await self.record(AbuseType.BRUTE_FORCE_LOGIN, user=user, source="login")
        count = 0
        if user:
            count = await self.uow.abuse.count_for_user(user.id, AbuseType.BRUTE_FORCE_LOGIN, 10)
        if count >= 5 and user:
            await self._apply(AutoActionType.RATE_LIMIT, user, "brute force login")
        return count

    # --- Whitelist / blacklist ---------------------------------------
    async def whitelist_user(self, telegram_id: int) -> User | None:
        user = await self.uow.users.get_by_telegram_id(telegram_id)
        if not user:
            return None
        user.whitelisted = True
        user.blacklisted = False
        await self.uow.flush()
        return user

    async def blacklist_user(self, telegram_id: int, reason: str | None = None) -> User | None:
        user = await self.uow.users.get_by_telegram_id(telegram_id)
        if not user:
            return None
        user.blacklisted = True
        user.whitelisted = False
        user.blacklist_reason = reason
        await self.uow.flush()
        return user

    async def unblacklist_user(self, telegram_id: int) -> User | None:
        user = await self.uow.users.get_by_telegram_id(telegram_id)
        if not user:
            return None
        user.blacklisted = False
        user.blacklist_reason = None
        await self.uow.flush()
        return user

    async def unban_user(self, telegram_id: int) -> User | None:
        user = await self.uow.users.get_by_telegram_id(telegram_id)
        if not user:
            return None
        user.is_banned = False
        user.abuse_suspended_until = None
        user.muted_until = None
        await self.uow.abuse.lift_active(user.id)
        await self.uow.flush()
        return user

    async def is_blocked(self, user: User) -> bool:
        """Check if the user is currently blocked by blacklist/suspension."""
        if user.blacklisted:
            return True
        if user.is_banned:
            return True
        if user.abuse_suspended_until and user.abuse_suspended_until > datetime.now(timezone.utc):
            return True
        return False

    async def is_muted(self, user: User) -> bool:
        if user.muted_until and user.muted_until > datetime.now(timezone.utc):
            return True
        return False

    async def recent_events(self, user_id: str | None = None, limit: int = 50) -> Sequence:
        return await self.uow.abuse.recent_events(user_id, limit)

    async def violation_summary(self) -> dict:
        return await self.uow.abuse.violation_summary()

    async def security_report(self) -> dict:
        """Summary for the admin security report."""
        summary = await self.uow.abuse.violation_summary()
        from bot.models.abuse import AbuseType
        events = await self.uow.abuse.recent_events(limit=200)
        blocked: dict = await self._count_blocked()
        return {
            "violations": summary,
            "total_events": len(events),
            "blocked_users": blocked["blocked"],
            "suspended": blocked["suspended"],
            "whitelisted": blocked["whitelisted"],
            "blacklisted": blocked["blacklisted"],
            "recent": [{
                "type": e.type.value, "severity": e.severity.value,
                "user": e.user.username if e.user else None,
                "time": e.created_at.isoformat() if e.created_at else None,
            } for e in events[:50]],
        }

    async def _count_blocked(self) -> dict:
        from sqlalchemy import func, select
        from bot.models.user import User as _U

        async def _count(col, cond=True):
            return int(await self.uow.session.scalar(
                select(func.count()).select_from(_U).where(col == cond)
            ) or 0)

        suspended = int(await self.uow.session.scalar(
            select(func.count()).select_from(_U).where(_U.abuse_suspended_until != None)
        ) or 0)
        return {
            "blocked": await _count(_U.is_banned, True),
            "suspended": suspended,
            "whitelisted": await _count(_U.whitelisted, True),
            "blacklisted": await _count(_U.blacklisted, True),
        }