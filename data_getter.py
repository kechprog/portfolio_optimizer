# data_getter.py

from abc import ABC, abstractmethod
from datetime import date
import pandas as pd
from typing import Set, List, Dict, Callable, Tuple, Optional # Added List, Dict, Callable, Tuple, Optional
import time
# import concurrent.futures # Removed as we are reverting to sequential

# For yfinance
import yfinance as yf
import os
from dotenv import load_dotenv
from alpha_vantage.timeseries import TimeSeries

class DataGetter(ABC):
    """Abstract base class for data getters with caching removed"""
    
    @classmethod
    @abstractmethod
    def fetch(cls,
              instruments: Set[str],
              start_date: date,
              end_date: date,
              include_dividends: bool = False,
              interval: str = "1d"
             ) -> pd.DataFrame:
        """
        Fetches financial data for the given instruments and date range
        
        Args:
            instruments: Set of instrument tickers
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            include_dividends: Whether to include dividend data
            
        Returns:
            DataFrame with (Field, Ticker) MultiIndex columns
        """
        pass


class YahooFinanceDataGetter(DataGetter):
    """
    Yahoo Finance data getter without caching. 
    Explicitly sets auto_adjust=False to return raw prices.
    """
    
    @classmethod
    def fetch(cls,
              instruments: Set[str],
              start_date: date,
              end_date: date,
              include_dividends: bool = False,
              interval: str = "1d"
             ) -> pd.DataFrame:
        
        if not instruments:
            print("INFO: No instruments provided to fetch. Returning empty DataFrame.")
            return pd.DataFrame()
        
        print(f"INFO: Fetching data via YahooFinance for: {instruments} "
              f"from {start_date} to {end_date} (interval: {interval}, "
              f"dividends: {include_dividends})")
        
        try:
            # Fetch raw data without adjustments
            raw_data = yf.download(
                sorted(list(instruments)),
                start=start_date,
                end=end_date + pd.Timedelta(days=1),  # Ensure end_date included
                interval=interval,
                progress=False,
                auto_adjust=False,  # Get raw prices, not adjusted
                actions=include_dividends,
                ignore_tz=True
            )

            # When include_dividends is True, we need to adjust prices by adding dividends
            if include_dividends and not raw_data.empty:
                if isinstance(raw_data.columns, pd.MultiIndex):
                    # Handle multi-index case
                    for col in raw_data.columns.levels[1]:
                        if ('Dividends', col) in raw_data.columns:
                            # Apply dividends by adjusting prices
                            dividends = raw_data[('Dividends', col)].fillna(0)
                            closes = raw_data[('Close', col)].copy()
                            # Start with most recent date and work backward
                            for i in reversed(range(len(dividends))):
                                if i > 0 and dividends.iloc[i] > 0:
                                    # Adjust all previous prices by the dividend factor
                                    dividend_factor = 1.0 + dividends.iloc[i] / closes.iloc[i]
                                    closes.iloc[:i] *= dividend_factor
                            # Replace close prices with adjusted values that include dividends
                            raw_data[('Close', col)] = closes
                else:
                    # Handle single index case (single instrument)
                    if 'Dividends' in raw_data.columns:
                        # Apply dividends by adjusting prices
                        dividends = raw_data['Dividends'].fillna(0)
                        closes = raw_data['Close'].copy()
                        # Start with most recent date and work backward
                        for i in reversed(range(len(dividends))):
                            if i > 0 and dividends.iloc[i] > 0:
                                # Adjust all previous prices by the dividend factor
                                dividend_factor = 1.0 + dividends.iloc[i] / closes.iloc[i]
                                closes.iloc[:i] *= dividend_factor
                        # Replace close prices with adjusted values that include dividends
                        raw_data['Close'] = closes
        except Exception as e:
            print(f"ERROR: Failed to fetch data from Yahoo Finance: {e}")
            return pd.DataFrame()

        if raw_data.empty:
            print("INFO: No data returned from Yahoo Finance")
            return pd.DataFrame()
        
        # Process columns into consistent MultiIndex format
        multi_data = pd.DataFrame()
        
        if isinstance(raw_data.columns, pd.MultiIndex):
            # Already in multiindex format
            multi_data = raw_data.copy()
        else:
            # Single instrument needs conversion to multiindex
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if col in raw_data.columns:
                    multi_data[(col, instruments[0])] = raw_data[col]
            
        # Filter to required columns
        req_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        if include_dividends and 'Dividends' in multi_data.columns.get_level_values(0):
            req_cols.append('Dividends')
            
        filtered_data = multi_data.reindex(columns=req_cols, level=0)
        
        # Ensure date index is clean
        filtered_data.index.name = 'Date'
        return filtered_data.sort_index()



