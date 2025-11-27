"""
CRUD operations for database models using SQLAlchemy 2.0 async patterns.

All operations use async sessions and modern select() statements.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import select, delete as sql_delete, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DashboardSettings, User, UserAllocator


async def create_user(
    session: AsyncSession, session_id: str, auth0_user_id: str | None = None
) -> User:
    """
    Create a new user with the given session ID.

    Args:
        session: SQLAlchemy async session
        session_id: WebSocket connection ID
        auth0_user_id: Optional Auth0 user identifier

    Returns:
        Created User instance

    Example:
        async with async_session() as session:
            user = await create_user(session, "ws-conn-123", "auth0|123456")
            await session.commit()
    """
    user = User(
        session_id=session_id,
        auth0_user_id=auth0_user_id,
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


async def get_users_by_auth0_id(
    session: AsyncSession, auth0_user_id: str
) -> List[User]:
    """
    Retrieve all users associated with a specific Auth0 user ID.

    Args:
        session: SQLAlchemy async session
        auth0_user_id: Auth0 user identifier

    Returns:
        List of User instances matching the Auth0 user ID

    Example:
        async with async_session() as session:
            users = await get_users_by_auth0_id(session, "auth0|123456")
            print(f"Found {len(users)} users for Auth0 ID")
    """
    stmt = select(User).where(User.auth0_user_id == auth0_user_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


# =============================================================================
# UserAllocator CRUD Operations
# =============================================================================


async def create_allocator(
    session: AsyncSession,
    auth0_user_id: str,
    name: str,
    allocator_type: str,
    config: Dict[str, Any],
    enabled: bool = False,
    allocator_id: uuid.UUID | None = None,
) -> UserAllocator:
    """
    Create a new allocator for a user.

    Args:
        session: SQLAlchemy async session
        auth0_user_id: Auth0 user identifier
        name: Display name for the allocator
        allocator_type: Type of allocator (manual, max_sharpe, min_volatility)
        config: JSON configuration for the allocator
        enabled: Whether the allocator is enabled
        allocator_id: Optional UUID (if provided by client)

    Returns:
        Created UserAllocator instance
    """
    # Get next display order
    stmt = select(UserAllocator).where(
        UserAllocator.auth0_user_id == auth0_user_id
    ).order_by(UserAllocator.display_order.desc())
    result = await session.execute(stmt)
    last_allocator = result.scalars().first()
    next_order = (last_allocator.display_order + 1) if last_allocator else 0

    allocator = UserAllocator(
        id=allocator_id or uuid.uuid4(),
        auth0_user_id=auth0_user_id,
        name=name,
        allocator_type=allocator_type,
        config=config,
        enabled=enabled,
        display_order=next_order,
    )
    session.add(allocator)
    await session.flush()
    return allocator


async def get_allocator_by_id(
    session: AsyncSession, allocator_id: uuid.UUID
) -> UserAllocator | None:
    """
    Retrieve an allocator by its ID.

    Args:
        session: SQLAlchemy async session
        allocator_id: Allocator UUID

    Returns:
        UserAllocator instance if found, None otherwise
    """
    stmt = select(UserAllocator).where(UserAllocator.id == allocator_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_allocators_by_user(
    session: AsyncSession, auth0_user_id: str
) -> List[UserAllocator]:
    """
    Retrieve all allocators for a user, ordered by display_order.

    Args:
        session: SQLAlchemy async session
        auth0_user_id: Auth0 user identifier

    Returns:
        List of UserAllocator instances
    """
    stmt = (
        select(UserAllocator)
        .where(UserAllocator.auth0_user_id == auth0_user_id)
        .order_by(UserAllocator.display_order)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_allocator(
    session: AsyncSession,
    allocator_id: uuid.UUID,
    auth0_user_id: str,
    config: Dict[str, Any] | None = None,
    enabled: bool | None = None,
    name: str | None = None,
) -> UserAllocator | None:
    """
    Update an allocator's configuration.

    Args:
        session: SQLAlchemy async session
        allocator_id: Allocator UUID
        auth0_user_id: Auth0 user ID (for authorization check)
        config: New configuration (optional)
        enabled: New enabled state (optional)
        name: New name (optional)

    Returns:
        Updated UserAllocator instance if found and owned by user, None otherwise
    """
    allocator = await get_allocator_by_id(session, allocator_id)
    if not allocator or allocator.auth0_user_id != auth0_user_id:
        return None

    if config is not None:
        allocator.config = config
    if enabled is not None:
        allocator.enabled = enabled
    if name is not None:
        allocator.name = name

    allocator.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return allocator


async def delete_allocator(
    session: AsyncSession, allocator_id: uuid.UUID, auth0_user_id: str
) -> bool:
    """
    Delete an allocator by its ID.

    Args:
        session: SQLAlchemy async session
        allocator_id: Allocator UUID
        auth0_user_id: Auth0 user ID (for authorization check)

    Returns:
        True if allocator was deleted, False if not found or unauthorized
    """
    stmt = sql_delete(UserAllocator).where(
        UserAllocator.id == allocator_id,
        UserAllocator.auth0_user_id == auth0_user_id,
    )
    result = await session.execute(stmt)
    await session.flush()
    return result.rowcount > 0


# =============================================================================
# DashboardSettings CRUD Operations
# =============================================================================


async def get_dashboard_settings(
    session: AsyncSession, auth0_user_id: str
) -> DashboardSettings | None:
    """
    Retrieve dashboard settings for a user.

    Args:
        session: SQLAlchemy async session
        auth0_user_id: Auth0 user identifier

    Returns:
        DashboardSettings instance if found, None otherwise
    """
    stmt = select(DashboardSettings).where(
        DashboardSettings.auth0_user_id == auth0_user_id
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_or_update_dashboard_settings(
    session: AsyncSession,
    auth0_user_id: str,
    fit_start_date: date | None = None,
    fit_end_date: date | None = None,
    test_end_date: date | None = None,
    include_dividends: bool | None = None,
) -> DashboardSettings:
    """
    Create or update dashboard settings for a user (upsert).

    Args:
        session: SQLAlchemy async session
        auth0_user_id: Auth0 user identifier
        fit_start_date: Start date for fitting period
        fit_end_date: End date for fitting period
        test_end_date: End date for testing period
        include_dividends: Whether to include dividends

    Returns:
        Created or updated DashboardSettings instance
    """
    settings = await get_dashboard_settings(session, auth0_user_id)

    if settings is None:
        # Create new settings
        settings = DashboardSettings(
            auth0_user_id=auth0_user_id,
            fit_start_date=fit_start_date,
            fit_end_date=fit_end_date,
            test_end_date=test_end_date,
            include_dividends=include_dividends if include_dividends is not None else True,
        )
        session.add(settings)
    else:
        # Update existing settings
        if fit_start_date is not None:
            settings.fit_start_date = fit_start_date
        if fit_end_date is not None:
            settings.fit_end_date = fit_end_date
        if test_end_date is not None:
            settings.test_end_date = test_end_date
        if include_dividends is not None:
            settings.include_dividends = include_dividends
        settings.updated_at = datetime.now(timezone.utc)

    await session.flush()
    return settings


async def get_user_dashboard(
    session: AsyncSession, auth0_user_id: str
) -> Dict[str, Any]:
    """
    Retrieve complete dashboard data for a user (allocators + settings).

    Args:
        session: SQLAlchemy async session
        auth0_user_id: Auth0 user identifier

    Returns:
        Dictionary with allocators list and settings
    """
    allocators = await get_allocators_by_user(session, auth0_user_id)
    settings = await get_dashboard_settings(session, auth0_user_id)

    return {
        "allocators": [a.to_dict() for a in allocators],
        "settings": settings.to_dict() if settings else {
            "fit_start_date": None,
            "fit_end_date": None,
            "test_end_date": None,
            "include_dividends": True,
        },
    }
