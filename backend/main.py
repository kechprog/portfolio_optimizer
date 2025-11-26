"""
FastAPI WebSocket server for Portfolio Optimizer.

Provides real-time communication between the React frontend and Python backend
for portfolio optimization computations.
"""

import json
import logging
from contextlib import asynccontextmanager
from typing import Union

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from config import WS_HOST, WS_PORT
from connection_state import ConnectionState
from message_handlers import MESSAGE_HANDLERS
from schemas import (
    ComputePortfolio,
    CreateAllocator,
    DeleteAllocator,
    Error,
    ListAllocators,
    UpdateAllocator,
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
    yield
    logger.info("Shutting down Portfolio Optimizer WebSocket server")


# Create FastAPI app
app = FastAPI(
    title="Portfolio Optimizer WebSocket API",
    description="Real-time WebSocket API for portfolio optimization",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
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
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint.

    Handles the connection lifecycle:
    1. Accept connection and create state
    2. Process messages in a loop
    3. Clean up on disconnect
    """
    await websocket.accept()
    state = ConnectionState()

    # Get client info for logging
    client_host = websocket.client.host if websocket.client else "unknown"
    client_port = websocket.client.port if websocket.client else "unknown"
    client_id = f"{client_host}:{client_port}"

    logger.info(f"Client connected: {client_id}")

    try:
        while True:
            # Receive raw JSON text
            raw_text = await websocket.receive_text()

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
        # Cleanup
        state.clear()
        logger.debug(f"Cleaned up state for {client_id}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=WS_HOST,
        port=WS_PORT,
        reload=False,
        log_level="info",
    )
