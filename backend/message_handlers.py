"""
WebSocket message handlers.

Each handler processes a specific message type and sends appropriate responses.
Allocator operations are persisted to the database for authenticated users.
"""

import asyncio
import logging
import uuid
from datetime import date
from typing import Any, Dict, Type

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from allocators.base import Allocator, Portfolio
from allocators.manual import ManualAllocator
from allocators.max_sharpe import MaxSharpeAllocator
from allocators.min_volatility import MinVolatilityAllocator
from connection_state import ConnectionState, create_compute_cache_key
from db import async_session_maker
from db.crud import (
    create_allocator as db_create_allocator,
    update_allocator as db_update_allocator,
    delete_allocator as db_delete_allocator,
    get_allocators_by_user,
    create_or_update_dashboard_settings,
)
from errors import AppError, ValidationError, NetworkError, ComputeError, DatabaseError, ErrorCategory, ErrorSeverity
from schemas import (
    AllocatorCreated,
    AllocatorDeleted,
    AllocatorsList,
    AllocatorUpdated,
    ComputePortfolio,
    CreateAllocator,
    DeleteAllocator,
    DashboardSettingsUpdated,
    Error,
    ListAllocators,
    Progress,
    Result,
    UpdateAllocator,
    UpdateDashboardSettings,
)
from services.portfolio import calculate_metrics, compute_performance
from services.price_fetcher import get_price_data, InvalidTickerError, RateLimitError, APIError, CacheDateRangeError

logger = logging.getLogger(__name__)


async def send_error(websocket: WebSocket, error: AppError) -> None:
    """Send structured error through WebSocket."""
    await websocket.send_json(error.to_dict())


# Registry of allocator types to their implementation classes
ALLOCATOR_CLASSES: Dict[str, Type[Allocator]] = {
    "manual": ManualAllocator,
    "max_sharpe": MaxSharpeAllocator,
    "min_volatility": MinVolatilityAllocator,
}


def transform_frontend_config(allocator_type: str, config: dict) -> dict:
    """
    Transform frontend config format to backend format.

    Frontend sends:
        update_interval: { value: number, unit: string } | null
        target_return: number | null

    Backend expects:
        update_enabled: bool
        update_interval_value: int
        update_interval_unit: str
        target_return_enabled: bool
        target_return_value: float
    """
    transformed = config.copy()

    # Transform update_interval to update_enabled/value/unit
    update_interval = transformed.pop("update_interval", None)
    if update_interval is not None:
        transformed["update_enabled"] = True
        transformed["update_interval_value"] = update_interval.get("value", 1)
        transformed["update_interval_unit"] = update_interval.get("unit", "days")
    else:
        transformed["update_enabled"] = False

    # Transform target_return to target_return_enabled/value (min_volatility only)
    if allocator_type == "min_volatility":
        target_return = transformed.pop("target_return", None)
        if target_return is not None:
            transformed["target_return_enabled"] = True
            transformed["target_return_value"] = target_return
        else:
            transformed["target_return_enabled"] = False

    return transformed


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

    # Transform frontend config format to backend format
    transformed_config = transform_frontend_config(allocator_type, config)
    return cls.from_config(transformed_config)


async def send_message(websocket: WebSocket, message: Any) -> bool:
    """
    Send a Pydantic model as JSON through the WebSocket.

    Args:
        websocket: The WebSocket connection.
        message: A Pydantic model to serialize and send.

    Returns:
        True if message was sent successfully, False if connection was closed.
    """
    if websocket.client_state != WebSocketState.CONNECTED:
        logger.warning(f"Cannot send message, WebSocket not connected: {websocket.client_state}")
        return False
    try:
        await websocket.send_json(message.model_dump())
        return True
    except Exception as e:
        # Handle WebSocketDisconnect and other connection errors gracefully
        logger.debug(f"Failed to send message (connection closed): {e}")
        return False


