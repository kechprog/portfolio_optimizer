"""
WebSocket message handlers.

Each handler processes a specific message type and sends appropriate responses.
"""

import logging
from datetime import date
from typing import Any, Dict, Type

from fastapi import WebSocket

from allocators.base import Allocator, Portfolio
from allocators.manual import ManualAllocator
from allocators.max_sharpe import MaxSharpeAllocator
from allocators.min_volatility import MinVolatilityAllocator
from connection_state import ConnectionState
from schemas import (
    AllocatorCreated,
    AllocatorDeleted,
    AllocatorsList,
    AllocatorUpdated,
    ComputePortfolio,
    CreateAllocator,
    DeleteAllocator,
    Error,
    ListAllocators,
    Progress,
    Result,
    UpdateAllocator,
)
from services.portfolio import compute_performance
from services.price_fetcher import get_price_data

logger = logging.getLogger(__name__)


# Registry of allocator types to their implementation classes
ALLOCATOR_CLASSES: Dict[str, Type[Allocator]] = {
    "manual": ManualAllocator,
    "max_sharpe": MaxSharpeAllocator,
    "min_volatility": MinVolatilityAllocator,
}


def create_allocator_instance(allocator_type: str, config: dict) -> Allocator:
    """
    Create an allocator instance from a type string and configuration.

    Args:
        allocator_type: The type of allocator to create.
        config: Configuration dictionary for the allocator.

    Returns:
        An Allocator instance.

    Raises:
        ValueError: If the allocator type is unknown.
    """
    cls = ALLOCATOR_CLASSES.get(allocator_type)
    if cls is None:
        raise ValueError(f"Unknown allocator type: {allocator_type}")
    return cls.from_config(config)


async def send_message(websocket: WebSocket, message: Any) -> None:
    """
    Send a Pydantic model as JSON through the WebSocket.

    Args:
        websocket: The WebSocket connection.
        message: A Pydantic model to serialize and send.
    """
    await websocket.send_json(message.model_dump())


async def handle_create_allocator(
    websocket: WebSocket, state: ConnectionState, message: CreateAllocator
) -> None:
    """
    Handle allocator creation request.

    Args:
        websocket: The WebSocket connection.
        state: The connection state.
        message: The create allocator message.
    """
    try:
        # Create the actual allocator instance
        allocator_instance = create_allocator_instance(
            message.allocator_type, message.config
        )

        # Store both the config and the instance
        allocator_id = state.add_allocator(
            allocator_type=message.allocator_type,
            config=message.config,
            allocator_instance=allocator_instance,
        )

        response = AllocatorCreated(
            id=allocator_id,
            allocator_type=message.allocator_type,
            config=message.config,
        )
        await send_message(websocket, response)
        logger.info(f"Created allocator {allocator_id} of type {message.allocator_type}")

    except Exception as e:
        logger.error(f"Error creating allocator: {e}")
        await send_message(websocket, Error(message=str(e)))


async def handle_update_allocator(
    websocket: WebSocket, state: ConnectionState, message: UpdateAllocator
) -> None:
    """
    Handle allocator update request.

    Args:
        websocket: The WebSocket connection.
        state: The connection state.
        message: The update allocator message.
    """
    try:
        # Get existing allocator to determine its type
        existing = state.get_allocator(message.id)
        if existing is None:
            await send_message(
                websocket,
                Error(
                    message=f"Allocator {message.id} not found",
                    allocator_id=message.id,
                ),
            )
            return

        # Recreate the allocator instance with the new config
        allocator_type = existing["type"]
        allocator_instance = create_allocator_instance(allocator_type, message.config)

        # Update the stored state with the new config and instance
        if state.update_allocator(
            message.id, message.config, allocator_instance=allocator_instance
        ):
            response = AllocatorUpdated(
                id=message.id,
                config=message.config,
            )
            await send_message(websocket, response)
            logger.info(f"Updated allocator {message.id}")
        else:
            await send_message(
                websocket,
                Error(
                    message=f"Allocator {message.id} not found",
                    allocator_id=message.id,
                ),
            )

    except Exception as e:
        logger.error(f"Error updating allocator {message.id}: {e}")
        await send_message(
            websocket,
            Error(message=str(e), allocator_id=message.id),
        )


