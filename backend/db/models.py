"""
SQLAlchemy models for connection tracking and user data persistence.

Uses SQLAlchemy 2.0 async patterns with declarative base.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict

from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class User(Base):
    """
    User model for tracking WebSocket connections.

    Attributes:
        id: Unique identifier (UUID) for the user record
        session_id: WebSocket connection ID (unique)
        connected_at: Timestamp when the connection was established
        last_active_at: Timestamp of the last activity
        metadata_: JSON field for storing additional connection information
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    session_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    auth0_user_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    metadata_: Mapped[Dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )

    def __repr__(self) -> str:
        """Return string representation of User."""
        return (
            f"User(id={self.id}, session_id='{self.session_id}', "
            f"connected_at={self.connected_at}, last_active_at={self.last_active_at})"
        )


class UserAllocator(Base):
    """
    User allocator model for persisting allocator configurations.

    Attributes:
        id: Unique identifier (UUID) for the allocator
        auth0_user_id: Auth0 user ID (owner of the allocator)
        name: Display name for the allocator
        allocator_type: Type of allocator (manual, max_sharpe, min_volatility)
        config: JSON configuration for the allocator
        enabled: Whether the allocator is enabled for computation
        display_order: Order in which allocators are displayed
        created_at: Timestamp when the allocator was created
        updated_at: Timestamp when the allocator was last updated
    """

    __tablename__ = "user_allocators"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    auth0_user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    allocator_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    config: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        """Return string representation of UserAllocator."""
        return (
            f"UserAllocator(id={self.id}, auth0_user_id='{self.auth0_user_id}', "
            f"name='{self.name}', type='{self.allocator_type}')"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert allocator to dictionary for API responses."""
        return {
            "id": str(self.id),
            "type": self.allocator_type,
            "config": self.config,
            "enabled": self.enabled,
        }


class DashboardSettings(Base):
    """
    Dashboard settings model for persisting user preferences.

    Attributes:
        id: Unique identifier (UUID) for the settings record
        auth0_user_id: Auth0 user ID (unique per user)
        fit_start_date: Start date for fitting period
        fit_end_date: End date for fitting period
        test_end_date: End date for testing period
        include_dividends: Whether to include dividends in calculations
        created_at: Timestamp when the settings were created
        updated_at: Timestamp when the settings were last updated
    """

    __tablename__ = "dashboard_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    auth0_user_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    fit_start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    fit_end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    test_end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    include_dividends: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        """Return string representation of DashboardSettings."""
        return (
            f"DashboardSettings(id={self.id}, auth0_user_id='{self.auth0_user_id}')"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary for API responses."""
        return {
            "fit_start_date": self.fit_start_date.isoformat() if self.fit_start_date else None,
            "fit_end_date": self.fit_end_date.isoformat() if self.fit_end_date else None,
            "test_end_date": self.test_end_date.isoformat() if self.test_end_date else None,
            "include_dividends": self.include_dividends,
        }
