"""create users table

Revision ID: 001
Revises:
Create Date: 2025-11-26 18:22:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create users table for tracking WebSocket connections."""
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('session_id', sa.String(length=255), nullable=False),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata_', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id'),
    )

    # Create index on session_id for faster lookups
    op.create_index(
        op.f('ix_users_session_id'),
        'users',
        ['session_id'],
        unique=False
    )


def downgrade() -> None:
    """Drop users table."""
    op.drop_index(op.f('ix_users_session_id'), table_name='users')
    op.drop_table('users')
