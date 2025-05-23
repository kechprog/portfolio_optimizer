# data_getter.py

from abc import ABC, abstractmethod
from datetime import date, timedelta
import pandas as pd
from typing import Set, Dict, Tuple, Type, ClassVar

# For yfinance, if not installed: pip install yfinance
import yfinance as yf

# Define a type for the cache key for clarity
CacheKey = Tuple[frozenset[str], date, date, str]

class DataGetter(ABC):
    """
    Abstract Base Class for data getters.
    Subclasses are expected to manage their own independent caches.
    Fetching is done via a class method.
    """

    # This __init_subclass__ ensures each subclass gets its own _cache dictionary.
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._cache: ClassVar[Dict[CacheKey, pd.DataFrame]] = {}
        # Optional: Define a supported intervals map if it's common
        # cls._supported_intervals_map: ClassVar[Dict[str, str]] = {}

    @classmethod
    def _get_cache_key(cls,
                       instruments: Set[str],
                       start_date: date,
                       end_date: date,
                       interval: str) -> CacheKey:
        """Generates a consistent cache key."""
        # frozenset for instruments ensures hashability and order-independence for the set part
        # interval is lowercased for consistency
        return (frozenset(instruments), start_date, end_date, interval.lower())

    @classmethod
    def clear_cache(cls) -> None:
        """Clears the cache for this specific DataGetter subclass."""
        if hasattr(cls, '_cache') and isinstance(cls._cache, dict):
            cls._cache.clear()
            print(f"INFO: {cls.__name__} cache cleared.")
        else:
            # This should ideally not be reached if __init_subclass__ is working.
            print(f"WARNING: {cls.__name__} does not have a properly initialized _cache to clear.")

    @classmethod
    @abstractmethod
    def fetch(cls,
              instruments: Set[str],
              start_date: date,
              end_date: date,
              interval: str = "1d" # Defaulting to "1d" which yfinance uses for daily
             ) -> pd.DataFrame:
        """
        Fetches financial data for the given instruments and date range.
        Utilizes a cache specific to the DataGetter subclass.

        Args:
            instruments: A set of instrument tickers.
            start_date: The start date for the data (inclusive).
            end_date: The end date for the data (inclusive).
            interval: The interval of the data (e.g., "1d" for daily, "1wk" for weekly, "1mo" for monthly).
                      The implementation for a specific getter should handle mapping common aliases
                      like "d" to its required format e.g., "1d".

        Returns:
            A pandas DataFrame with a DatetimeIndex (named 'Date').
            The columns should include 'Open', 'High', 'Low', 'Close', 'Volume'.
            For multiple instruments, columns are expected to be a MultiIndex, typically
            (Field, Ticker), e.g., ('Open', 'AAPL'), allowing access like df['Open']['AAPL'].
            Returns an empty DataFrame if no instruments are provided, if data cannot be fetched,
            or if the requested fields are not available.
        """
        pass


