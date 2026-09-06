#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/user/NOXbot/NOXbot')

import asyncio
from bot.database.session import get_session_factory
from sqlalchemy import text, inspect

async def run_migration():
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            # Check if columns exist
            conn = await session.connection()
            def check_columns(connection):
                inspector = inspect(connection)
                columns = [col['name'] for col in inspector.get_columns('users')]
                return columns
            
            columns = await conn.run_sync(check_columns)
            
            # Add columns if they don't exist
            if 'email' not in columns:
                await session.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255)"))
                print("  ✅ Added email column")
            
            if 'password' not in columns:
                await session.execute(text("ALTER TABLE users ADD COLUMN password VARCHAR(255)"))
                print("  ✅ Added password column")
            
            if 'customer_name' not in columns:
                await session.execute(text("ALTER TABLE users ADD COLUMN customer_name VARCHAR(255)"))
                print("  ✅ Added customer_name column")
            
            # Create order_deliveries table if it doesn't exist
            def check_order_deliveries(connection):
                inspector = inspect(connection)
                return 'order_deliveries' in inspector.get_table_names()
            
            table_exists = await conn.run_sync(check_order_deliveries)
            if not table_exists:
                await session.execute(text("""
                    CREATE TABLE order_deliveries (
                        id VARCHAR(36) PRIMARY KEY,
                        order_id VARCHAR(36) NOT NULL UNIQUE,
                        delivery_type VARCHAR(20) NOT NULL DEFAULT 'config_text',
                        config_text TEXT,
                        file_id VARCHAR(255),
                        file_name VARCHAR(255),
                        note TEXT,
                        status VARCHAR(20) NOT NULL DEFAULT 'draft',
                        delivered_at TIMESTAMP WITH TIME ZONE,
                        created_by_id VARCHAR(36),
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                        FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE SET NULL
                    )
                """))
                print("  ✅ Created order_deliveries table")
            
            await session.commit()
            print("✅ Migration completed successfully")
        except Exception as e:
            await session.rollback()
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_migration())
