"""Financial service — orchestrates the financial dashboard metrics."""

from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from bot.services.base import BaseService
from bot.database.uow import UnitOfWork


class FinancialService(BaseService):
    """Financial dashboard + report aggregation."""

    def __init__(self, uow: UnitOfWork) -> None:
        super().__init__(uow)

    async def dashboard(self, filters: dict[str, Any]) -> dict:
        """Compute every dashboard metric honoring ``filters``."""
        f = dict(filters or {})
        periods = await self.uow.finance.all_periods(f)
        revenue, paid_count = await self.uow.finance.revenue_and_count(f)
        avg = await self.uow.finance.avg_order_value(f)

        # Breakdowns (honor date filters for the paid window).
        by_product = await self.uow.finance.breakdown_by_product(f)
        by_category = await self.uow.finance.breakdown_by_category(f)
        by_config = await self.uow.finance.breakdown_by_config(f)
        by_tournament = await self.uow.finance.breakdown_by_tournament(f)

        top_customers = await self.uow.finance.top_customers(f, by="spend")
        active_customers = await self.uow.finance.top_customers(f, by="count")

        status_counts = await self.uow.finance.order_status_counts()
        pending_payments = await self.uow.finance.pending_payments()
        conversion = await self.uow.finance.conversion()
        total_orders = await self.uow.finance.total_orders()

        return {
            "periods": periods,
            "total_revenue": revenue,
            "paid_orders": paid_count,
            "avg_order_value": avg,
            "by_product": by_product,
            "by_category": by_category,
            "by_config": by_config,
            "by_tournament": by_tournament,
            "top_customers": top_customers,
            "active_customers": active_customers,
            "status_counts": status_counts,
            "pending_payments": pending_payments,
            "conversion": conversion,
            "total_orders": total_orders,
            "filters": f,
        }

    async def revenue_series(self, days: int = 30, filters: dict[str, Any] | None = None) -> list[dict]:
        """Per-day revenue series for charts (last ``days`` days)."""
        f = dict(filters or {})
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        start = today - timedelta(days=days - 1)
        result = []
        for i in range(days):
            day = start + timedelta(days=i)
            f["date_from"] = day
            f["date_to"] = day + timedelta(days=1)
            rev, cnt = await self.uow.finance.revenue_and_count(f)
            result.append({"date": day.strftime("%Y-%m-%d"), "revenue": rev, "orders": cnt})
        return result

    async def export_data(self, filters: dict[str, Any]) -> dict:
        """Full data bundle for report generators."""
        return await self.dashboard(filters)