async def handle_delete_allocator(
    websocket: WebSocket, state: ConnectionState, message: DeleteAllocator
) -> None:
    """
    Handle allocator deletion request.

    Args:
        websocket: The WebSocket connection.
        state: The connection state.
        message: The delete allocator message.
    """
    try:
        if state.delete_allocator(message.id):
            response = AllocatorDeleted(id=message.id)
            await send_message(websocket, response)
            logger.info(f"Deleted allocator {message.id}")
        else:
            await send_message(
                websocket,
                Error(
                    message=f"Allocator {message.id} not found",
                    allocator_id=message.id,
                ),
            )

    except Exception as e:
        logger.error(f"Error deleting allocator {message.id}: {e}")
        await send_message(
            websocket,
            Error(message=str(e), allocator_id=message.id),
        )


async def handle_list_allocators(
    websocket: WebSocket, state: ConnectionState, message: ListAllocators
) -> None:
    """
    Handle list allocators request.

    Args:
        websocket: The WebSocket connection.
        state: The connection state.
        message: The list allocators message.
    """
    try:
        allocators = state.list_allocators()
        response = AllocatorsList(allocators=allocators)
        await send_message(websocket, response)
        logger.debug(f"Listed {len(allocators)} allocators")

    except Exception as e:
        logger.error(f"Error listing allocators: {e}")
        await send_message(websocket, Error(message=str(e)))


async def handle_compute_portfolio(
    websocket: WebSocket, state: ConnectionState, message: ComputePortfolio
) -> None:
    """
    Handle portfolio computation request.

    Executes the allocator's compute method to generate portfolio allocations,
    then calculates performance metrics for the resulting portfolio.

    Args:
        websocket: The WebSocket connection.
        state: The connection state.
        message: The compute portfolio message.
    """
    allocator_id = message.allocator_id

    try:
        # Check if allocator exists and get its instance
        allocator_data = state.get_allocator(allocator_id)
        if allocator_data is None:
            await send_message(
                websocket,
                Error(
                    message=f"Allocator {allocator_id} not found",
                    allocator_id=allocator_id,
                ),
            )
            return

        allocator_instance: Allocator = allocator_data.get("instance")
        if allocator_instance is None:
            await send_message(
                websocket,
                Error(
                    message=f"Allocator {allocator_id} has no instance",
                    allocator_id=allocator_id,
                ),
            )
            return

        # Parse dates from strings to date objects
        fit_start_date = date.fromisoformat(message.fit_start_date)
        fit_end_date = date.fromisoformat(message.fit_end_date)
        test_end_date = date.fromisoformat(message.test_end_date)

        # Create a progress callback that sends Progress messages via websocket
        async def progress_callback(msg: str, step: int, total_steps: int):
            await send_message(
                websocket,
                Progress(
                    allocator_id=allocator_id,
                    message=msg,
                    step=step,
                    total_steps=total_steps,
                ),
            )

        # Create a price fetcher wrapper
        async def price_fetcher(ticker: str, start: date, end: date):
            return await get_price_data(ticker, start, end)

        # Send initial progress
        await progress_callback("Starting portfolio computation...", 0, 4)

        # Compute the portfolio allocations
        await progress_callback("Computing allocations...", 1, 4)
        portfolio: Portfolio = await allocator_instance.compute(
            fit_start_date=fit_start_date,
            fit_end_date=fit_end_date,
            test_end_date=test_end_date,
            include_dividends=message.include_dividends,
            price_fetcher=price_fetcher,
            progress_callback=progress_callback,
        )

        # Convert portfolio segments to dict format for the Result message
        segments = []
        for segment in portfolio.segments:
            segments.append({
                "start_date": segment.start_date.isoformat(),
                "end_date": segment.end_date.isoformat(),
                "weights": segment.allocations,
            })

        # Calculate performance metrics
        await progress_callback("Calculating performance metrics...", 3, 4)
        performance = await compute_performance(
            portfolio=portfolio,
            fit_end_date=fit_end_date,
            test_end_date=test_end_date,
            include_dividends=message.include_dividends,
            price_fetcher=price_fetcher,
        )

        await progress_callback("Computation complete", 4, 4)

        # Send the result
        result = Result(
            allocator_id=allocator_id,
            segments=segments,
            performance=performance,
        )
        await send_message(websocket, result)
        logger.info(f"Completed computation for allocator {allocator_id}")

    except Exception as e:
        logger.error(f"Error computing portfolio for {allocator_id}: {e}", exc_info=True)
        await send_message(
            websocket,
            Error(message=str(e), allocator_id=allocator_id),
        )


# Handler registry mapping message types to handler functions
MESSAGE_HANDLERS = {
    "create_allocator": handle_create_allocator,
    "update_allocator": handle_update_allocator,
    "delete_allocator": handle_delete_allocator,
    "list_allocators": handle_list_allocators,
    "compute": handle_compute_portfolio,
}
