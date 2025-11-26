"""
Database models and CRUD operations for Portfolio Optimizer.

Requires PostgreSQL via asyncpg. Set DATABASE_URL environment variable.
Format: postgresql+asyncpg://user:password@host:port/dbname
"""

from .models import Base, User
from .crud import (
    create_user,
    get_user_by_session_id,
    update_user_activity,
    delete_user,
    get_all_active_users,
)
from .engine import (
    engine,
    async_session_maker,
    get_async_session,
    init_db,
    close_db,
    get_database_url,
)

__all__ = [
    # Models
    "Base",
    "User",
    # CRUD operations
    "create_user",
    "get_user_by_session_id",
    "update_user_activity",
    "delete_user",
    "get_all_active_users",
    # Database engine and session
    "engine",
    "async_session_maker",
    "get_async_session",
    # Lifecycle functions
    "init_db",
    "close_db",
    # Utility
    "get_database_url",
]