from typing import Callable, Tuple, Set, List, Dict
import logging
def _create_fetcher() -> Callable[[Set[str], pd.Timestamp, pd.Timestamp], Tuple[pd.DataFrame, List[str]]]:
    load_dotenv()

    cache: Dict[str, pd.DataFrame] = {} # Stores full, validated dataframes from API
    # key = os.getenv("ALPHA_KEY")
    key = "GW7UT97X1WGGEYP7"

    col_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "adjusted close": "AdjClose",
        "volume": "Volume",
        "dividend amount": "DivedentAmount",
        "split coefficient": "SplitCoef"
    }

    def _inner(instruments: Set[str], start: pd.Timestamp, end: pd.Timestamp) -> Tuple[pd.DataFrame, List[str]]:
        flawed: List[str] = []
        data_to_combine: List[pd.DataFrame] = [] # Renamed from 'ok' for clarity with original sequential logic

        for instrument_ticker in instruments: # Uppercase from AlphaVantageDataGetter
            # The specific instrument name being processed (original case potentially, if mapping were used)
            # However, AlphaVantageDataGetter passes uppercase strings from self._instruments.
            # So, instrument_ticker is an uppercase string here.
            
            df_for_period: Optional[pd.DataFrame] = None # Holds the data for the specific instrument and period

            # Check cache first (for the full, un-period-filtered data)
            if instrument_ticker in cache:
                logging.info(f"Cache hit for: `{instrument_ticker}` (full data)")
                full_instrument_df = cache[instrument_ticker]
                # Filter for the period
                df_for_period = full_instrument_df[(start <= full_instrument_df.index) & (full_instrument_df.index <= end)]
            else:
                logging.info(f"Cache miss for: `{instrument_ticker}`. Fetching from API.")
                timeseries_client = TimeSeries(key, output_format="pandas")
                try:
                    # Fetch full data
                    raw_df_from_api, _ = timeseries_client.get_daily_adjusted(instrument_ticker, outputsize="full") # type: ignore
                    
                    # Process columns
                    current_columns = list(raw_df_from_api.columns)
                    mapped_columns = []
                    for col_name in current_columns:
                        processed_col_name = col_name.split('. ', 1)[-1] if '. ' in col_name else col_name
                        mapped_columns.append(col_map.get(processed_col_name.lower(), processed_col_name))
                    raw_df_from_api.columns = mapped_columns
                    raw_df_from_api.index = pd.to_datetime(raw_df_from_api.index)

                    # Validate for NaNs in the raw fetched data
                    if raw_df_from_api.isnull().values.any():
                        logging.warning(f"Instrument {instrument_ticker}: Fetched data contains NaN values. Will not cache or use.")
                        flawed.append(instrument_ticker)
                        continue # Move to the next instrument

                    # Cache the full, validated DataFrame
                    cache[instrument_ticker] = raw_df_from_api.copy()
                    logging.info(f"API Fetch: Successfully fetched and cached full validated data for {instrument_ticker}.")
                    
                    # Now, filter the newly fetched data for the requested period
                    df_for_period = raw_df_from_api[(start <= raw_df_from_api.index) & (raw_df_from_api.index <= end)]

                except Exception as e:
                    logging.error(f"API Fetch Error for {instrument_ticker}: {e}")
                    flawed.append(instrument_ticker)
                    continue # Move to the next instrument
            
            # At this point, df_for_period should be the data for the current instrument, filtered for the period.
            # It could be None if an error occurred during fetch for a cache miss.
            if df_for_period is None : # Should be caught by continue statements above, but as a safeguard
                 if instrument_ticker not in flawed: # Ensure it's marked flawed if not already
                    logging.warning(f"Instrument {instrument_ticker}: df_for_period is None unexpectedly. Marking as flawed.")
                    flawed.append(instrument_ticker)
                 continue

            # Check if data for the period is empty
            if df_for_period.empty:
                logging.warning(f"Instrument {instrument_ticker}: No data points found within the requested period {start} to {end} (after cache/fetch).")
                if instrument_ticker not in flawed: # Not an API error, but no data for period
                    flawed.append(instrument_ticker)
                continue # Move to the next instrument
            
            # Apply MultiIndex columns
            # instrument_ticker is already uppercase as it comes from AlphaVantageDataGetter's instruments set
            df_for_period.columns = pd.MultiIndex.from_product(
                [df_for_period.columns, [instrument_ticker]], # Ticker in MultiIndex is uppercase
                names=["Field", "Ticker"]
            )
            data_to_combine.append(df_for_period)
            logging.info(f"Processed {instrument_ticker} for period {start}-{end}. Shape: {df_for_period.shape}")

        if not data_to_combine:
            logging.info("No data to combine after processing all instruments.")
            return pd.DataFrame(), list(set(flawed))

        try:
            final_df = pd.concat(data_to_combine, axis=1).sort_index()
            logging.info(f"Successfully concatenated {len(data_to_combine)} dataframes. Final shape: {final_df.shape}")
        except Exception as e:
            logging.error(f"Error during final pd.concat or sort_index: {e}")
            # Attempt to list all tickers that were meant to be combined, for better error reporting
            involved_tickers = set()
            for df_item in data_to_combine:
                if isinstance(df_item.columns, pd.MultiIndex) and 'Ticker' in df_item.columns.names:
                    involved_tickers.update(df_item.columns.get_level_values('Ticker').unique())
            return pd.DataFrame(), list(set(flawed + list(involved_tickers)))

        return final_df, list(set(flawed))

    return _inner


class AlphaVantageDataGetter(DataGetter):
    av_fetcher =  _create_fetcher()
    @classmethod
    def fetch(cls,
            instruments: Set[str],
              start_date: date,
              end_date: date,
              include_dividends: bool = False,
              interval: str = "1d"
            ) -> Tuple[pd.DataFrame, List[str]]:
        return cls.av_fetcher(instruments, pd.to_datetime(start_date), pd.to_datetime(end_date))