"""add customer info to user

Revision ID: add_customer_info
Revises: 79692c7
Create Date: 2026-09-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_customer_info'
down_revision = '79692c7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add customer info fields to users table
    op.add_column('users', sa.Column('email', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('password', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('customer_name', sa.String(255), nullable=True))


def downgrade() -> None:
    # Remove customer info fields from users table
    op.drop_column('users', 'customer_name')
    op.drop_column('users', 'password')
    op.drop_column('users', 'email')
