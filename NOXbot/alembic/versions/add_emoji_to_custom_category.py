"""add emoji to custom category

Revision ID: add_emoji_custom_cat
Revises: add_customer_info_to_user
Create Date: 2026-09-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_emoji_custom_cat'
down_revision = 'add_customer_info_to_user'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('custom_categories', sa.Column('emoji', sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column('custom_categories', 'emoji')
