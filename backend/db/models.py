"""
SQLAlchemy models for connection tracking.

Uses SQLAlchemy 2.0 async patterns with declarative base.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import JSON, DateTime, String, Uuid
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
