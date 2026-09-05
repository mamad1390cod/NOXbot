"""Financial repository — revenue and analytics aggregations.

All revenue/order counts window on the order's ``paid_at`` (approved) date.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.custom import Custom
from bot.models.order import Order, OrderItem, OrderStatus
from bot.models.payment import Payment, PaymentStatus
from bot.models.product import Product
from bot.models.user import User
from bot.repositories.base import BaseRepository

PAID_STATUSES = [
    OrderStatus.APPROVED,
    OrderStatus.PREPARING,
    OrderStatus.DELIVERED,
    OrderStatus.COMPLETED,
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FinanceRepository(BaseRepository[Order]):
    """Aggregated financial queries for the dashboard and reports."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Order)

    # --- Base paid-order window ------------------------------------------- #
    def _paid_stmt(self, f: dict[str, Any]) -> Any:
        """An Order select restricted to paid orders + optional filters."""
        stmt = select(Order).where(Order.status.in_(PAID_STATUSES))
        if f.get("date_from") and f.get("date_to"):
            stmt = stmt.where(Order.paid_at.between(f["date_from"], f["date_to"]))
        elif f.get("date_from"):
            stmt = stmt.where(Order.paid_at >= f["date_from"])
        elif f.get("date_to"):
            stmt = stmt.where(Order.paid_at <= f["date_to"])
        if f.get("user_id"):
            stmt = stmt.where(Order.user_id == f["user_id"])
        if f.get("admin_id"):
            stmt = stmt.where(
                (Order.approved_by_id == f["admin_id"]) | (Order.delivered_by_id == f["admin_id"])
            )
        return stmt

    async def revenue_and_count(self, f: dict[str, Any]) -> tuple[int, int]:
        """Return (revenue, paid_order_count) for the given filters."""
        base = self._paid_stmt(f).subquery()
        stmt = select(
            func.coalesce(func.sum(base.c.final_amount), 0),
            func.count(base.c.id),
        )
        result = await self.session.execute(stmt)
        row = result.one()
        return int(row[0]), int(row[1])

    async def _revenue_period(
        self, from_dt: datetime | None, to_dt: datetime | None, extra: dict[str, Any]
    ) -> tuple[int, int]:
        f = dict(extra)
        if from_dt:
            f["date_from"] = from_dt
        if to_dt:
            f["date_to"] = to_dt
        return await self.revenue_and_count(f)

    async def all_periods(self, f: dict[str, Any]) -> dict:
        """today/yesterday/week/month/year revenue on paid_at windows."""
        now = _utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_start = today_start - timedelta(days=6)
        month_start = today_start.replace(day=1)
        year_start = month_start.replace(month=1)

        today, today_n = await self._revenue_period(today_start, None, f)
        yesterday, y_n = await self._revenue_period(yesterday_start, today_start, f)
        week, week_n = await self._revenue_period(week_start, None, f)
        month, m_n = await self._revenue_period(month_start, None, f)
        year, yr_n = await self._revenue_period(year_start, None, f)

        return {
            "today": today, "today_orders": today_n,
            "yesterday": yesterday, "yesterday_orders": y_n,
            "week": week, "week_orders": week_n,
            "month": month, "month_orders": m_n,
            "year": year, "year_orders": yr_n,
        }

    async def avg_order_value(self, f: dict[str, Any]) -> int:
        revenue, count = await self.revenue_and_count(f)
        return revenue // count if count else 0

    # --- Breakdowns -------------------------------------------------------- #
    async def breakdown_by_product(self, f: dict[str, Any], limit: int = 50) -> list[dict]:
        base = self._paid_stmt(f).subquery()
        stmt = (
            select(
                OrderItem.product_title.label("label"),
                func.sum(OrderItem.quantity).label("units"),
                func.sum(OrderItem.total_price).label("revenue"),
            )
            .select_from(OrderItem)
            .join(base, OrderItem.order_id == base.c.id)
            .group_by(OrderItem.product_title)
            .order_by(desc("revenue"))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [dict(r._mapping) for r in result]

    async def breakdown_by_category(self, f: dict[str, Any], limit: int = 50) -> list[dict]:
        base = self._paid_stmt(f).subquery()
        stmt = (
            select(
                func.coalesce(Product.category_id, "بدون دسته").label("category_id"),
                func.sum(OrderItem.total_price).label("revenue"),
                func.count(OrderItem.id).label("count"),
            )
            .select_from(OrderItem)
            .join(base, OrderItem.order_id == base.c.id)
            .outerjoin(OrderItem.product)
            .group_by(Product.category_id)
            .order_by(desc("revenue"))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = [dict(r._mapping) for r in result]
        # Resolve category names.
        from bot.models.category import Category
        if rows:
            ids = {r["category_id"] for r in rows if r["category_id"] != "بدون دسته"}
            cats = {c.id: c for c in await self.session.scalars(select(Category).where(Category.id.in_(ids)))}
            for r in rows:
                if r["category_id"] in cats:
                    r["label"] = cats[r["category_id"]].name
                else:
                    r["label"] = r["category_id"]
        return rows

    async def breakdown_by_config(self, f: dict[str, Any], limit: int = 50) -> list[dict]:
        base = self._paid_stmt(f).subquery()
        stmt = (
            select(
                OrderItem.config_product_id.label("config_id"),
                func.sum(OrderItem.quantity).label("units"),
                func.sum(OrderItem.total_price).label("revenue"),
            )
            .select_from(OrderItem)
            .join(base, OrderItem.order_id == base.c.id)
            .where(OrderItem.config_product_id.isnot(None))
            .group_by(OrderItem.config_product_id)
            .order_by(desc("revenue"))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = [dict(r._mapping) for r in result]
        from bot.models.config_shop import ConfigProduct, ConfigProductStatus
        from bot.models.config_shop import ConfigProduct as CP
        ids = [r["config_id"] for r in rows]
        stmt2 = select(CP.id, CP.title).where(CP.id.in_(ids))
        result2 = await self.session.execute(stmt2)
        titles = dict(result2.all())
        for r in rows:
            r["label"] = titles.get(r["config_id"], r["config_id"])
        return rows

    async def breakdown_by_tournament(self, f: dict[str, Any], limit: int = 50) -> list[dict]:
        """Revenue from custom-registration payments (orders linked to a custom)."""
        from bot.models.custom import CustomRegistration
        stmt = (
            select(
                Custom.title.label("label"),
                func.count(Order.id).label("orders"),
                func.sum(Order.final_amount).label("revenue"),
            )
            .select_from(Order)
            .join(CustomRegistration, Order.custom_registration_id == CustomRegistration.id)
            .join(Custom, CustomRegistration.custom_id == Custom.id)
            .where(Order.status.in_(PAID_STATUSES))
            .group_by(Custom.id, Custom.title)
            .order_by(desc("revenue"))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [dict(r._mapping) for r in result]

    # --- Top customers ------------------------------------------------------ #
    async def top_customers(
        self, f: dict[str, Any], by: str = "spend", limit: int = 10
    ) -> list[dict]:
        order_expr = func.sum(Order.final_amount).label("spend")
        stmt = (
            select(
                User.id, User.username, User.telegram_id,
                func.count(Order.id).label("order_count"),
                func.sum(Order.final_amount).label("spend"),
            )
            .select_from(Order)
            .join(User, Order.user_id == User.id)
            .where(Order.status.in_(PAID_STATUSES))
            .group_by(User.id)
            .order_by(desc("spend" if by == "spend" else "order_count"))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [dict(r._mapping) for r in result]

    # --- Statuses / conversion --------------------------------------------- #
    async def order_status_counts(self) -> dict[str, int]:
        stmt = select(Order.status, func.count(Order.id)).group_by(Order.status)
        result = await self.session.execute(stmt)
        counts = {s.value: 0 for s in OrderStatus}
        for status, count in result.all():
            counts[status.value] = count
        return counts

    async def pending_payments(self) -> int:
        result = await self.session.scalar(
            select(func.count()).select_from(Payment).where(Payment.status == PaymentStatus.PENDING)
        )
        return int(result or 0)

    async def conversion(self) -> float:
        """Paid orders / distinct paid users (at least one non-rejected payment)."""
        loyal = (
            await self.session.scalar(
                select(func.count(func.distinct(Payment.user_id))).where(
                    Payment.status != PaymentStatus.REJECTED
                )
            )
            or 0
        )
        if not loyal:
            return 0.0
        revenue, paid_count = await self.revenue_and_count({})
        total_orders = await self.session.scalar(select(func.count()).select_from(Order)) or 0
        # Conversion rate = paid orders / distinct paying users.
        return paid_count / loyal if loyal else 0.0

    async def total_orders(self) -> int:
        return int(await self.session.scalar(select(func.count()).select_from(Order)) or 0)