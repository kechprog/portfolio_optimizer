"""
Example usage of the User database model for WebSocket connection tracking.

This demonstrates how to integrate the User model with your FastAPI WebSocket endpoint.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
import logging

from db import (
    init_db,
    close_db,
    async_session_maker,
    create_user,
    update_user_activity,
    delete_user,
    get_all_active_users,
)

logger = logging.getLogger(__name__)


# Application lifespan with database initialization
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup, clean up on shutdown."""
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized")

    yield

    logger.info("Closing database...")
    await close_db()
    logger.info("Database closed")


# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint with connection tracking.

    Demonstrates:
    1. Creating a user record on connection
    2. Updating activity on each message
    3. Cleaning up on disconnect
    """
    await websocket.accept()

    # Generate session ID from client info
    client_host = websocket.client.host if websocket.client else "unknown"
    client_port = websocket.client.port if websocket.client else "unknown"
    session_id = f"{client_host}:{client_port}"

    logger.info(f"Client connected: {session_id}")

    # Create user record for this connection
    async with async_session_maker() as session:
        user = await create_user(session, session_id)
        await session.commit()
        logger.info(f"Created user record: {user.id}")

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()

            # Update user activity timestamp
            async with async_session_maker() as session:
                user = await update_user_activity(session, session_id)
                await session.commit()
                if user:
                    logger.debug(f"Updated activity for {session_id}")

            # Process the message (your business logic here)
            await websocket.send_text(f"Echo: {data}")

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Error in WebSocket connection {session_id}: {e}")
    finally:
        # Clean up user record on disconnect
        async with async_session_maker() as session:
            deleted = await delete_user(session, session_id)
            await session.commit()
            if deleted:
                logger.info(f"Deleted user record for {session_id}")


@app.get("/active-connections")
async def get_active_connections():
    """
    API endpoint to get all active WebSocket connections.

    Returns:
        JSON response with count and list of active users
    """
    async with async_session_maker() as session:
        users = await get_all_active_users(session)

        return {
            "count": len(users),
            "connections": [
                {
                    "id": str(user.id),
                    "session_id": user.session_id,
                    "connected_at": user.connected_at.isoformat(),
                    "last_active_at": user.last_active_at.isoformat(),
                    "duration_seconds": (
                        user.last_active_at - user.connected_at
                    ).total_seconds(),
                }
                for user in users
            ],
        }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "example_usage:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
