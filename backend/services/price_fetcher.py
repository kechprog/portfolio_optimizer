"""
Price fetcher service with Alpha Vantage API integration and SQLite caching.
"""
import asyncio
import logging
from datetime import date, datetime
from typing import Dict, Any, Optional

import aiohttp
import pandas as pd

from config import ALPHA_VANTAGE_API_KEY
from database import (
    init_database,
    get_cached_price_data,
    store_price_data,
)

logger = logging.getLogger(__name__)

# Module-level shared HTTP session for connection pooling
_http_session: Optional[aiohttp.ClientSession] = None

# Module-level per-ticker locks to prevent race conditions
_ticker_locks: Dict[str, asyncio.Lock] = {}


class PriceFetcherError(Exception):
    """Base exception for price fetcher errors."""
    pass


class APIError(PriceFetcherError):
    """Error from the Alpha Vantage API."""
    pass


class RateLimitError(PriceFetcherError):
    """API rate limit exceeded."""
    pass


class InvalidTickerError(PriceFetcherError):
    """Invalid or unknown ticker symbol."""
    pass


class CacheDateRangeError(PriceFetcherError):
    """Requested start_date is before cached first_date."""
    pass


def get_ticker_lock(ticker: str) -> asyncio.Lock:
    """
    Get or create a lock for a specific ticker to prevent race conditions.

    Args:
        ticker: The stock ticker symbol

    Returns:
        asyncio.Lock for the ticker
    """
    if ticker not in _ticker_locks:
        _ticker_locks[ticker] = asyncio.Lock()
    return _ticker_locks[ticker]


async def get_http_session() -> aiohttp.ClientSession:
    """
    Get or create the shared HTTP session for connection pooling.

    Returns:
        Shared aiohttp.ClientSession instance
    """
    global _http_session
    if _http_session is None or _http_session.closed:
        timeout = aiohttp.ClientTimeout(total=30)
        _http_session = aiohttp.ClientSession(timeout=timeout)
    return _http_session


async def close_http_session() -> None:
    """
    Close the shared HTTP session.
    Should be called on application shutdown.
    """
    global _http_session
    if _http_session is not None and not _http_session.closed:
        await _http_session.close()
        _http_session = None


async def fetch_from_alpha_vantage(ticker: str) -> Dict[str, Any]:
    """
    Fetch all historical daily adjusted data from Alpha Vantage API.

    Args:
        ticker: The stock ticker symbol

    Returns:
        Dictionary of time series data with date strings as keys

    Raises:
        APIError: If the API returns an error
        RateLimitError: If rate limit is exceeded
        InvalidTickerError: If the ticker is invalid
    """
    if not ALPHA_VANTAGE_API_KEY:
        raise APIError("Alpha Vantage API key not configured. Set ALPHA_KEY in .env file.")

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": ticker,
        "apikey": ALPHA_VANTAGE_API_KEY,
        "outputsize": "full",
        "datatype": "json"
    }

    logger.info(f"Fetching data for {ticker} from Alpha Vantage API...")

    try:
        session = await get_http_session()
        async with session.get(url, params=params) as response:
            if response.status != 200:
                raise APIError(f"HTTP {response.status}: Failed to fetch data for {ticker}")

            data = await response.json()

            # Check for API error messages
            if "Error Message" in data:
                raise InvalidTickerError(f"Invalid ticker '{ticker}': {data['Error Message']}")

            if "Note" in data:
                raise RateLimitError(f"API rate limit exceeded: {data['Note']}")

            if "Information" in data:
                # This can also indicate rate limiting
                raise RateLimitError(f"API information: {data['Information']}")

            # Extract time series data
            time_series_key = "Time Series (Daily)"
            if time_series_key not in data:
                raise APIError(f"No time series data found for {ticker}. Response: {list(data.keys())}")

            time_series = data[time_series_key]
            logger.info(f"Successfully fetched {len(time_series)} days of data for {ticker}")

            return time_series

    except asyncio.TimeoutError:
        raise APIError(f"Request timed out for {ticker}")
    except aiohttp.ClientError as e:
        raise APIError(f"Network error fetching {ticker}: {str(e)}")


def parse_time_series_to_dataframe(time_series: Dict[str, Any]) -> pd.DataFrame:
    """
    Convert Alpha Vantage time series data to a pandas DataFrame.

    Args:
        time_series: Dictionary with date strings as keys and OHLCV data as values

    Returns:
        DataFrame with datetime index and columns:
        Open, High, Low, Close, AdjClose, Volume, DividendAmount, SplitCoef
    """
    df_data = []

    for date_str, daily_data in time_series.items():
        try:
            row = {
                'date': pd.to_datetime(date_str),
                'Open': float(daily_data['1. open']),
                'High': float(daily_data['2. high']),
                'Low': float(daily_data['3. low']),
                'Close': float(daily_data['4. close']),
                'AdjClose': float(daily_data['5. adjusted close']),
                'Volume': int(daily_data['6. volume']),
                'DividendAmount': float(daily_data['7. dividend amount']),
                'SplitCoef': float(daily_data['8. split coefficient'])
            }
            df_data.append(row)
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse data for date {date_str}: {e}. Skipping row.")
            continue

    df = pd.DataFrame(df_data)
    df.set_index('date', inplace=True)
    df.sort_index(inplace=True)

    return df


