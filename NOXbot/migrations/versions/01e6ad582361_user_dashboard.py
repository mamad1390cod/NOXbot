"""user dashboard

Revision ID: 01e6ad582361
Revises: 665eb9a26744
Create Date: 2026-08-06 03:25:11.946789

Notes:
- Creates wishlist_items, transactions, badges, achievements tables.
- Adds wallet_balance and reward_points to users.
- Seeds the default achievement badges.
"""

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '01e6ad582361'
down_revision: Union[str, Sequence[str], None] = '665eb9a26744'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BADGES = [
    ("first_order", "اولین سفارش", "اولین خرید خود را انجام دادید", "🛒"),
    ("five_orders", "مشتری وفادار", "5 سفارش ثبت کردید", "⭐"),
    ("big_spender", "خریدار ویژه", "بیش از ۱ میلیون تومان خرید کردید", "💎"),
    ("member_30", "عضو یک‌ماهه", "یک ماه با ما بودید", "📅"),
    ("tournament_winner", "قهرمان", "در یک کاستوم برنده شدید", "🏆"),
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'wishlist_items',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('product_id', sa.String(), nullable=True),
        sa.Column('config_product_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['config_product_id'], ['config_products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'config_product_id', name='uq_wishlist_config'),
        sa.UniqueConstraint('user_id', 'product_id', name='uq_wishlist_product'),
    )
    op.create_index(op.f('ix_wishlist_items_user_id'), 'wishlist_items', ['user_id'])

    op.create_table(
        'transactions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('amount', sa.BigInteger(), nullable=False),
        sa.Column('balance_after', sa.BigInteger(), nullable=False),
        sa.Column('ref_id', sa.String(length=64), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_transactions_user_created', 'transactions', ['user_id', 'created_at'])
    op.create_index(op.f('ix_transactions_user_id'), 'transactions', ['user_id'])

    op.create_table(
        'badges',
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('icon', sa.String(length=20), nullable=False),
        sa.Column('id', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )

    op.create_table(
        'achievements',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('badge_key', sa.String(length=50), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['badge_key'], ['badges.key'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'badge_key', name='uq_achievement_user_badge'),
    )
    op.create_index('ix_achievements_user_id', 'achievements', ['user_id'])

    op.add_column('users', sa.Column('wallet_balance', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('reward_points', sa.Integer(), nullable=False, server_default='0'))

    # Seed default badges.
    conn = op.get_bind()
    for key, name, desc, icon in BADGES:
        conn.execute(
            sa.text(
                "INSERT INTO badges (id, key, name, description, icon) "
                "VALUES (:id, :key, :name, :desc, :icon)"
            ).bindparams(
                id=str(uuid.uuid4()), key=key, name=name, desc=desc, icon=icon,
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'reward_points')
    op.drop_column('users', 'wallet_balance')
    op.drop_index('ix_achievements_user_id', table_name='achievements')
    op.drop_table('achievements')
    op.drop_table('badges')
    op.drop_index(op.f('ix_transactions_user_id'), table_name='transactions')
    op.drop_index('ix_transactions_user_created', table_name='transactions')
    op.drop_table('transactions')
    op.drop_index(op.f('ix_wishlist_items_user_id'), table_name='wishlist_items')
    op.drop_table('wishlist_items')