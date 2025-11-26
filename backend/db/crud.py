"""
CRUD operations for User model using SQLAlchemy 2.0 async patterns.

All operations use async sessions and modern select() statements.
"""

from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User


async def create_user(session: AsyncSession, session_id: str) -> User:
    """
    Create a new user with the given session ID.

    Args:
        session: SQLAlchemy async session
        session_id: WebSocket connection ID

    Returns:
        Created User instance

    Example:
        async with async_session() as session:
            user = await create_user(session, "ws-conn-123")
            await session.commit()
    """
    user = User(
        session_id=session_id,
        connected_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
    )
    session.add(user)
    await session.flush()  # Flush to generate the UUID
    return user


async def get_user_by_session_id(
    session: AsyncSession, session_id: str
) -> User | None:
    """
    Retrieve a user by their session ID.

    Args:
        session: SQLAlchemy async session
        session_id: WebSocket connection ID

    Returns:
        User instance if found, None otherwise

    Example:
        async with async_session() as session:
            user = await get_user_by_session_id(session, "ws-conn-123")
            if user:
                print(f"Found user: {user.id}")
    """
    stmt = select(User).where(User.session_id == session_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_user_activity(
    session: AsyncSession, session_id: str
) -> User | None:
    """
    Update the last_active_at timestamp for a user.

    Args:
        session: SQLAlchemy async session
        session_id: WebSocket connection ID

    Returns:
        Updated User instance if found, None otherwise

    Example:
        async with async_session() as session:
            user = await update_user_activity(session, "ws-conn-123")
            if user:
                await session.commit()
    """
    user = await get_user_by_session_id(session, session_id)
    if user:
        user.last_active_at = datetime.now(timezone.utc)
        await session.flush()
    return user


async def delete_user(session: AsyncSession, session_id: str) -> bool:
    """
    Delete a user by their session ID.

    Args:
        session: SQLAlchemy async session
        session_id: WebSocket connection ID

    Returns:
        True if user was deleted, False if not found

    Example:
        async with async_session() as session:
            deleted = await delete_user(session, "ws-conn-123")
            if deleted:
                await session.commit()
                print("User deleted")
    """
    stmt = sql_delete(User).where(User.session_id == session_id)
    result = await session.execute(stmt)
    await session.flush()
    return result.rowcount > 0


async def get_all_active_users(session: AsyncSession) -> List[User]:
    """
    Retrieve all active users.

    Args:
        session: SQLAlchemy async session

    Returns:
        List of all User instances, ordered by connected_at (newest first)

    Example:
        async with async_session() as session:
            users = await get_all_active_users(session)
            print(f"Active users: {len(users)}")
            for user in users:
                print(f"  - {user.session_id} (connected at {user.connected_at})")
    """
    stmt = select(User).order_by(User.connected_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())