def filter_dataframe_by_date(
    df: pd.DataFrame,
    start_date: date,
    end_date: date
) -> pd.DataFrame:
    """
    Filter DataFrame to only include rows within the date range.

    Args:
        df: DataFrame with datetime index
        start_date: Start date (inclusive)
        end_date: End date (inclusive)

    Returns:
        Filtered DataFrame
    """
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)

    mask = (df.index >= start_ts) & (df.index <= end_ts)
    return df[mask].copy()


async def get_price_data(
    ticker: str,
    start_date: date,
    end_date: date
) -> pd.DataFrame:
    """
    Get price data for a ticker, using cache when possible.

    Caching logic:
    - If ticker not in cache: fetch all, store, return filtered
    - If end_date > cached last_date: refetch all, overwrite, return filtered
    - If start_date < cached first_date: raise CacheDateRangeError
    - Otherwise: return filtered from cache

    Args:
        ticker: The stock ticker symbol
        start_date: Start date for the data (inclusive)
        end_date: End date for the data (inclusive)

    Returns:
        DataFrame with columns: Open, High, Low, Close, AdjClose, Volume, DividendAmount, SplitCoef
        Index is datetime

    Raises:
        CacheDateRangeError: If start_date is before cached first_date
        APIError: If API request fails
        RateLimitError: If rate limit is exceeded
        InvalidTickerError: If ticker is invalid
    """
    # Ensure database is initialized
    await init_database()

    # Acquire per-ticker lock to prevent race conditions
    lock = get_ticker_lock(ticker)
    async with lock:
        # Check cache
        cached = await get_cached_price_data(ticker)

        if cached is None:
            # Not in cache - fetch all data
            logger.info(f"Cache miss for {ticker}, fetching from API...")
            time_series = await fetch_from_alpha_vantage(ticker)

            # Determine date range from fetched data
            dates = sorted(time_series.keys())
            if not dates:
                raise APIError(f"No price data available for {ticker}")
            first_date_fetched = datetime.strptime(dates[0], '%Y-%m-%d').date()
            last_date_fetched = datetime.strptime(dates[-1], '%Y-%m-%d').date()

            # Store in cache
            await store_price_data(ticker, time_series, first_date_fetched, last_date_fetched)

            # Convert to DataFrame and filter
            df = parse_time_series_to_dataframe(time_series)
            return filter_dataframe_by_date(df, start_date, end_date)

        # Check if we need to refetch (end_date is after cached data)
        if end_date > cached['last_date']:
            logger.info(f"Cache stale for {ticker} (cached until {cached['last_date']}, need {end_date}), refetching...")
            time_series = await fetch_from_alpha_vantage(ticker)

            # Determine date range from fetched data
            dates = sorted(time_series.keys())
            if not dates:
                raise APIError(f"No price data available for {ticker}")
            first_date_fetched = datetime.strptime(dates[0], '%Y-%m-%d').date()
            last_date_fetched = datetime.strptime(dates[-1], '%Y-%m-%d').date()

            # Overwrite cache
            await store_price_data(ticker, time_series, first_date_fetched, last_date_fetched)

            # Convert to DataFrame and filter
            df = parse_time_series_to_dataframe(time_series)
            return filter_dataframe_by_date(df, start_date, end_date)

        # Check if start_date is before cached first_date
        if start_date < cached['first_date']:
            raise CacheDateRangeError(
                f"Requested start_date ({start_date}) is before cached first_date ({cached['first_date']}) for {ticker}. "
                f"The Alpha Vantage API returns all available history, so data before {cached['first_date']} does not exist."
            )

        # Cache hit - use cached data
        logger.debug(f"Cache hit for {ticker} ({cached['first_date']} to {cached['last_date']})")
        df = parse_time_series_to_dataframe(cached['data'])
        return filter_dataframe_by_date(df, start_date, end_date)


async def get_multiple_price_data(
    tickers: list[str],
    start_date: date,
    end_date: date,
    max_concurrent: int = 5
) -> tuple[Dict[str, pd.DataFrame], list[str]]:
    """
    Get price data for multiple tickers concurrently.

    Args:
        tickers: List of stock ticker symbols
        start_date: Start date for the data (inclusive)
        end_date: End date for the data (inclusive)
        max_concurrent: Maximum number of concurrent API requests

    Returns:
        Tuple of (results dict, failed tickers list)
        - results: Dictionary mapping ticker to DataFrame
        - failed: List of tickers that failed to fetch
    """
    results: Dict[str, pd.DataFrame] = {}
    failed: list[str] = []

    # Use semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_with_semaphore(ticker: str) -> tuple[str, Optional[pd.DataFrame], Optional[str]]:
        async with semaphore:
            try:
                df = await get_price_data(ticker, start_date, end_date)
                return (ticker, df, None)
            except PriceFetcherError as e:
                logger.warning(f"Error fetching {ticker}: {e}")
                return (ticker, None, str(e))
            except Exception as e:
                logger.error(f"Unexpected error fetching {ticker}: {e}")
                return (ticker, None, str(e))

    # Create tasks for all tickers
    tasks = [fetch_with_semaphore(ticker) for ticker in tickers]

    # Execute all tasks concurrently
    responses = await asyncio.gather(*tasks)

    # Process results
    for ticker, df, error in responses:
        if df is not None:
            results[ticker] = df
        else:
            failed.append(ticker)

    return results, failed
