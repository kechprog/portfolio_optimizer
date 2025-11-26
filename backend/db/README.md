# Database Module - User Connection Tracking

This module provides SQLAlchemy 2.0 async database operations for tracking WebSocket user connections in the Portfolio Optimizer application.

## Overview

The module consists of:
- **models.py**: SQLAlchemy declarative models (Base, User)
- **crud.py**: Async CRUD operations for User model
- **engine.py**: Database engine, session factory, and initialization utilities

## Models

### User Model

Tracks WebSocket connections with the following fields:

```python
class User:
    id: UUID                    # Primary key (auto-generated)
    session_id: str            # Unique WebSocket connection ID
    connected_at: datetime     # When connection was established (UTC)
    last_active_at: datetime   # Last activity timestamp (UTC)
    metadata_: dict | None     # Additional connection info (JSON)
```

## CRUD Operations

All CRUD operations use SQLAlchemy 2.0 async patterns with `select()` statements.

### create_user(session, session_id)
Creates a new user record for a WebSocket connection.

```python
from db import async_session_maker, create_user

async with async_session_maker() as session:
    user = await create_user(session, "ws-conn-12345")
    await session.commit()
    print(f"Created user: {user.id}")
```

### get_user_by_session_id(session, session_id)
Retrieves a user by their session ID.

```python
from db import async_session_maker, get_user_by_session_id

async with async_session_maker() as session:
    user = await get_user_by_session_id(session, "ws-conn-12345")
    if user:
        print(f"User last active: {user.last_active_at}")
```

### update_user_activity(session, session_id)
Updates the last_active_at timestamp for a user.

```python
from db import async_session_maker, update_user_activity

async with async_session_maker() as session:
    user = await update_user_activity(session, "ws-conn-12345")
    if user:
        await session.commit()
        print(f"Updated activity: {user.last_active_at}")
```

### delete_user(session, session_id)
Deletes a user record.

```python
from db import async_session_maker, delete_user

async with async_session_maker() as session:
    deleted = await delete_user(session, "ws-conn-12345")
    if deleted:
        await session.commit()
        print("User deleted successfully")
```

### get_all_active_users(session)
Retrieves all active users, ordered by connection time (newest first).

```python
from db import async_session_maker, get_all_active_users

async with async_session_maker() as session:
    users = await get_all_active_users(session)
    print(f"Active connections: {len(users)}")
    for user in users:
        print(f"  - {user.session_id} (connected: {user.connected_at})")
```

## Database Setup

### Initialize Database

Call `init_db()` on application startup to create tables:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from db import init_db, close_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()

app = FastAPI(lifespan=lifespan)
```

### Using with FastAPI Dependency Injection

```python
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from db import get_async_session, get_all_active_users

app = FastAPI()

@app.get("/active-users")
async def list_active_users(session: AsyncSession = Depends(get_async_session)):
    users = await get_all_active_users(session)
    return {
        "count": len(users),
        "users": [
            {
                "id": str(user.id),
                "session_id": user.session_id,
                "connected_at": user.connected_at.isoformat(),
                "last_active_at": user.last_active_at.isoformat(),
            }
            for user in users
        ]
    }
```

## WebSocket Integration Example

Track connections in your WebSocket endpoint:

```python
from fastapi import WebSocket
from db import async_session_maker, create_user, update_user_activity, delete_user

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Create session ID from client info
    client_id = f"{websocket.client.host}:{websocket.client.port}"

    # Track connection
    async with async_session_maker() as session:
        user = await create_user(session, client_id)
        await session.commit()

    try:
        while True:
            data = await websocket.receive_text()

            # Update activity on each message
            async with async_session_maker() as session:
                await update_user_activity(session, client_id)
                await session.commit()

            # Process message...

    finally:
        # Clean up on disconnect
        async with async_session_maker() as session:
            await delete_user(session, client_id)
            await session.commit()
```

## Configuration

Database configuration is read from `config.py`:
- `DATABASE_PATH`: Path to SQLite database file
- Database URL: `sqlite+aiosqlite:///{DATABASE_PATH}`

## Dependencies

Required packages (see requirements.txt):
- `sqlalchemy[asyncio]>=2.0.0`
- `aiosqlite>=0.19.0`

## Notes

- All datetime fields use UTC timezone
- `metadata_` uses underscore suffix to avoid conflict with SQLAlchemy's `metadata`
- Sessions use `expire_on_commit=False` for better performance
- Manual flush/commit control with `autoflush=False` and `autocommit=False`
