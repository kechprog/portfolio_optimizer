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


class OptimizationAllocatorBase(Allocator):
    """
    Base class for optimization-based allocators using PyPortfolioOpt.

    Provides common functionality for fetching prices, computing updates,
    and managing portfolio segments. Subclasses implement specific
    optimization strategies via the _optimize() method.
    """

    def __init__(
        self,
        name: str,
        instruments: List[str],
        allow_shorting: bool = False,
        use_adj_close: bool = True,
        update_enabled: bool = False,
        update_interval_value: int = 1,
        update_interval_unit: str = "days"
    ):
        """
        Initializes the OptimizationAllocatorBase.

        Args:
            name: The name of this allocator instance.
            instruments: List of ticker symbols to include in the portfolio.
            allow_shorting: If True, allows negative weights (short positions).
            use_adj_close: If True, uses adjusted close prices; otherwise uses close prices.
            update_enabled: If True, rebalances portfolio at regular intervals.
            update_interval_value: Number of time units between rebalancing.
            update_interval_unit: Time unit for rebalancing ('days', 'weeks', or 'months').
        """
        if not name or not name.strip():
            raise ValueError("Allocator name cannot be empty.")

        self._name = name.strip()
        self._instruments: Set[str] = set()

        # Validate and store instruments
        for ticker in instruments:
            if not isinstance(ticker, str) or not ticker.strip():
                raise ValueError(f"Invalid ticker: {ticker}")
            self._instruments.add(ticker.strip().upper())

        # Validate minimum number of instruments for optimization
        if len(self._instruments) < 2:
            raise ValueError(
                f"Optimization allocator requires at least 2 instruments, got {len(self._instruments)}"
            )

        self._allow_shorting = allow_shorting
        self._use_adj_close = use_adj_close
        self._update_enabled = update_enabled
        self._update_interval_value = update_interval_value
        self._update_interval_unit = update_interval_unit

    @property
    def name(self) -> str:
        """Returns the name of this allocator."""
        return self._name

    def get_instruments(self) -> Set[str]:
        """Returns the set of instrument tickers used by this allocator."""
        return self._instruments.copy()

    def _get_weight_bounds(self) -> tuple:
        """
        Returns the weight bounds for optimization.

        Returns:
            Tuple of (min_weight, max_weight).
        """
        if self._allow_shorting:
            return (-1, 1)
        return (0, 1)

    async def _fetch_prices(
        self,
        price_fetcher: PriceFetcher,
        instruments: Set[str],
        start_date: date,
        end_date: date
    ) -> Optional[pd.DataFrame]:
        """
        Fetches price data for all instruments and combines into a single DataFrame.

        Args:
            price_fetcher: Async function to fetch price data.
            instruments: Set of ticker symbols.
            start_date: Start date for price data.
            end_date: End date for price data.

        Returns:
            DataFrame with tickers as columns and dates as index, or None if fetch failed.
        """
        import logging
        logger = logging.getLogger(__name__)

        price_column = "AdjClose" if self._use_adj_close else "Close"
        prices_list: List[pd.Series] = []

        for ticker in instruments:
            try:
                df = await price_fetcher(ticker, start_date, end_date)
                if df.empty:
                    logger.warning(f"No data returned for {ticker}")
                    continue

                if price_column in df.columns:
                    prices_list.append(df[price_column].rename(ticker))
                elif "Close" in df.columns:
                    # Fallback to Close if AdjClose not available
                    prices_list.append(df["Close"].rename(ticker))
                else:
                    logger.warning(f"No price column found for {ticker}")
                    continue

            except Exception as e:
                logger.error(f"Failed to fetch data for {ticker}: {e}")
                continue

        if not prices_list:
            return None

        # Combine all price series into a single DataFrame
        prices = pd.concat(prices_list, axis=1)
        # Forward fill then backward fill to handle missing data
        prices = prices.ffill().bfill()

        return prices

    def _get_update_delta(self):
        """
        Returns the time delta for rebalancing based on configured interval.

        Returns:
            timedelta or DateOffset representing the rebalancing interval.
        """
        from datetime import timedelta
        from pandas.tseries.offsets import DateOffset

        if self._update_interval_unit == "weeks":
            return timedelta(weeks=self._update_interval_value)
        elif self._update_interval_unit == "months":
            return DateOffset(months=self._update_interval_value)
        else:  # days
            return timedelta(days=self._update_interval_value)

    @abstractmethod
    def _optimize(
        self,
        prices: pd.DataFrame,
        instruments: Set[str]
    ) -> Dict[str, float]:
        """
        Run the specific optimization algorithm.

        Args:
            prices: DataFrame of historical prices with tickers as columns.
            instruments: Set of instrument tickers to compute allocations for.

        Returns:
            Dictionary mapping tickers to their optimal weights.
        """
        pass

    @abstractmethod
    def _get_optimization_name(self) -> str:
        """
        Returns the name of the optimization strategy for progress messages.

        Returns:
            Strategy name (e.g., 'MaxSharpe', 'MinVolatility').
        """
        pass

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
        Computes the portfolio allocations using the optimization strategy.

        Args:
            fit_start_date: Start date for the fitting period.
            fit_end_date: End date for the fitting period (start of test period).
            test_end_date: End date for the test/backtest period.
            include_dividends: Whether to include dividends (affects price column choice).
            price_fetcher: Async function to fetch price data.
            progress_callback: Optional async callback for progress updates.

        Returns:
            Portfolio with computed allocations.
        """
        import logging
        logger = logging.getLogger(__name__)

        portfolio = Portfolio()
        instruments = self.get_instruments()
        optimization_name = self._get_optimization_name()

        if not instruments:
            raise ValueError(f"({self._name}) No instruments configured")

        if test_end_date <= fit_end_date:
            raise ValueError(
                f"test_end_date ({test_end_date}) must be after fit_end_date ({fit_end_date})"
            )

        if progress_callback:
            await progress_callback(f"Optimizing {optimization_name} for {self._name}...", 0, 1)

        if not self._update_enabled:
            # Single optimization using fit period
            try:
                prices = await self._fetch_prices(
                    price_fetcher, instruments, fit_start_date, fit_end_date
                )
                if prices is None or prices.empty:
                    logger.error(f"({self._name}) No price data available")
                    return portfolio

                allocations = self._optimize(prices, instruments)
                portfolio.append_segment(
                    start_date=fit_end_date,
                    end_date=test_end_date,
                    allocations=allocations
                )

            except Exception as e:
                logger.error(f"({self._name}) Static allocation failed: {e}", exc_info=True)

            if progress_callback:
                await progress_callback(f"{optimization_name} optimization complete for {self._name}", 1, 1)

            return portfolio

        # Dynamic update enabled - create multiple segments
        from datetime import timedelta

        delta = self._get_update_delta()
        current_date = fit_end_date
        segment_count = 0

        while current_date < test_end_date:
            try:
                # Fetch prices from fit_start to current_date
                prices = await self._fetch_prices(
                    price_fetcher, instruments, fit_start_date, current_date
                )
                if prices is None or prices.empty:
                    logger.error(f"({self._name}) No price data at {current_date}")
                    break

                allocations = self._optimize(prices, instruments)

            except Exception as e:
                logger.error(
                    f"({self._name}) Dynamic allocation failed at {current_date}: {e}",
                    exc_info=True
                )
                break

            # Calculate segment end date
            if isinstance(delta, timedelta):
                segment_end_date = current_date + delta
            else:
                segment_end_date = (pd.Timestamp(current_date) + delta).date()

            segment_end_date = min(segment_end_date, test_end_date)

            portfolio.append_segment(
                start_date=current_date,
                end_date=segment_end_date,
                allocations=allocations
            )

            segment_count += 1
            if progress_callback:
                await progress_callback(
                    f"Optimizing {optimization_name} for {self._name} (segment {segment_count})...",
                    segment_count,
                    segment_count + 1
                )

            current_date = segment_end_date

        if progress_callback:
            await progress_callback(
                f"{optimization_name} optimization complete for {self._name} ({segment_count} segments)",
                segment_count,
                segment_count
            )

        return portfolio
