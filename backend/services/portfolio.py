"""
Portfolio performance calculation service.

Computes cumulative returns for a portfolio over time.
"""

import logging
import os
from datetime import date, timedelta
from typing import Any, Callable, Coroutine, Dict, List, Optional

import pandas as pd

from allocators.base import Portfolio, PortfolioSegment, PriceFetcher

logger = logging.getLogger(__name__)


async def compute_performance(
    portfolio: Portfolio,
    fit_end_date: date,
    test_end_date: date,
    include_dividends: bool,
    price_fetcher: PriceFetcher
) -> Dict[str, Any]:
    """
    Calculates portfolio performance over the test period.

    Args:
        portfolio: Portfolio with allocation segments.
        fit_end_date: Start date for performance calculation.
        test_end_date: End date for performance calculation.
        include_dividends: Whether to use adjusted close prices (includes dividends).
        price_fetcher: Async function to fetch price data for a ticker.

    Returns:
        Dictionary with:
            - dates: List of date strings (ISO format)
            - cumulative_returns: List of cumulative return values (as percentages)
    """
    if test_end_date <= fit_end_date:
        return {"dates": [], "cumulative_returns": []}

    # Get all unique tickers from the portfolio
    all_tickers = portfolio.get_all_tickers()

    if not all_tickers:
        return {"dates": [], "cumulative_returns": []}

    # Fetch price data for all tickers
    price_data: Dict[str, pd.DataFrame] = {}
    failed_tickers: List[str] = []
    for ticker in all_tickers:
        try:
            df = await price_fetcher(ticker, fit_end_date, test_end_date)
            if df is not None and not df.empty:
                price_data[ticker] = df
            else:
                failed_tickers.append(ticker)
                logger.warning(f"Failed to fetch price data for {ticker}: Empty or None result")
        except Exception as e:
            # Track and log failed tickers
            failed_tickers.append(ticker)
            logger.warning(f"Failed to fetch price data for {ticker}: {e}")
            continue

    # If ALL tickers failed, raise an exception
    if not price_data and all_tickers:
        raise ValueError(
            f"Failed to fetch price data for all tickers. "
            f"Failed tickers ({len(failed_tickers)}): {', '.join(failed_tickers)}"
        )

    if not price_data:
        return {"dates": [], "cumulative_returns": []}

    # Build a combined price DataFrame
    # Note: price_fetcher returns columns with names: AdjClose, Close (from Alpha Vantage)
    price_column = "AdjClose" if include_dividends else "Close"

    # Collect all price series
    price_series_list: List[pd.Series] = []
    for ticker, df in price_data.items():
        if price_column in df.columns:
            series = df[price_column].rename(ticker)
            price_series_list.append(series)
        elif "Close" in df.columns:
            # Fallback to Close if AdjClose not available
            logger.warning(f"AdjClose not available for {ticker}, using Close instead. Dividends will not be reflected.")
            series = df["Close"].rename(ticker)
            price_series_list.append(series)

    if not price_series_list:
        return {"dates": [], "cumulative_returns": []}

    # Combine into a single DataFrame
    combined_prices = pd.concat(price_series_list, axis=1)
    combined_prices = combined_prices.sort_index()

    # Track missing data before filling
    initial_row_count = len(combined_prices)
    missing_data_count = combined_prices.isna().sum().sum()

    # Forward fill missing values only (never backward fill to avoid look-ahead bias)
    combined_prices = combined_prices.ffill()

    # Drop rows that still have NaN values (typically at the beginning before any data exists)
    combined_prices = combined_prices.dropna()

    # Log warning if significant data was missing or dropped
    rows_dropped = initial_row_count - len(combined_prices)
    if rows_dropped > 0:
        logger.warning(
            f"Dropped {rows_dropped} rows with missing data at the beginning of the series. "
            f"Total missing values before fill: {missing_data_count}"
        )

    # Calculate daily returns
    daily_returns = combined_prices.pct_change()

    # Remove the first row (NaN from pct_change)
    daily_returns = daily_returns.iloc[1:]

    if daily_returns.empty:
        return {"dates": [], "cumulative_returns": []}

    # Calculate portfolio returns for each day
    dates_list: List[str] = []
    cumulative_returns: List[float] = []
    cumulative_factor = 1.0

    # Add initial point at fit_end_date with 0% return (matches original app behavior)
    # This provides the starting reference point for the performance curve
    dates_list.append(fit_end_date.isoformat())
    cumulative_returns.append(0.0)

    for idx, row in daily_returns.iterrows():
        # Get the date (handle both datetime and date index)
        if hasattr(idx, 'date'):
            current_date = idx.date()
        else:
            current_date = idx

        # Find the active segment for this date
        segment = portfolio.get_segment_for_date(current_date)

        if segment is None:
            continue

        # Calculate weighted return for this day
        daily_portfolio_return = 0.0
        total_weight = 0.0

        for ticker, weight in segment.allocations.items():
            if ticker in row.index and pd.notna(row[ticker]):
                daily_portfolio_return += weight * row[ticker]
                total_weight += weight

        # Skip if no valid returns
        if total_weight == 0:
            continue

        # Update cumulative factor
        cumulative_factor *= (1.0 + daily_portfolio_return)

        # Store results (convert to percentage return)
        dates_list.append(current_date.isoformat())
        cumulative_returns.append((cumulative_factor - 1.0) * 100.0)

    return {
        "dates": dates_list,
        "cumulative_returns": cumulative_returns
    }


