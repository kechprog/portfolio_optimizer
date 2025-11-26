"""
Base allocator classes and portfolio data structures.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

import pandas as pd


@dataclass
class PortfolioSegment:
    """
    Represents a time segment of a portfolio with fixed allocations.

    Attributes:
        start_date: The start date of this segment (inclusive).
        end_date: The end date of this segment (exclusive).
        allocations: A dictionary mapping ticker symbols to their weights (0.0 to 1.0).
    """
    start_date: date
    end_date: date
    allocations: Dict[str, float]

    def __post_init__(self):
        if self.end_date <= self.start_date:
            raise ValueError(
                f"end_date ({self.end_date}) must be after start_date ({self.start_date})"
            )


@dataclass
class Portfolio:
    """
    Represents a portfolio with time-varying allocations across segments.

    Attributes:
        segments: List of portfolio segments, each with its own date range and allocations.
    """
    segments: List[PortfolioSegment] = field(default_factory=list)

    def append_segment(
        self,
        start_date: date,
        end_date: date,
        allocations: Dict[str, float]
    ) -> None:
        """
        Appends a new segment to the portfolio.

        Args:
            start_date: The start date of the segment.
            end_date: The end date of the segment.
            allocations: Dictionary mapping tickers to weights.
        """
        segment = PortfolioSegment(
            start_date=start_date,
            end_date=end_date,
            allocations=allocations.copy()
        )
        self.segments.append(segment)

    def get_segment_for_date(self, query_date: date) -> Optional[PortfolioSegment]:
        """
        Returns the segment active on a given date.

        Args:
            query_date: The date to query.

        Returns:
            The active PortfolioSegment or None if no segment covers this date.
        """
        for segment in self.segments:
            # Use <= for end_date to match original app behavior (inclusive end)
            if segment.start_date <= query_date <= segment.end_date:
                return segment
        return None

    def get_all_tickers(self) -> Set[str]:
        """
        Returns all unique tickers across all segments.

        Returns:
            Set of ticker symbols.
        """
        tickers: Set[str] = set()
        for segment in self.segments:
            tickers.update(segment.allocations.keys())
        return tickers

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializes the portfolio to a dictionary.

        Returns:
            Dictionary representation of the portfolio.
        """
        return {
            "segments": [
                {
                    "start_date": seg.start_date.isoformat(),
                    "end_date": seg.end_date.isoformat(),
                    "allocations": seg.allocations.copy()
                }
                for seg in self.segments
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Portfolio":
        """
        Creates a Portfolio from a dictionary representation.

        Args:
            data: Dictionary with portfolio data.

        Returns:
            Portfolio instance.
        """
        portfolio = cls()
        for seg_data in data.get("segments", []):
            portfolio.append_segment(
                start_date=date.fromisoformat(seg_data["start_date"]),
                end_date=date.fromisoformat(seg_data["end_date"]),
                allocations=seg_data["allocations"]
            )
        return portfolio


# Type aliases for callback functions
ProgressCallback = Callable[[str, int, int], Coroutine[Any, Any, None]]
PriceFetcher = Callable[[str, date, date], Coroutine[Any, Any, pd.DataFrame]]


class Allocator(ABC):
    """
    Abstract base class for all portfolio allocators.

    Allocators are responsible for computing portfolio allocations
    based on historical data and various strategies.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Returns the name of this allocator instance.

        Returns:
            The allocator's name.
        """
        pass

    @abstractmethod
    def get_instruments(self) -> Set[str]:
        """
        Returns the set of instrument tickers used by this allocator.

        Returns:
            Set of ticker symbols.
        """
        pass

    @abstractmethod
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
        Computes the portfolio allocations.

        Args:
            fit_start_date: Start date for the fitting period.
            fit_end_date: End date for the fitting period (start of test period).
            test_end_date: End date for the test/backtest period.
            include_dividends: Whether to include dividends in calculations.
            price_fetcher: Async function to fetch price data.
            progress_callback: Optional async callback for progress updates.

        Returns:
            Portfolio with computed allocations.
        """
        pass

    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """
        Returns the configuration of this allocator for serialization.

        Returns:
            Dictionary containing all configuration needed to recreate this allocator.
        """
        pass

    @classmethod
    @abstractmethod
    def from_config(cls, config: Dict[str, Any]) -> "Allocator":
        """
        Creates an allocator instance from a configuration dictionary.

        Args:
            config: Configuration dictionary.

        Returns:
            Allocator instance.
        """
        pass
