"""
Manual allocator implementation.

Allows users to specify fixed allocation percentages for each instrument.
"""

from datetime import date
from typing import Any, Dict, Optional, Set

from .base import Allocator, Portfolio, PortfolioSegment, PriceFetcher, ProgressCallback


class ManualAllocator(Allocator):
    """
    An allocator where the user manually specifies fixed allocation percentages.

    The allocations remain constant throughout the entire period.
    """

    def __init__(self, name: str, allocations: Dict[str, float]):
        """
        Initializes the ManualAllocator.

        Args:
            name: The name of this allocator instance.
            allocations: Dictionary mapping ticker symbols to allocation weights (0.0 to 1.0).
        """
        if not name or not name.strip():
            raise ValueError("Allocator name cannot be empty.")

        self._name = name.strip()
        self._allocations: Dict[str, float] = {}

        # Validate and store allocations
        for ticker, weight in allocations.items():
            if not isinstance(ticker, str) or not ticker.strip():
                raise ValueError(f"Invalid ticker: {ticker}")
            if not isinstance(weight, (int, float)):
                raise ValueError(f"Invalid weight for {ticker}: {weight}")

            weight_float = float(weight)

            # Validate weight is in allowed range
            # Default range is [0, 1], but could be [-1, 1] if shorting is supported
            # For manual allocator, we'll be conservative and allow [-1, 1] range
            if weight_float < -1.0 or weight_float > 1.0:
                raise ValueError(
                    f"Weight for {ticker} must be between -1 and 1, got {weight_float}"
                )

            # Normalize ticker to uppercase
            self._allocations[ticker.strip().upper()] = weight_float

        # Warn if allocations don't sum to approximately 1.0
        total_allocation = sum(self._allocations.values())
        if abs(total_allocation - 1.0) > 0.01:
            import warnings
            warnings.warn(
                f"Allocations sum to {total_allocation:.4f}, which deviates from 1.0 by more than 0.01. "
                f"This may result in unexpected portfolio behavior.",
                UserWarning
            )

    @property
    def name(self) -> str:
        """Returns the name of this allocator."""
        return self._name

    def get_instruments(self) -> Set[str]:
        """Returns the set of instrument tickers used by this allocator."""
        return set(self._allocations.keys())

    async def compute(
        self,
        fit_start_date: date,
        fit_end_date: date,
        test_end_date: date,
        include_dividends: bool,
        price_fetcher: PriceFetcher,
        progress_callback: Optional[ProgressCallback] = None
    ) -> Portfolio:
        """
        Computes the portfolio with fixed manual allocations.

        For ManualAllocator, this simply creates a single segment
        spanning from fit_end_date to test_end_date with the configured allocations.

        Args:
            fit_start_date: Start date for fitting (not used for manual allocator).
            fit_end_date: End date for fitting, becomes start of the allocation segment.
            test_end_date: End date for the allocation segment.
            include_dividends: Whether to include dividends (not used for manual allocator).
            price_fetcher: Async function to fetch prices (not used for manual allocator).
            progress_callback: Optional callback for progress updates.

        Returns:
            Portfolio with a single segment containing the manual allocations.
        """
        if progress_callback:
            await progress_callback("Computing manual allocations", 1, 2)

        # Validate date range
        if test_end_date <= fit_end_date:
            raise ValueError(
                f"test_end_date ({test_end_date}) must be after fit_end_date ({fit_end_date})"
            )

        portfolio = Portfolio()
        portfolio.append_segment(
            start_date=fit_end_date,
            end_date=test_end_date,
            allocations=self._allocations.copy()
        )

        if progress_callback:
            await progress_callback("Manual allocations complete", 2, 2)

        return portfolio

    def get_config(self) -> Dict[str, Any]:
        """
        Returns the configuration for serialization.

        Returns:
            Dictionary with 'type', 'name', and 'allocations' keys.
        """
        return {
            "type": "manual",
            "name": self._name,
            "allocations": self._allocations.copy()
        }

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "ManualAllocator":
        """
        Creates a ManualAllocator from a configuration dictionary.

        Args:
            config: Dictionary with 'name' and 'allocations' keys.

        Returns:
            ManualAllocator instance.
        """
        name = config.get("name", "Manual Allocator")
        allocations = config.get("allocations", {})
        return cls(name=name, allocations=allocations)

    def get_allocation_sum(self) -> float:
        """
        Returns the sum of all allocation weights.

        Useful for validation - should typically sum to 1.0 (100%).

        Returns:
            Sum of all allocation weights.
        """
        return sum(self._allocations.values())

    def is_fully_allocated(self, tolerance: float = 1e-7) -> bool:
        """
        Checks if allocations sum to 1.0 within tolerance.

        Args:
            tolerance: Acceptable deviation from 1.0.

        Returns:
            True if allocations sum to approximately 1.0.
        """
        return abs(self.get_allocation_sum() - 1.0) <= tolerance
