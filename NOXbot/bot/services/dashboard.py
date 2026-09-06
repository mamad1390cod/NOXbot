"""User Dashboard service — aggregates all profile data for the user."""

from typing import Sequence

from bot.models.custom import CustomRegistration
from bot.models.order import Order, OrderStatus
from bot.models.user import User
from bot.models.ticket import TicketStatus
from bot.models.user_dashboard import TransactionType
from bot.services.base import BaseService
from bot.database.uow import UnitOfWork
from bot.models.ticket import TicketStatus

ACTIVE_STATUSES = [
    OrderStatus.WAITING_PAYMENT,
    OrderStatus.PAYMENT_UPLOADED,
    OrderStatus.PAYMENT_REVIEWING,
    OrderStatus.APPROVED,
    OrderStatus.PREPARING,
]
COMPLETED_STATUSES = [OrderStatus.COMPLETED, OrderStatus.DELIVERED]
CANCELLED_STATUSES = [OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.REFUNDED]


class UserDashboardService(BaseService):
    """Aggregates everything shown in the user's 'My Account' section."""

    def __init__(self, uow: UnitOfWork) -> None:
        super().__init__(uow)

    # --- Overview --------------------------------------------------------- #
    async def overview(self, user: User) -> dict:
        orders = await self.uow.orders.get_by_user(user.id, limit=100)
        paid = [o for o in orders if o.is_paid]
        tickets = await self.uow.tickets.get_by_user(user.id, limit=100)
        regs = await self.uow.custom_registrations.get_by_user(user.id)
        wishlist = await self.uow.wishlist.list_for_user(user.id)
        return {
            "user": user,
            "total_orders": len(orders),
            "active_orders": len([o for o in orders if o.status in ACTIVE_STATUSES]),
            "completed_orders": len([o for o in orders if o.status in COMPLETED_STATUSES]),
            "cancelled_orders": len([o for o in orders if o.status in CANCELLED_STATUSES]),
            "open_tickets": len([t for t in tickets if t.status.value != "closed"]),
            "tournament_count": len(regs),
            "wishlist_count": len(wishlist),
            "wallet_balance": user.wallet_balance or 0,
            "reward_points": user.reward_points or 0,
            "total_spent": user.total_spent or 0,
        }

    # --- Profile / referral ----------------------------------------------- #
    async def profile_info(self, user: User) -> dict:
        return {
            "username": user.username,
            "telegram_id": user.telegram_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "registered_at": user.created_at,
            "referral_code": user.referral_code,
            "referred_by": user.referred_by,
        }

    async def edit_profile(self, user: User, **fields) -> User:
        updates = {}
        if "first_name" in fields and fields["first_name"]:
            updates["first_name"] = fields["first_name"]
        if "last_name" in fields and fields["last_name"]:
            updates["last_name"] = fields["last_name"]
        if updates:
            await self.uow.users.update(user.id, **updates)
            await self.uow.flush()
        return user

    # --- Histories -------------------------------------------------------- #
    async def order_history(self, user: User, statuses: list[OrderStatus] | None = None,
                            limit: int = 20) -> Sequence[Order]:
        orders = await self.uow.orders.get_by_user(user.id, limit=limit)
        if statuses:
            orders = [o for o in orders if o.status in statuses]
        return orders

    async def current_orders(self, user: User) -> Sequence[Order]:
        return await self.order_history(user, ACTIVE_STATUSES)

    async def completed_orders(self, user: User) -> Sequence[Order]:
        return await self.order_history(user, COMPLETED_STATUSES)

    async def cancelled_orders(self, user: User) -> Sequence[Order]:
        return await self.order_history(user, CANCELLED_STATUSES)

    async def payment_history(self, user: User, limit: int = 20):
        return await self.uow.payments.get_by_user(user.id, limit=limit)

    async def ticket_history(self, user: User, limit: int = 20):
        return await self.uow.tickets.get_by_user(user.id, limit=limit)

    async def tournament_registrations(self, user: User) -> Sequence[CustomRegistration]:
        return await self.uow.custom_registrations.get_by_user(user.id)

    async def tournament_results(self, user: User) -> list[dict]:
        regs = await self.tournament_registrations(user)
        results = []
        for r in regs:
            custom = r.custom
            if not custom:
                continue
            results.append({
                "custom_id": custom.id,
                "title": custom.title,
                "status": custom.status.value,
                "winner": custom.winner_id == user.id,
                "result": "برنده" if custom.winner_id == user.id else ("شرکت‌کننده" if custom.status.value == "completed" else custom.status.value),
            })
        return results

    # --- Purchases / downloads / receipts -------------------------------- #
    async def purchased_products(self, user: User) -> list[dict]:
        orders = await self.uow.orders.get_by_user(user.id, limit=100)
        items = []
        seen = set()
        for o in orders:
            if not o.is_paid:
                continue
            for it in o.items:
                if it.product_id and it.product_id not in seen:
                    seen.add(it.product_id)
                    items.append({"id": it.product_id, "title": it.product_title,
                                  "price": it.total_price, "order": o.order_number})
        return items

    async def purchased_configs(self, user: User) -> list[dict]:
        orders = await self.uow.orders.get_by_user(user.id, limit=100)
        items = []
        seen = set()
        for o in orders:
            if not o.is_paid:
                continue
            for it in o.items:
                if it.config_product_id and it.config_product_id not in seen:
                    seen.add(it.config_product_id)
                    items.append({"id": it.config_product_id, "title": it.product_title,
                                  "price": it.total_price, "order": o.order_number})
        return items

    async def downloads(self, user: User) -> list[dict]:
        """Delivered account data / config links the user can download."""
        orders = await self.uow.orders.get_by_user(user.id, limit=100)
        out = []
        for o in orders:
            if not o.is_paid:
                continue
            for it in o.items:
                if it.delivered_data:
                    out.append({"title": it.product_title, "data": it.delivered_data,
                                "order": o.order_number})
        return out

    async def receipts(self, user: User) -> list[dict]:
        payments = await self.uow.payments.get_by_user(user.id, limit=50)
        return [{"id": p.id, "amount": p.amount, "status": p.status.value,
                 "receipt_url": p.receipt_url, "created_at": p.created_at}
                for p in payments if p.receipt_url]

    # --- Wishlist --------------------------------------------------------- #
    async def list_wishlist(self, user: User):
        return await self.uow.wishlist.list_for_user(user.id)

    async def add_wishlist(self, user: User, product_id: str | None = None, config_id: str | None = None):
        existing = await self.uow.wishlist.find(user.id, product_id, config_id)
        if existing:
            return existing
        return await self.uow.wishlist.add_item(user.id, product_id, config_id)

    async def remove_wishlist(self, item_id: str) -> bool:
        return await self.uow.wishlist.remove(item_id)

    # --- Coupons ---------------------------------------------------------- #
    async def my_coupons(self, user: User) -> list[str]:
        orders = await self.uow.orders.get_by_user(user.id, limit=100)
        return [o.coupon_code for o in orders if o.coupon_code]

    # --- Wallet ----------------------------------------------------------- #
    async def wallet_ledger(self, user: User, limit: int = 30):
        return await self.uow.transactions.list_for_user(user.id, limit)

    async def credit_wallet(self, user: User, amount: int, note: str = "", ref_id: str | None = None) -> User:
        user.wallet_balance = (user.wallet_balance or 0) + amount
        await self.uow.transactions.add(user.id, TransactionType.DEPOSIT, amount,
                                        user.wallet_balance, ref_id, note)
        await self.uow.flush()
        return user

    async def spend_wallet(self, user: User, amount: int, note: str = "", ref_id: str | None = None) -> bool:
        if (user.wallet_balance or 0) < amount:
            return False
        user.wallet_balance -= amount
        await self.uow.transactions.add(user.id, TransactionType.SPEND, -amount,
                                        user.wallet_balance, ref_id, note)
        await self.uow.flush()
        return True

    async def reward(self, user: User, points: int, note: str = "") -> User:
        user.reward_points = (user.reward_points or 0) + points
        await self.uow.transactions.add(user.id, TransactionType.REWARD, points,
                                        user.wallet_balance, None, note or "امتیاز")
        await self.uow.flush()
        return user

    # --- Achievements ----------------------------------------------------- #
    async def earned_badges(self, user: User):
        return await self.uow.achievements.earned_by_user(user.id)

    async def all_badges(self):
        return await self.uow.badges.all_badges()

    async def unlock_badge(self, user: User, badge_key: str) -> bool:
        unlocked = await self.uow.achievements.unlock(user.id, badge_key)
        await self.uow.flush()
        return unlocked is not None

    async def check_auto_badges(self, user: User) -> list[str]:
        """Unlock badges earned by order/spend thresholds; returns new badge keys."""
        earned = {a.badge_key for a in await self.earned_badges(user)}
        orders = await self.uow.orders.get_by_user(user.id, limit=100)
        paid = [o for o in orders if o.is_paid]
        new = []
        candidates = []
        if paid:
            candidates.append("first_order")
        if len(paid) >= 5:
            candidates.append("five_orders")
        if (user.total_spent or 0) >= 1_000_000:
            candidates.append("big_spender")
        from datetime import datetime, timezone
        if user.created_at:
            created = user.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - created).days >= 30:
                candidates.append("member_30")
        for key in candidates:
            if key not in earned and await self.unlock_badge(user, key):
                new.append(key)
        return new

    # --- Reorder ---------------------------------------------------------- #
    async def reorder(self, user: User, order_id: str) -> int:
        """Re-add a past order's items to the cart. Returns number of items added."""
        order = await self.uow.orders.get_with_items(order_id)
        if not order or order.user_id != user.id:
            return 0
        cart = await self.uow.carts.get_or_create(user.id)
        count = 0
        for it in order.items:
            if it.product_id:
                product = it.product
                if product and product.is_visible and product.is_in_stock:
                    await self.uow.carts.add_item(cart.id, product_id=it.product_id, quantity=it.quantity)
                    count += 1
            elif it.config_product_id:
                cfg = it.config_product
                if cfg and cfg.is_visible and cfg.is_in_stock:
                    await self.uow.carts.add_item(cart.id, config_product_id=it.config_product_id, quantity=it.quantity)
                    count += 1
        await self.uow.flush()
        return count