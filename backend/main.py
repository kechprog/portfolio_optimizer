"""
FastAPI WebSocket server for Portfolio Optimizer.

Provides real-time communication between the React frontend and Python backend
for portfolio optimization computations.
"""

import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Union

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette import status

from auth import validate_token, AuthError, TokenPayload, is_auth_configured
from config import WS_HOST, WS_PORT, CORS_ORIGINS
from connection_state import ConnectionState
from db import init_db, close_db, get_database_url, async_session_maker
from db.crud import create_user, delete_user, update_user_activity, get_user_dashboard
from message_handlers import MESSAGE_HANDLERS
from schemas import (
    ComputePortfolio,
    CreateAllocator,
    DeleteAllocator,
    Error,
    ListAllocators,
    UpdateAllocator,
    UpdateDashboardSettings,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info(f"Starting Portfolio Optimizer WebSocket server on {WS_HOST}:{WS_PORT}")

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully (PostgreSQL)")
        # Mask password in log for security
        db_url = get_database_url()
        masked_url = db_url.split('@')[0].rsplit(':', 1)[0] + ':***@' + db_url.split('@')[1] if '@' in db_url else db_url
        logger.info(f"Connected to: {masked_url}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    yield

    # Close database connection
    logger.info("Shutting down Portfolio Optimizer WebSocket server")
    try:
        await close_db()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")


# Create FastAPI app
app = FastAPI(
    title="Portfolio Optimizer WebSocket API",
    description="Real-time WebSocket API for portfolio optimization",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware for frontend development
# WARNING: Using wildcard ["*"] in allow_origins is insecure for production.
# In production, always specify exact origins via the CORS_ORIGINS environment variable.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Message type to Pydantic model mapping
MESSAGE_MODELS: dict[str, type] = {
    "create_allocator": CreateAllocator,
    "update_allocator": UpdateAllocator,
    "delete_allocator": DeleteAllocator,
    "list_allocators": ListAllocators,
    "compute": ComputePortfolio,
    "update_dashboard_settings": UpdateDashboardSettings,
}


def parse_message(
    raw_data: dict,
) -> Union[CreateAllocator, UpdateAllocator, DeleteAllocator, ListAllocators, ComputePortfolio]:
    """
    Parse raw JSON data into the appropriate Pydantic message model.

    Args:
        raw_data: Raw dictionary from JSON parsing.

    Returns:
        Parsed Pydantic model instance.

    Raises:
        ValueError: If message type is unknown.
        ValidationError: If message validation fails.
    """
    message_type = raw_data.get("type")
    if message_type not in MESSAGE_MODELS:
        raise ValueError(f"Unknown message type: {message_type}")

    model = MESSAGE_MODELS[message_type]
    return model.model_validate(raw_data)


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(None, description="Auth0 JWT token")
):
    """
    Main WebSocket endpoint.

    Handles the connection lifecycle:
    1. Authenticate user (if Auth0 is configured)
    2. Accept connection and create state
    3. Track user connection in database
    4. Process messages in a loop
    5. Clean up on disconnect
    """
    # Get client info for logging
    client_host = websocket.client.host if websocket.client else "unknown"
    client_port = websocket.client.port if websocket.client else "unknown"
    client_id = f"{client_host}:{client_port}"

    # Authenticate user before accepting connection
    auth0_user_id = None
    if is_auth_configured():
        if not token:
            logger.warning(f"Authentication required but no token provided from {client_id}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
            return

        try:
            payload: TokenPayload = await validate_token(token)
            auth0_user_id = payload.sub
            logger.debug(f"Authenticated user: {auth0_user_id}")
        except AuthError as e:
            logger.warning(f"Authentication failed for {client_id}: {e.error}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=e.error)
            return
    else:
        logger.debug("Auth0 not configured, allowing anonymous connection")

    # Accept WebSocket connection after successful authentication
    await websocket.accept()
    state = ConnectionState(auth0_user_id=auth0_user_id)

    # Generate unique session ID for this connection
    session_id = str(uuid.uuid4())

    logger.info(f"Client connected: {client_id} (session: {session_id}, user: {auth0_user_id or 'anonymous'})")

    # Track user connection in database
    try:
        async with async_session_maker() as db_session:
            await create_user(db_session, session_id, auth0_user_id)
            await db_session.commit()
            logger.debug(f"Created user record for session: {session_id}")
    except Exception as db_error:
        logger.warning(f"Failed to create user record in database: {db_error}")
        # Continue execution even if database tracking fails

    try:
        while True:
            # Receive raw JSON text
            raw_text = await websocket.receive_text()

            # Update user activity in database
            try:
                async with async_session_maker() as db_session:
                    await update_user_activity(db_session, session_id)
                    await db_session.commit()
            except Exception as db_error:
                logger.debug(f"Failed to update user activity: {db_error}")
                # Continue execution even if database tracking fails

            try:
                # Parse JSON
                raw_data = json.loads(raw_text)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON from {client_id}: {e}")
                error = Error(message=f"Invalid JSON: {e}")
                await websocket.send_json(error.model_dump())
                continue

            try:
                # Parse into typed message
                message = parse_message(raw_data)
            except ValueError as e:
                logger.warning(f"Unknown message type from {client_id}: {e}")
                error = Error(message=str(e))
                await websocket.send_json(error.model_dump())
                continue
            except ValidationError as e:
                logger.warning(f"Validation error from {client_id}: {e}")
                error = Error(message=f"Validation error: {e}")
                await websocket.send_json(error.model_dump())
                continue

            # Route to appropriate handler
            handler = MESSAGE_HANDLERS.get(message.type)
            if handler:
                logger.debug(f"Handling {message.type} from {client_id}")
                await handler(websocket, state, message)
            else:
                logger.error(f"No handler for message type: {message.type}")
                error = Error(message=f"No handler for message type: {message.type}")
                await websocket.send_json(error.model_dump())

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Error in WebSocket connection {client_id}: {e}")
    finally:
        # Cleanup connection state
        try:
            await state.clear()
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")

        # Delete user record from database
        try:
            async with async_session_maker() as db_session:
                deleted = await delete_user(db_session, session_id)
                await db_session.commit()
                if deleted:
                    logger.debug(f"Deleted user record for session: {session_id}")
                else:
                    logger.debug(f"User record not found for session: {session_id}")
        except Exception as db_error:
            logger.warning(f"Failed to delete user record from database: {db_error}")

        # Close WebSocket connection
        try:
            await websocket.close()
        except Exception:
            pass  # Connection may already be closed
        logger.debug(f"Cleaned up state for {client_id}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# =============================================================================
# HTTP API Endpoints
# =============================================================================

# HTTP Bearer token scheme for API authentication
http_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)]
) -> TokenPayload:
    """
    Dependency to get the current authenticated user from HTTP Bearer token.

    Args:
        credentials: The HTTP Authorization credentials (Bearer token)

    Returns:
        TokenPayload: The validated token payload with user info

    Raises:
        HTTPException: If authentication fails
    """
    if not is_auth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication not configured",
        )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = await validate_token(credentials.credentials)
        return payload
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/api/dashboard")
async def get_dashboard(
    current_user: Annotated[TokenPayload, Depends(get_current_user)]
):
    """
    Get the current user's dashboard data (allocators and settings).

    This endpoint returns the complete dashboard state for the authenticated user,
    including all their allocators and dashboard settings.

    Returns:
        dict: Dashboard data with allocators and settings
    """
    try:
        async with async_session_maker() as db_session:
            dashboard_data = await get_user_dashboard(db_session, current_user.sub)
            return dashboard_data
    except Exception as e:
        logger.error(f"Error fetching dashboard for user {current_user.sub}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch dashboard data",
        )


# Serve frontend static files at root (must be last to not override API routes)
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=WS_HOST,
        port=WS_PORT,
        reload=False,
        log_level="info",
    )
