"""add auth0_user_id to users table

Revision ID: 002
Revises: 001
Create Date: 2025-11-26 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add auth0_user_id column to users table."""
    # Add auth0_user_id column
    op.add_column(
        'users',
        sa.Column('auth0_user_id', sa.String(length=255), nullable=True)
    )

    # Create index on auth0_user_id for faster lookups
    op.create_index(
        op.f('ix_users_auth0_user_id'),
        'users',
        ['auth0_user_id'],
        unique=False
    )


def downgrade() -> None:
    """Remove auth0_user_id column from users table."""
    # Drop index first
    op.drop_index(op.f('ix_users_auth0_user_id'), table_name='users')

    # Drop column
    op.drop_column('users', 'auth0_user_id')