async def handle_create_allocator(
    websocket: WebSocket, state: ConnectionState, message: CreateAllocator
) -> None:
    """
    Handle allocator creation request.

    For authenticated users, persists the allocator to the database.
    For anonymous users, stores only in session state.

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

        # Extract name from config (default to type if not specified)
        name = message.config.get("name", message.allocator_type)

        # Generate allocator ID
        allocator_id = str(uuid.uuid4())

        # Persist to database if user is authenticated
        if state.auth0_user_id:
            try:
                async with async_session_maker() as db_session:
                    await db_create_allocator(
                        session=db_session,
                        auth0_user_id=state.auth0_user_id,
                        name=name,
                        allocator_type=message.allocator_type,
                        config=message.config,
                        enabled=False,
                        allocator_id=uuid.UUID(allocator_id),
                    )
                    await db_session.commit()
                    logger.debug(f"Persisted allocator {allocator_id} to database")
            except Exception as db_error:
                logger.error(f"Failed to persist allocator to database: {db_error}")
                # Send warning but continue with session-only storage
                warning = DatabaseError(
                    message="Allocator created but failed to save. Changes may be lost on disconnect.",
                    code="DB_002",
                    severity=ErrorSeverity.WARNING,
                    recoverable=True
                )
                await send_error(websocket, warning)

        # Store in session state (for computation)
        state.allocators[allocator_id] = {
            "id": allocator_id,
            "type": message.allocator_type,
            "config": message.config,
            "instance": allocator_instance,
        }

        response = AllocatorCreated(
            id=allocator_id,
            allocator_type=message.allocator_type,
            config=message.config,
        )
        await send_message(websocket, response)
        logger.info(f"Created allocator {allocator_id} of type {message.allocator_type}")

    except ValueError as e:
        logger.error(f"Validation error creating allocator: {e}")
        error = ValidationError(
            message=str(e),
            code="VAL_004"
        )
        await send_error(websocket, error)
    except Exception as e:
        logger.error(f"Error creating allocator: {e}")
        await send_message(websocket, Error(message=str(e)))


async def handle_update_allocator(
    websocket: WebSocket, state: ConnectionState, message: UpdateAllocator
) -> None:
    """
    Handle allocator update request.

    For authenticated users, persists the update to the database.

    Args:
        websocket: The WebSocket connection.
        state: The connection state.
        message: The update allocator message.
    """
    try:
        # Get existing allocator to determine its type
        existing = await state.get_allocator(message.id)
        if existing is None:
            await send_message(
                websocket,
                Error(
                    message="Allocator not found. Please refresh the page or create a new allocator.",
                    allocator_id=message.id,
                ),
            )
            return

        # Recreate the allocator instance with the new config
        allocator_type = existing["type"]
        allocator_instance = create_allocator_instance(allocator_type, message.config)

        # Persist to database if user is authenticated
        if state.auth0_user_id:
            try:
                async with async_session_maker() as db_session:
                    name = message.config.get("name")
                    await db_update_allocator(
                        session=db_session,
                        allocator_id=uuid.UUID(message.id),
                        auth0_user_id=state.auth0_user_id,
                        config=message.config,
                        name=name,
                    )
                    await db_session.commit()
                    logger.debug(f"Persisted allocator update {message.id} to database")
            except Exception as db_error:
                logger.error(f"Failed to persist allocator update to database: {db_error}")
                # Send warning but continue with the operation
                warning = DatabaseError(
                    message="Allocator updated but failed to save. Changes may be lost on disconnect.",
                    code="DB_002",
                    severity=ErrorSeverity.WARNING,
                    recoverable=True
                )
                await send_error(websocket, warning)

        # Invalidate cached results for this allocator since config changed
        await state.invalidate_allocator_cache(message.id)

        # Update the stored state with the new config and instance
        if await state.update_allocator(
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
                    message="Allocator not found. Please refresh the page or create a new allocator.",
                    allocator_id=message.id,
                ),
            )

    except ValueError as e:
        logger.error(f"Validation error updating allocator {message.id}: {e}")
        error = ValidationError(
            message=str(e),
            code="VAL_004"
        )
        await send_error(websocket, error)
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

    For authenticated users, removes the allocator from the database.

    Args:
        websocket: The WebSocket connection.
        state: The connection state.
        message: The delete allocator message.
    """
    try:
        # Persist deletion to database if user is authenticated
        if state.auth0_user_id:
            try:
                async with async_session_maker() as db_session:
                    await db_delete_allocator(
                        session=db_session,
                        allocator_id=uuid.UUID(message.id),
                        auth0_user_id=state.auth0_user_id,
                    )
                    await db_session.commit()
                    logger.debug(f"Deleted allocator {message.id} from database")
            except Exception as db_error:
                logger.error(f"Failed to delete allocator from database: {db_error}")
                # Send warning but continue with the operation
                warning = DatabaseError(
                    message="Allocator deleted but failed to save. Changes may be lost on disconnect.",
                    code="DB_002",
                    severity=ErrorSeverity.WARNING,
                    recoverable=True
                )
                await send_error(websocket, warning)

        # Invalidate cached results for this allocator
        await state.invalidate_allocator_cache(message.id)

        if await state.delete_allocator(message.id):
            response = AllocatorDeleted(id=message.id)
            await send_message(websocket, response)
            logger.info(f"Deleted allocator {message.id}")
        else:
            await send_message(
                websocket,
                Error(
                    message="Allocator not found. Please refresh the page or create a new allocator.",
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
        allocators = await state.list_allocators()
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
    Results are cached to prevent recomputation of unchanged allocators.

    Args:
        websocket: The WebSocket connection.
        state: The connection state.
        message: The compute portfolio message.
    """
    allocator_id = message.allocator_id

    try:
        # Check if allocator exists and get its instance
        allocator_data = await state.get_allocator(allocator_id)
        if allocator_data is None:
            await send_message(
                websocket,
                Error(
                    message="Allocator not found. Please refresh the page or create a new allocator.",
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

        # Progress tracking info from request
        current_allocator = message.current_allocator
        total_allocators = message.total_allocators
        allocator_name = allocator_data.get("config", {}).get("name", "Allocator")

        # Check cache before computing
        cache_key = create_compute_cache_key(
            allocator_id=allocator_id,
            allocator_config=allocator_data.get("config", {}),
            fit_start_date=message.fit_start_date,
            fit_end_date=message.fit_end_date,
            test_end_date=message.test_end_date,
            include_dividends=message.include_dividends,
        )

        cached_result = await state.get_cached_result(cache_key)
        if cached_result:
            # Send cached result immediately
            logger.info(f"Returning cached result for allocator {allocator_id}")
            await send_message(
                websocket,
                Progress(
                    allocator_id=allocator_id,
                    allocator_name=allocator_name,
                    phase="cached",
                    current=current_allocator,
                    total=total_allocators,
                ),
            )
            result = Result(
                allocator_id=allocator_id,
                segments=cached_result["segments"],
                performance=cached_result["performance"],
            )
            await send_message(websocket, result)
            return

        # Parse dates from strings to date objects
        try:
            fit_start_date = date.fromisoformat(message.fit_start_date)
            fit_end_date = date.fromisoformat(message.fit_end_date)
            test_end_date = date.fromisoformat(message.test_end_date)
        except ValueError as e:
            error = ValidationError(
                message=f"Invalid date format: {e}",
                code="VAL_002"
            )
            await send_error(websocket, error)
            return

        # Validate date ranges
        if fit_end_date <= fit_start_date:
            error = ValidationError(
                message="Fit end date must be after fit start date",
                code="VAL_003"
            )
            await send_error(websocket, error)
            return

        if test_end_date <= fit_end_date:
            error = ValidationError(
                message="Test end date must be after fit end date",
                code="VAL_003"
            )
            await send_error(websocket, error)
            return

        # Helper to send progress updates with new schema
        async def send_progress(
            phase: str,
            segment: int = None,
            total_segments: int = None
        ):
            await send_message(
                websocket,
                Progress(
                    allocator_id=allocator_id,
                    allocator_name=allocator_name,
                    phase=phase,
                    current=current_allocator,
                    total=total_allocators,
                    segment=segment,
                    total_segments=total_segments,
                ),
            )

        # Create a progress callback for allocators (they report segment progress)
        async def allocator_progress_callback(
            segment: int = None,
            total_segments: int = None
        ):
            await send_progress("optimizing", segment, total_segments)

        # Create a price fetcher wrapper
        async def price_fetcher(ticker: str, start: date, end: date):
            return await get_price_data(ticker, start, end)

        # Send fetching progress
        await send_progress("fetching")

        # Compute the portfolio allocations with a timeout
        await send_progress("optimizing")
        try:
            portfolio: Portfolio = await asyncio.wait_for(
                allocator_instance.compute(
                    fit_start_date=fit_start_date,
                    fit_end_date=fit_end_date,
                    test_end_date=test_end_date,
                    include_dividends=message.include_dividends,
                    price_fetcher=price_fetcher,
                    progress_callback=allocator_progress_callback,
                ),
                timeout=300  # 5 minutes timeout
            )
        except asyncio.TimeoutError:
            error_msg = f"Computation timed out after 300 seconds for allocator {allocator_id}"
            logger.error(error_msg)
            error = ComputeError(
                message="Computation timed out after 5 minutes. Please try with a shorter date range or fewer assets.",
                code="CMP_004"
            )
            await send_error(websocket, error)
            return

        # Convert portfolio segments to dict format for the Result message
        segments = []
        for segment in portfolio.segments:
            segments.append({
                "start_date": segment.start_date.isoformat(),
                "end_date": segment.end_date.isoformat(),
                "weights": segment.allocations,
            })

        # Calculate performance metrics
        await send_progress("metrics")
        performance = await compute_performance(
            portfolio=portfolio,
            fit_end_date=fit_end_date,
            test_end_date=test_end_date,
            include_dividends=message.include_dividends,
            price_fetcher=price_fetcher,
        )

        # Calculate and add statistics to performance
        stats = calculate_metrics(
            cumulative_returns=performance.get("cumulative_returns", []),
            dates=performance.get("dates", [])
        )
        performance["stats"] = stats

        await send_progress("complete")

        # Cache the result for future use
        await state.set_cached_result(cache_key, {
            "allocator_id": allocator_id,
            "segments": segments,
            "performance": performance,
        })

        # Send the result
        result = Result(
            allocator_id=allocator_id,
            segments=segments,
            performance=performance,
        )
        await send_message(websocket, result)
        logger.info(f"Completed computation for allocator {allocator_id}")

    except InvalidTickerError as e:
        logger.error(f"Invalid ticker for allocator {allocator_id}: {e}")
        # Get allocator name for human-readable message
        allocator_name = allocator_data.get("config", {}).get("name", allocator_data.get("type", "allocator"))
        ticker = e.ticker or "unknown"
        error = ValidationError(
            message=f"Invalid ticker '{ticker}' in {allocator_name}",
            code="VAL_001",
            allocator_id=allocator_id
        )
        await send_error(websocket, error)
    except CacheDateRangeError as e:
        logger.error(f"Date range error for allocator {allocator_id}: {e}")
        # Get allocator name for human-readable message
        allocator_name = allocator_data.get("config", {}).get("name", allocator_data.get("type", "allocator"))
        ticker = e.ticker or "unknown instrument"
        requested = e.requested_date.isoformat() if e.requested_date else "unknown"
        earliest = e.earliest_date.isoformat() if e.earliest_date else "unknown"
        error = ValidationError(
            message=f"No data available for {requested} in '{allocator_name}'. The earliest available date is {earliest} (due to {ticker}).",
            code="VAL_006",
            allocator_id=allocator_id
        )
        await send_error(websocket, error)
    except RateLimitError as e:
        logger.error(f"Rate limit error for allocator {allocator_id}: {e}")
        error = NetworkError(
            message=str(e),
            code="NET_002",
            recoverable=True
        )
        await send_error(websocket, error)
    except AppError as e:
        logger.error(f"Application error computing portfolio for {allocator_id}: {e}")
        await send_error(websocket, e)
    except ValueError as e:
        # Handle ValueError from compute_performance (e.g., failed tickers)
        logger.error(f"Value error computing portfolio for {allocator_id}: {e}")
        allocator_name = allocator_data.get("config", {}).get("name", allocator_data.get("type", "allocator")) if allocator_data else "allocator"
        error_msg = str(e)
        # Make the message more user-friendly by including allocator name
        if "Failed to fetch price data" in error_msg:
            # Extract failed tickers from message
            error = ValidationError(
                message=f"{error_msg} in '{allocator_name}'",
                code="VAL_001",
                allocator_id=allocator_id
            )
        else:
            error = ValidationError(
                message=f"{error_msg} in '{allocator_name}'",
                code="VAL_004",
                allocator_id=allocator_id
            )
        await send_error(websocket, error)
    except Exception as e:
        logger.error(f"Error computing portfolio for {allocator_id}: {e}", exc_info=True)
        allocator_name = allocator_data.get("config", {}).get("name", allocator_data.get("type", "allocator")) if allocator_data else "allocator"
        error = AppError(
            message=f"Error in '{allocator_name}': {str(e)}",
            code="SYS_001",
            category=ErrorCategory.SYSTEM,
            allocator_id=allocator_id
        )
        await send_error(websocket, error)


async def handle_update_dashboard_settings(
    websocket: WebSocket, state: ConnectionState, message: UpdateDashboardSettings
) -> None:
    """
    Handle dashboard settings update request.

    Persists settings to database for authenticated users.

    Args:
        websocket: The WebSocket connection.
        state: The connection state.
        message: The update dashboard settings message.
    """
    try:
        # Parse dates if provided
        fit_start = date.fromisoformat(message.fit_start_date) if message.fit_start_date else None
        fit_end = date.fromisoformat(message.fit_end_date) if message.fit_end_date else None
        test_end = date.fromisoformat(message.test_end_date) if message.test_end_date else None

        # Persist to database if user is authenticated
        if state.auth0_user_id:
            try:
                async with async_session_maker() as db_session:
                    settings = await create_or_update_dashboard_settings(
                        session=db_session,
                        auth0_user_id=state.auth0_user_id,
                        fit_start_date=fit_start,
                        fit_end_date=fit_end,
                        test_end_date=test_end,
                        include_dividends=message.include_dividends,
                    )
                    await db_session.commit()
                    logger.debug(f"Updated dashboard settings for user {state.auth0_user_id}")

                    # Send response with the updated settings
                    response = DashboardSettingsUpdated(
                        fit_start_date=settings.fit_start_date.isoformat() if settings.fit_start_date else None,
                        fit_end_date=settings.fit_end_date.isoformat() if settings.fit_end_date else None,
                        test_end_date=settings.test_end_date.isoformat() if settings.test_end_date else None,
                        include_dividends=settings.include_dividends,
                    )
                    await send_message(websocket, response)
            except Exception as db_error:
                logger.error(f"Failed to persist dashboard settings: {db_error}")
                await send_message(websocket, Error(message=f"Failed to save settings: {str(db_error)}"))
        else:
            # For anonymous users, just acknowledge the message
            response = DashboardSettingsUpdated(
                fit_start_date=message.fit_start_date,
                fit_end_date=message.fit_end_date,
                test_end_date=message.test_end_date,
                include_dividends=message.include_dividends,
            )
            await send_message(websocket, response)

    except Exception as e:
        logger.error(f"Error updating dashboard settings: {e}")
        await send_message(websocket, Error(message=str(e)))


# Handler registry mapping message types to handler functions
MESSAGE_HANDLERS = {
    "create_allocator": handle_create_allocator,
    "update_allocator": handle_update_allocator,
    "delete_allocator": handle_delete_allocator,
    "list_allocators": handle_list_allocators,
    "compute": handle_compute_portfolio,
    "update_dashboard_settings": handle_update_dashboard_settings,
}
