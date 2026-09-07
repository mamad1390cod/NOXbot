"""Test script to debug custom categories issue."""
import asyncio
import sys
sys.path.insert(0, '.')

from bot.database.uow import UnitOfWorkFactory
from bot.services.custom import CustomService


async def test_get_active_categories():
    """Test if get_active_categories returns categories."""
    factory = UnitOfWorkFactory()
    
    async with factory() as uow:
        cs = CustomService(uow)
        cats = await cs.get_active_categories()
        
        print(f"Found {len(cats)} active categories:")
        for cat in cats:
            print(f"  - {cat.id}: {cat.name} (is_active={cat.is_active})")
        
        if not cats:
            print("\n⚠️  No active categories found!")
            print("Checking all categories (including inactive)...")
            
            # Try to get all categories
            from bot.models.custom import CustomCategory
            from sqlalchemy import select
            
            stmt = select(CustomCategory)
            result = await uow.session.execute(stmt)
            all_cats = result.scalars().all()
            
            print(f"\nFound {len(all_cats)} total categories:")
            for cat in all_cats:
                print(f"  - {cat.id}: {cat.name} (is_active={cat.is_active})")


if __name__ == "__main__":
    asyncio.run(test_get_active_categories())