class YahooFinanceDataGetter(DataGetter):
    """
    DataGetter implementation for fetching data from Yahoo Finance using the yfinance library.
    """
    # _cache is initialized by DataGetter.__init_subclass__
    _supported_intervals_map: ClassVar[Dict[str, str]] = {
        "d": "1d", "1d": "1d",
        "w": "1wk", "1wk": "1wk",
        "m": "1mo", "1mo": "1mo",
        # Add other yfinance intervals as needed: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 5d, 3mo
    }

    @classmethod
    def fetch(cls,
              instruments: Set[str],
              start_date: date,
              end_date: date,
              interval: str = "1d" # Default matches yfinance daily
             ) -> pd.DataFrame:

        if not instruments:
            print("INFO: No instruments provided to fetch. Returning empty DataFrame.")
            return pd.DataFrame()

        normalized_interval = cls._supported_intervals_map.get(interval.lower(), interval.lower())
        cache_key = cls._get_cache_key(instruments, start_date, end_date, normalized_interval)

        if cache_key in cls._cache:
            print(f"INFO: Cache hit for {cls.__name__}: {instruments} from {start_date} to {end_date}, interval '{normalized_interval}'.")
            return cls._cache[cache_key].copy() # Return a copy

        print(f"INFO: Fetching data via {cls.__name__} for: {instruments} from {start_date} to {end_date}, interval '{normalized_interval}'.")

        tickers_list = sorted(list(instruments)) # yfinance takes a list or space-separated string

        try:
            # Fetch data up to the day after end_date to ensure end_date itself is included,
            # then slice to the exact end_date. This is a robust way to handle yfinance's
            # date range behavior, especially across different intervals.
            fetch_end_date = end_date + timedelta(days=1)
            
            raw_data = yf.download(
                tickers_list,
                start=start_date.strftime('%Y-%m-%d'),
                end=fetch_end_date.strftime('%Y-%m-%d'),
                interval=normalized_interval,
                progress=False,   # Disable yfinance progress bar
                actions=False,    # Exclude dividend and stock split actions
                ignore_tz=True,   # Simplifies date handling by ignoring timezone information from yfinance
                                  # This usually means dates are naive or UTC depending on yf version.
                                  # For daily data, it's typically just the date.
                # group_by='ticker' is default, results in (Field, Ticker) MultiIndex for columns
            )
        except Exception as e:
            print(f"ERROR: Failed to fetch data from Yahoo Finance for {instruments} (interval: {normalized_interval}): {e}")
            cls._cache[cache_key] = pd.DataFrame() # Cache empty DF to prevent repeated errors for same request
            return pd.DataFrame()

        if raw_data.empty:
            print(f"INFO: No data returned from Yahoo Finance for {instruments} in the specified range/interval.")
            cls._cache[cache_key] = raw_data.copy()
            return raw_data.copy()

        # Ensure the index is DatetimeIndex and named 'Date'
        if not isinstance(raw_data.index, pd.DatetimeIndex):
            raw_data.index = pd.to_datetime(raw_data.index)
        raw_data.index.name = 'Date'
        
        # Filter data to be strictly within [start_date, end_date] inclusive
        # This is important because we fetched up to end_date + 1 day
        raw_data = raw_data[(raw_data.index.date >= start_date) & (raw_data.index.date <= end_date)]

        if raw_data.empty: # Check again after slicing
            print(f"INFO: No data available for {instruments} within the exact date range [{start_date}, {end_date}].")
            cls._cache[cache_key] = raw_data.copy()
            return raw_data.copy()

        # Standardize output: select specific fields and ensure MultiIndex (Field, Ticker)
        required_fields = ['Open', 'High', 'Low', 'Close', 'Volume']
        processed_data: pd.DataFrame

        if isinstance(raw_data.columns, pd.MultiIndex): # Multiple tickers, or single ticker downloaded as MultiIndex
            # Columns are like ('Open', 'AAPL'), ('Close', 'AAPL'), ...
            # Filter the first level of columns (Fields) to be only the required_fields.
            fields_present = raw_data.columns.levels[0] if len(raw_data.columns.levels) > 0 else raw_data.columns.get_level_values(0)

            fields_to_keep = [field for field in required_fields if field in fields_present]
            
            if not fields_to_keep:
                print(f"WARNING: None of the required fields ({required_fields}) found in fetched data for {instruments}.")
                cls._cache[cache_key] = pd.DataFrame()
                return pd.DataFrame()
            processed_data = raw_data.loc[:, pd.IndexSlice[fields_to_keep, :]] # Selects all tickers for the fields_to_keep
        
        elif len(tickers_list) == 1: # Single ticker, yfinance returns flat columns
            single_ticker = tickers_list[0]
            available_cols = [col for col in required_fields if col in raw_data.columns]
            if not available_cols:
                print(f"WARNING: None of the required fields ({required_fields}) found for single ticker {single_ticker}.")
                cls._cache[cache_key] = pd.DataFrame()
                return pd.DataFrame()
            
            processed_data = raw_data[available_cols]
            # Convert to MultiIndex (Field, Ticker) for consistency
            processed_data.columns = pd.MultiIndex.from_product(
                [processed_data.columns, [single_ticker]],
                names=['Field', 'Ticker']
            )
        else: # Should not happen if tickers_list is not empty and raw_data is not empty
            print(f"WARNING: Unexpected data structure from yfinance for {instruments}.")
            cls._cache[cache_key] = pd.DataFrame()
            return pd.DataFrame()
        
        # Ensure final DataFrame is not empty after column selection
        if processed_data.empty:
            print(f"INFO: Data became empty after selecting required fields for {instruments}.")
            cls._cache[cache_key] = processed_data.copy() # Cache the (empty) processed data
            return processed_data.copy()

        cls._cache[cache_key] = processed_data.copy()
        return processed_data.copy()


