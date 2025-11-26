"""
Database engine and session configuration for SQLAlchemy 2.0 async.

This module provides the async engine and session factory for PostgreSQL.
DATABASE_URL environment variable is required.
"""

import logging
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import DATABASE_URL

logger = logging.getLogger(__name__)

# DATABASE_URL is required
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is required. "
        "Format: postgresql+asyncpg://user:password@host:port/dbname"
    )

if not DATABASE_URL.startswith("postgresql+asyncpg://"):
    raise RuntimeError(
        "DATABASE_URL must use asyncpg driver. "
        "Format: postgresql+asyncpg://user:password@host:port/dbname"
    )

logger.info("Using PostgreSQL database")

# Create async engine for PostgreSQL
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=5,  # Number of connections to maintain
    max_overflow=10,  # Additional connections when pool is exhausted
    pool_recycle=3600,  # Recycle connections after 1 hour
)

# Create async session factory
async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_async_session() -> AsyncSession:
    """
    Dependency function to get an async database session.

    Yields:
        AsyncSession instance
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize the database by creating all tables.
    Should be called on application startup.
    """
    from .models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Close the database engine.
    Should be called on application shutdown.
    """
    await engine.dispose()


def get_database_url() -> str:
    """Get the current database URL."""
    return DATABASE_URL
