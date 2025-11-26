"""
Connection state management for WebSocket connections.

Each WebSocket connection has its own ConnectionState instance
that tracks allocators and caches data for that session.
"""

import asyncio
import copy
import hashlib
import json
import logging
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


def create_compute_cache_key(
    allocator_id: str,
    allocator_config: dict,
    fit_start_date: str,
    fit_end_date: str,
    test_end_date: str,
    include_dividends: bool
) -> str:
    """
    Create a cache key from compute parameters.

    Returns a hash that uniquely identifies the computation request.
    """
    cache_data = {
        "allocator_id": allocator_id,
        "config": allocator_config,
        "fit_start_date": fit_start_date,
        "fit_end_date": fit_end_date,
        "test_end_date": test_end_date,
        "include_dividends": include_dividends,
    }
    # Use JSON for deterministic serialization, then hash
    data_str = json.dumps(cache_data, sort_keys=True)
    return hashlib.sha256(data_str.encode()).hexdigest()


class ConnectionState:
    """
    Holds per-connection state for a WebSocket session.

    Attributes:
        allocators: Dictionary mapping allocator IDs to allocator instances.
        matrix_cache: Dictionary for caching matrix data during computation.
    """

    def __init__(self) -> None:
        """Initialize empty connection state."""
        self.allocators: dict[str, Any] = {}
        self.matrix_cache: dict[str, Any] = {}
        self.results_cache: dict[str, Any] = {}  # Cache for computation results
        self._lock = asyncio.Lock()

    async def add_allocator(
        self, allocator_type: str, config: dict[str, Any], allocator_instance: Any = None
    ) -> str:
        """
        Add a new allocator to the connection state.

        Args:
            allocator_type: Type of the allocator (e.g., "mean_variance", "equal_weight").
            config: Configuration dictionary for the allocator.
            allocator_instance: Optional allocator instance. If None, stores config only.

        Returns:
            The generated unique ID for the allocator.
        """
        async with self._lock:
            allocator_id = str(uuid4())
            self.allocators[allocator_id] = {
                "id": allocator_id,
                "type": allocator_type,
                "config": config,
                "instance": allocator_instance,
            }
            logger.debug(f"Added allocator {allocator_id} of type {allocator_type}")
            return allocator_id

    async def update_allocator(
        self, allocator_id: str, config: dict[str, Any], allocator_instance: Any = None
    ) -> bool:
        """
        Update an existing allocator's configuration.

        Args:
            allocator_id: ID of the allocator to update.
            config: New configuration dictionary.
            allocator_instance: Optional new allocator instance.

        Returns:
            True if the allocator was found and updated, False otherwise.
        """
        async with self._lock:
            if allocator_id not in self.allocators:
                logger.warning(f"Attempted to update non-existent allocator {allocator_id}")
                return False

            self.allocators[allocator_id]["config"] = config
            if allocator_instance is not None:
                self.allocators[allocator_id]["instance"] = allocator_instance
            logger.debug(f"Updated allocator {allocator_id}")
            return True

    async def delete_allocator(self, allocator_id: str) -> bool:
        """
        Delete an allocator from the connection state.

        Args:
            allocator_id: ID of the allocator to delete.

        Returns:
            True if the allocator was found and deleted, False otherwise.
        """
        async with self._lock:
            if allocator_id not in self.allocators:
                logger.warning(f"Attempted to delete non-existent allocator {allocator_id}")
                return False

            del self.allocators[allocator_id]
            logger.debug(f"Deleted allocator {allocator_id}")
            return True

    async def get_allocator(self, allocator_id: str) -> dict[str, Any] | None:
        """
        Get an allocator by ID.

        Args:
            allocator_id: ID of the allocator to retrieve.

        Returns:
            The allocator dictionary if found, None otherwise.
            Note: Returns the actual instance reference to avoid deep copy overhead.
        """
        async with self._lock:
            allocator = self.allocators.get(allocator_id)
            return allocator

    async def list_allocators(self) -> list[dict[str, Any]]:
        """
        List all allocators in the connection state.

        Returns:
            A list of allocator dictionaries (without instance objects).
            The list comprehension creates new dicts, so no deep copy needed.
        """
        async with self._lock:
            allocators = [
                {
                    "id": alloc["id"],
                    "type": alloc["type"],
                    "config": alloc["config"],
                }
                for alloc in self.allocators.values()
            ]
            return allocators

    async def get_matrix_cache(self, cache_key: str) -> Any | None:
        """
        Get cached matrix data.

        Args:
            cache_key: Key identifying the cached data.

        Returns:
            The cached data if found, None otherwise.
        """
        async with self._lock:
            return self.matrix_cache.get(cache_key)

    async def set_matrix_cache(self, cache_key: str, data: Any) -> None:
        """
        Store data in the matrix cache.

        Args:
            cache_key: Key to store the data under.
            data: The data to cache.
        """
        async with self._lock:
            self.matrix_cache[cache_key] = data
            logger.debug(f"Cached matrix data under key {cache_key}")

    async def clear_matrix_cache(self) -> None:
        """Clear all cached matrix data."""
        async with self._lock:
            self.matrix_cache.clear()
            logger.debug("Cleared matrix cache")

    async def clear(self) -> None:
        """Clear all state (allocators and cache)."""
        async with self._lock:
            self.allocators.clear()
            self.matrix_cache.clear()
            self.results_cache.clear()
            logger.debug("Cleared all connection state")

    async def get_cached_result(self, cache_key: str) -> dict[str, Any] | None:
        """
        Get cached computation result.

        Args:
            cache_key: Hash key for the cached result.

        Returns:
            The cached result dictionary if found, None otherwise.
        """
        async with self._lock:
            result = self.results_cache.get(cache_key)
            if result:
                logger.debug(f"Cache hit for key {cache_key[:16]}...")
            return result

    async def set_cached_result(self, cache_key: str, result: dict[str, Any]) -> None:
        """
        Store a computation result in the cache.

        Args:
            cache_key: Hash key for the result.
            result: The result dictionary to cache.
        """
        async with self._lock:
            self.results_cache[cache_key] = result
            logger.debug(f"Cached result under key {cache_key[:16]}...")

    async def invalidate_allocator_cache(self, allocator_id: str) -> int:
        """
        Invalidate all cached results for a specific allocator.

        Args:
            allocator_id: ID of the allocator whose cache should be cleared.

        Returns:
            Number of cache entries removed.
        """
        async with self._lock:
            # Find and remove all cache entries for this allocator
            keys_to_remove = [
                key for key in self.results_cache.keys()
                if self.results_cache[key].get("allocator_id") == allocator_id
            ]
            for key in keys_to_remove:
                del self.results_cache[key]
            if keys_to_remove:
                logger.debug(f"Invalidated {len(keys_to_remove)} cache entries for allocator {allocator_id}")
            return len(keys_to_remove)
