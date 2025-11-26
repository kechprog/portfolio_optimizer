"""
MaxSharpe allocator implementation using Modern Portfolio Theory.

Uses PyPortfolioOpt library to compute optimal portfolio weights
that maximize the Sharpe ratio.
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set

import pandas as pd
from pandas.tseries.offsets import DateOffset
from pypfopt import EfficientFrontier, expected_returns, risk_models

from .base import Allocator, Portfolio, PriceFetcher, ProgressCallback


logger = logging.getLogger(__name__)


class MaxSharpeAllocator(Allocator):
    """
    An allocator that uses Modern Portfolio Theory to maximize the Sharpe ratio.

    Uses PyPortfolioOpt library to compute expected returns and covariance
    matrices, then optimizes for maximum Sharpe ratio.
    """

    def __init__(
        self,
        name: str,
        instruments: List[str],
        allow_shorting: bool = False,
        use_adj_close: bool = True,
        update_enabled: bool = False,
        update_interval_value: int = 30,
        update_interval_unit: str = "days"
    ):
        """
        Initializes the MaxSharpeAllocator.

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

    def _calculate_allocations(
        self,
        prices: pd.DataFrame,
        instruments: Set[str]
    ) -> Dict[str, float]:
        """
        Runs PyPortfolioOpt calculations to compute optimal allocations.

        Args:
            prices: DataFrame of historical prices with tickers as columns.
            instruments: Set of instrument tickers to compute allocations for.

        Returns:
            Dictionary mapping tickers to their optimal weights.
        """
        mu = expected_returns.mean_historical_return(
            prices, compounding=True, frequency=252
        )
        S = risk_models.CovarianceShrinkage(prices, frequency=252).ledoit_wolf()

        bounds = self._get_weight_bounds()
        ef = EfficientFrontier(mu, S, weight_bounds=bounds)
        ef.max_sharpe()
        computed_allocations = ef.clean_weights()

        return {
            inst: computed_allocations.get(inst, 0.0)
            for inst in instruments
        }

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

    def _get_update_delta(self) -> timedelta | DateOffset:
        """
        Returns the time delta for rebalancing based on configured interval.

        Returns:
            timedelta or DateOffset representing the rebalancing interval.
        """
        if self._update_interval_unit == "weeks":
            return timedelta(weeks=self._update_interval_value)
        elif self._update_interval_unit == "months":
            return DateOffset(months=self._update_interval_value)
        else:  # days
            return timedelta(days=self._update_interval_value)

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
        Computes the portfolio allocations using MaxSharpe optimization.

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
        portfolio = Portfolio()
        instruments = self.get_instruments()

        if not instruments:
            logger.warning(f"({self._name}) No instruments configured")
            return portfolio

        if test_end_date <= fit_end_date:
            logger.warning(f"({self._name}) test_end_date must be after fit_end_date")
            return portfolio

        if progress_callback:
            await progress_callback(f"Optimizing MaxSharpe for {self._name}...", 0, 1)

        if not self._update_enabled:
            # Single optimization using fit period
            try:
                prices = await self._fetch_prices(
                    price_fetcher, instruments, fit_start_date, fit_end_date
                )
                if prices is None or prices.empty:
                    logger.error(f"({self._name}) No price data available")
                    return portfolio

                allocations = self._calculate_allocations(prices, instruments)
                portfolio.append_segment(
                    start_date=fit_end_date,
                    end_date=test_end_date,
                    allocations=allocations
                )

            except Exception as e:
                logger.error(f"({self._name}) Static allocation failed: {e}", exc_info=True)

            if progress_callback:
                await progress_callback(f"MaxSharpe optimization complete for {self._name}", 1, 1)

            return portfolio

        # Dynamic update enabled - create multiple segments
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

                allocations = self._calculate_allocations(prices, instruments)

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
                    f"Optimizing MaxSharpe for {self._name} (segment {segment_count})...",
                    segment_count,
                    segment_count + 1
                )

            current_date = segment_end_date

        if progress_callback:
            await progress_callback(
                f"MaxSharpe optimization complete for {self._name} ({segment_count} segments)",
                segment_count,
                segment_count
            )

        return portfolio

    def get_config(self) -> Dict[str, Any]:
        """
        Returns the configuration for serialization.

        Returns:
            Dictionary with all configuration needed to recreate this allocator.
        """
        return {
            "type": "max_sharpe",
            "name": self._name,
            "instruments": sorted(list(self._instruments)),
            "allow_shorting": self._allow_shorting,
            "use_adj_close": self._use_adj_close,
            "update_enabled": self._update_enabled,
            "update_interval_value": self._update_interval_value,
            "update_interval_unit": self._update_interval_unit
        }

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "MaxSharpeAllocator":
        """
        Creates a MaxSharpeAllocator from a configuration dictionary.

        Args:
            config: Dictionary with allocator configuration.

        Returns:
            MaxSharpeAllocator instance.
        """
        return cls(
            name=config.get("name", "MaxSharpe Allocator"),
            instruments=config.get("instruments", []),
            allow_shorting=config.get("allow_shorting", False),
            use_adj_close=config.get("use_adj_close", True),
            update_enabled=config.get("update_enabled", False),
            update_interval_value=config.get("update_interval_value", 30),
            update_interval_unit=config.get("update_interval_unit", "days")
        )
