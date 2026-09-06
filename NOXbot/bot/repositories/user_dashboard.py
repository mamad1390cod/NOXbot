"""User-dashboard repositories — wishlist, wallet ledger, achievements."""

from typing import Sequence

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models.user_dashboard import (
    Achievement,
    Badge,
    Transaction,
    TransactionType,
    WishlistItem,
)
from bot.repositories.base import BaseRepository


class WishlistRepository(BaseRepository[WishlistItem]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WishlistItem)

    async def list_for_user(self, user_id: str) -> Sequence[WishlistItem]:
        stmt = (
            select(WishlistItem)
            .where(WishlistItem.user_id == user_id)
            .options(
                selectinload(WishlistItem.product),
                selectinload(WishlistItem.config_product),
            )
            .order_by(desc(WishlistItem.created_at))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def add_item(self, user_id: str, product_id: str | None = None, config_id: str | None = None) -> WishlistItem:
        item = WishlistItem(user_id=user_id, product_id=product_id, config_product_id=config_id)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def find(self, user_id: str, product_id: str | None = None, config_id: str | None = None) -> WishlistItem | None:
        stmt = select(WishlistItem).where(WishlistItem.user_id == user_id)
        if product_id:
            stmt = stmt.where(WishlistItem.product_id == product_id)
        elif config_id:
            stmt = stmt.where(WishlistItem.config_product_id == config_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def remove(self, item_id: str) -> bool:
        item = await self.session.get(WishlistItem, item_id)
        if item:
            await self.session.delete(item)
            await self.session.flush()
            return True
        return False


class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Transaction)

    async def add(
        self, user_id: str, type_: TransactionType, amount: int, balance_after: int,
        ref_id: str | None = None, note: str | None = None,
        balance_before: int = 0, admin_id: str | None = None,
    ) -> Transaction:
        txn = Transaction(
            user_id=user_id, type=type_, amount=amount,
            balance_before=balance_before, balance_after=balance_after,
            ref_id=ref_id, note=note, admin_id=admin_id,
        )
        self.session.add(txn)
        await self.session.flush()
        await self.session.refresh(txn)
        return txn

    async def list_for_user(self, user_id: str, limit: int = 30) -> Sequence[Transaction]:
        stmt = (
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(desc(Transaction.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class AchievementRepository(BaseRepository[Achievement]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Achievement)

    async def earned_by_user(self, user_id: str) -> Sequence[Achievement]:
        stmt = (
            select(Achievement)
            .where(Achievement.user_id == user_id)
            .options(selectinload(Achievement.badge))
            .order_by(Achievement.unlocked_at)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def has_unlocked(self, user_id: str, badge_key: str) -> bool:
        return await self.exists(user_id=user_id, badge_key=badge_key)

    async def unlock(self, user_id: str, badge_key: str) -> Achievement | None:
        if await self.has_unlocked(user_id, badge_key):
            return None
        return await self.create(user_id=user_id, badge_key=badge_key)


class BadgeRepository(BaseRepository[Badge]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Badge)

    async def all_badges(self) -> Sequence[Badge]:
        stmt = select(Badge).order_by(Badge.key)
        result = await self.session.execute(stmt)
        return result.scalars().all()