if __name__ == '__main__':
    print("--- Testing DataGetter ---")

    # Test YahooFinanceDataGetter
    instruments1 = {'AAPL', 'MSFT'}
    start_dt1 = date(2023, 1, 1)
    end_dt1 = date(2023, 1, 10)

    print(f"\n--- 1. First Fetch (AAPL, MSFT) from {start_dt1} to {end_dt1}, interval 'd' ---")
    df1 = YahooFinanceDataGetter.fetch(instruments1, start_dt1, end_dt1, interval="d")
    print("Fetched DataFrame head:")
    print(df1.head())
    if not df1.empty:
        print("\nDataFrame columns:", df1.columns)
        if isinstance(df1.columns, pd.MultiIndex):
            print("Column names:", df1.columns.names)
            print("Example data for AAPL Open:", df1[('Open', 'AAPL')].head(2) if ('Open','AAPL') in df1 else "N/A")

    print(f"\n--- 2. Second Fetch (AAPL, MSFT) - Should be from cache ---")
    df2 = YahooFinanceDataGetter.fetch(instruments1, start_dt1, end_dt1, interval="d")
    # print(df2.head()) # Verify it's the same if needed

    print(f"\n--- 3. Fetch single instrument (GOOG) from {start_dt1} to {end_dt1} ---")
    df_goog = YahooFinanceDataGetter.fetch({'GOOG'}, start_dt1, end_dt1, interval="1d")
    print("GOOG DataFrame head:")
    print(df_goog.head())
    if not df_goog.empty:
        print("\nGOOG DataFrame columns:", df_goog.columns)

    start_dt2 = date(2023, 2, 1)
    end_dt2 = date(2023, 2, 5)
    print(f"\n--- 4. Fetch different date range (MSFT) from {start_dt2} to {end_dt2} ---")
    df_msft_new_range = YahooFinanceDataGetter.fetch({'MSFT'}, start_dt2, end_dt2)
    print("MSFT (new range) DataFrame head:")
    print(df_msft_new_range.head())

    print("\n--- 5. Clearing YahooFinanceDataGetter cache ---")
    YahooFinanceDataGetter.clear_cache()
    print(f"Cache size after clear: {len(YahooFinanceDataGetter._cache)}")

    print("\n--- 6. Fetch after cache clear (AAPL, MSFT) - Should be from API again ---")
    df3 = YahooFinanceDataGetter.fetch(instruments1, start_dt1, end_dt1, interval="1d")
    # print(df3.head()) # Verify it's fetched again

    print("\n--- 7. Fetch empty instrument set ---")
    df_empty_set = YahooFinanceDataGetter.fetch(set(), start_dt1, end_dt1)
    print(f"DataFrame for empty set is empty: {df_empty_set.empty}")

    print("\n--- 8. Fetch for a non-existent ticker (should be empty or handle gracefully) ---")
    df_bad_ticker = YahooFinanceDataGetter.fetch({'NONEXISTENTTICKER12345'}, start_dt1, end_dt1)
    print(f"DataFrame for non-existent ticker is empty: {df_bad_ticker.empty}")
    print(df_bad_ticker.head())

    print("\n--- 9. Fetch for a very short future period (should be empty) ---")
    future_start = date.today() + timedelta(days=60)
    future_end = date.today() + timedelta(days=65)
    df_future = YahooFinanceDataGetter.fetch({'AAPL'}, future_start, future_end)
    print(f"DataFrame for future period is empty: {df_future.empty}")
    print(df_future.head())
    
    print("\n--- Test Done ---")