async def compute_performance_with_segments(
    segments: List[Dict[str, Any]],
    fit_end_date: date,
    test_end_date: date,
    include_dividends: bool,
    price_fetcher: PriceFetcher
) -> Dict[str, Any]:
    """
    Convenience function that accepts segments as dictionaries.

    Args:
        segments: List of segment dictionaries with 'start_date', 'end_date', 'allocations'.
        fit_end_date: Start date for performance calculation.
        test_end_date: End date for performance calculation.
        include_dividends: Whether to use adjusted close prices.
        price_fetcher: Async function to fetch price data.

    Returns:
        Dictionary with dates and cumulative_returns lists.
    """
    portfolio = Portfolio()

    for seg in segments:
        start = seg["start_date"]
        end = seg["end_date"]

        # Handle string dates
        if isinstance(start, str):
            start = date.fromisoformat(start)
        if isinstance(end, str):
            end = date.fromisoformat(end)

        portfolio.append_segment(
            start_date=start,
            end_date=end,
            allocations=seg["allocations"]
        )

    return await compute_performance(
        portfolio=portfolio,
        fit_end_date=fit_end_date,
        test_end_date=test_end_date,
        include_dividends=include_dividends,
        price_fetcher=price_fetcher
    )


def calculate_metrics(
    cumulative_returns: List[float],
    dates: List[str],
    risk_free_rate: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calculates performance metrics from cumulative returns.

    Args:
        cumulative_returns: List of cumulative return percentages.
        dates: List of date strings (ISO format).
        risk_free_rate: Annual risk-free rate as a percentage (e.g., 4.0 for 4%).
            If not provided, defaults to environment variable RISK_FREE_RATE or 4.0.

    Returns:
        Dictionary with performance metrics:
            - total_return: Final cumulative return percentage
            - annualized_return: CAGR (Compound Annual Growth Rate)
            - volatility: Annualized standard deviation of daily returns
            - sharpe_ratio: Risk-adjusted return
            - max_drawdown: Maximum peak-to-trough decline
    """
    if not cumulative_returns or not dates or len(dates) < 2:
        return {
            "total_return": 0.0,
            "annualized_return": 0.0,
            "volatility": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0
        }

    # Total return is the final cumulative return
    total_return = cumulative_returns[-1]

    # Calculate years elapsed using actual calendar days
    start_date = date.fromisoformat(dates[0])
    end_date = date.fromisoformat(dates[-1])
    calendar_days = (end_date - start_date).days
    years_elapsed = calendar_days / 365.25

    # Annualized return (CAGR formula)
    if years_elapsed > 0 and total_return > -100:  # Avoid math errors
        annualized_return = (pow(1 + total_return / 100, 1 / years_elapsed) - 1) * 100
    else:
        annualized_return = 0.0

    # Calculate max drawdown
    peak = cumulative_returns[0]
    max_drawdown = 0.0

    for ret in cumulative_returns:
        if ret > peak:
            peak = ret
        drawdown = peak - ret
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    # Calculate volatility (annualized standard deviation of daily returns)
    daily_volatility = 0.0
    if len(cumulative_returns) > 1:
        # Convert cumulative percentage returns to daily returns using geometric calculation
        daily_returns = []
        for i in range(1, len(cumulative_returns)):
            prev_factor = 1.0 + cumulative_returns[i - 1] / 100.0
            curr_factor = 1.0 + cumulative_returns[i] / 100.0
            if prev_factor != 0:
                daily_ret = ((curr_factor / prev_factor) - 1.0) * 100.0
            else:
                daily_ret = 0.0
            daily_returns.append(daily_ret)

        # Calculate standard deviation (using sample std dev with Bessel's correction)
        if len(daily_returns) > 1:
            mean = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            daily_volatility = variance ** 0.5

    # Annualize volatility (sqrt(252) for trading days)
    annualized_volatility = daily_volatility * (252 ** 0.5)

    # Sharpe Ratio - get risk-free rate from parameter, environment variable, or default
    if risk_free_rate is None:
        risk_free_rate = float(os.environ.get('RISK_FREE_RATE', 4.0))

    if annualized_volatility > 0:
        sharpe_ratio = (annualized_return - risk_free_rate) / annualized_volatility
    else:
        sharpe_ratio = 0.0

    return {
        "total_return": round(total_return, 4),
        "annualized_return": round(annualized_return, 4),
        "volatility": round(annualized_volatility, 4),
        "sharpe_ratio": round(sharpe_ratio, 4),
        "max_drawdown": round(max_drawdown, 4)
    }
