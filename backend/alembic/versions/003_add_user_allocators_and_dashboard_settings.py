"""add user_allocators and dashboard_settings tables

Revision ID: 003
Revises: 002
Create Date: 2025-11-26 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user_allocators and dashboard_settings tables."""
    # Create user_allocators table
    op.create_table(
        'user_allocators',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('auth0_user_id', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('allocator_type', sa.String(length=50), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create index on auth0_user_id for faster lookups
    op.create_index(
        op.f('ix_user_allocators_auth0_user_id'),
        'user_allocators',
        ['auth0_user_id'],
        unique=False
    )

    # Create dashboard_settings table
    op.create_table(
        'dashboard_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('auth0_user_id', sa.String(length=255), nullable=False),
        sa.Column('fit_start_date', sa.Date(), nullable=True),
        sa.Column('fit_end_date', sa.Date(), nullable=True),
        sa.Column('test_end_date', sa.Date(), nullable=True),
        sa.Column('include_dividends', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('auth0_user_id'),
    )

    # Create index on auth0_user_id
    op.create_index(
        op.f('ix_dashboard_settings_auth0_user_id'),
        'dashboard_settings',
        ['auth0_user_id'],
        unique=True
    )


def downgrade() -> None:
    """Drop user_allocators and dashboard_settings tables."""
    op.drop_index(op.f('ix_dashboard_settings_auth0_user_id'), table_name='dashboard_settings')
    op.drop_table('dashboard_settings')
    op.drop_index(op.f('ix_user_allocators_auth0_user_id'), table_name='user_allocators')
    op.drop_table('user_allocators')
