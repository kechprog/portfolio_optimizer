# data_getter.py

from abc import ABC, abstractmethod
from datetime import date
import pandas as pd
from typing import Set, List, Dict, Callable, Tuple, Optional # Added List, Dict, Callable, Tuple, Optional
import time
import concurrent.futures # Added for parallel processing

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
    key = os.getenv("ALPHA_KEY")

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
        data_to_combine: List[pd.DataFrame] = []
        instruments_requiring_api_fetch: List[str] = []

        # Phase 1: Identify instruments requiring API fetch and process directly from cache if possible
        instruments_fully_from_cache: List[str] = []

        for instrument_name in list(instruments): # Iterate over a copy for potential modification
            # Check if the *full* data (not just period) is in cache
            if instrument_name in cache:
                # We'll still filter this later in Phase 3 to be consistent
                # For now, just note it's cached and doesn't need API fetch.
                instruments_fully_from_cache.append(instrument_name)
            else:
                instruments_requiring_api_fetch.append(instrument_name)
        
        # Phase 2: Fetch data from API in parallel for identified instruments
        if instruments_requiring_api_fetch:
            def fetch_and_process_single_api(instrument_to_fetch: str) -> Tuple[str, Optional[pd.DataFrame], Optional[str]]:
                logging.info(f"API Fetch: Attempting for instrument: `{instrument_to_fetch}`")
                timeseries_client = TimeSeries(key, output_format="pandas")
                try:
                    raw_df_from_api, _ = timeseries_client.get_daily_adjusted(instrument_to_fetch, outputsize="full") # type: ignore
                    
                    current_columns = list(raw_df_from_api.columns)
                    mapped_columns = []
                    for col_name in current_columns:
                        processed_col_name = col_name.split('. ', 1)[-1] if '. ' in col_name else col_name
                        mapped_columns.append(col_map.get(processed_col_name.lower(), processed_col_name)) # Ensure key is lower
                    raw_df_from_api.columns = mapped_columns
                    raw_df_from_api.index = pd.to_datetime(raw_df_from_api.index)

                    if raw_df_from_api.isnull().values.any():
                        logging.warning(f"Instrument {instrument_to_fetch}: Fetched data contains NaN values. Will not cache or use.")
                        return instrument_to_fetch, None, "nan_values"
                    
                    # Cache the full, validated DataFrame
                    cache[instrument_to_fetch] = raw_df_from_api.copy() # Store the raw, validated full df
                    logging.info(f"API Fetch: Successfully fetched and cached full validated data for {instrument_to_fetch}.")
                    
                    # The actual filtering for the period will happen in Phase 3 using the cached data
                    return instrument_to_fetch, raw_df_from_api, None # Return full DF for now, filtering in phase 3
                except Exception as e:
                    logging.error(f"API Fetch Error for {instrument_to_fetch}: {e}")
                    return instrument_to_fetch, None, f"api_error: {str(e)}"

            # User has a paid subscription: 70 calls/min.
            # Set max_workers to a higher value, e.g., 15.
            num_workers = min(15, len(instruments_requiring_api_fetch) if instruments_requiring_api_fetch else 1)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                future_to_instrument_map = {
                    executor.submit(fetch_and_process_single_api, instr_name): instr_name 
                    for instr_name in instruments_requiring_api_fetch
                }
                for future in concurrent.futures.as_completed(future_to_instrument_map):
                    instr_name_result = future_to_instrument_map[future]
                    try:
                        _, _, error_msg = future.result() # We only care about errors here; data is in cache
                        if error_msg:
                            logging.warning(f"Adding {instr_name_result} to flawed list due to (API stage): {error_msg}")
                            if instr_name_result not in flawed: flawed.append(instr_name_result)
                        # If no error, data was successfully cached by fetch_and_process_single_api
                    except Exception as exc:
                        logging.error(f"Exception processing result for {instr_name_result} from API future: {exc}")
                        if instr_name_result not in flawed: flawed.append(instr_name_result)
        
        # Phase 3: Process all requested instruments (using cache for both pre-existing and newly fetched data)
        for instrument_name in instruments:
            if instrument_name in flawed: # Already marked as flawed from API fetch stage
                continue

            if instrument_name in cache:
                full_df_from_cache = cache[instrument_name]
                # Now, filter the *cached full data* for the requested period
                df_for_period = full_df_from_cache[(start <= full_df_from_cache.index) & (full_df_from_cache.index <= end)]

                if df_for_period.empty:
                    logging.warning(f"Instrument {instrument_name} (from cache/post-fetch): No data points found within the requested period {start} to {end}. Adding to flawed.")
                    if instrument_name not in flawed: flawed.append(instrument_name)
                    continue # Skip to next instrument
                
                # Apply MultiIndex columns
                df_for_period_multi_indexed = df_for_period.copy() # Avoid SettingWithCopyWarning
                df_for_period_multi_indexed.columns = pd.MultiIndex.from_product(
                    [df_for_period_multi_indexed.columns, [instrument_name.upper()]], # Use uppercase ticker for MultiIndex
                    names=["Field", "Ticker"]
                )
                data_to_combine.append(df_for_period_multi_indexed)
                logging.info(f"Processed {instrument_name} for period {start}-{end} from cache. Shape: {df_for_period_multi_indexed.shape}")

            else: 
                # This instrument was not in cache initially, and API fetch failed (or it wasn't in instruments_requiring_api_fetch)
                # If it failed API fetch, it should already be in 'flawed'. This is a fallback.
                if instrument_name not in flawed:
                    logging.warning(f"Instrument {instrument_name} was not found in cache and was not successfully fetched. Ensure it was queued for API if needed. Adding to flawed.")
                    flawed.append(instrument_name)

        if not data_to_combine:
            logging.info("No data to combine after processing all instruments.")
            return pd.DataFrame(), list(set(flawed)) # Ensure flawed list contains unique items

        try:
            # It's possible data_to_combine contains DFs with completely different date ranges
            # or even non-overlapping indices after individual period filtering.
            # pd.concat should handle this by creating NaNs where data doesn't exist for a given date across all DFs.
            # Sort_index will then sort the combined DataFrame by date.
            final_df = pd.concat(data_to_combine, axis=1).sort_index()
            logging.info(f"Successfully concatenated {len(data_to_combine)} dataframes. Final shape: {final_df.shape}")
        except Exception as e:
            logging.error(f"Error during final pd.concat or sort_index: {e}")
            return pd.DataFrame(), list(set(flawed + [inst_name for df_item in data_to_combine for inst_name in df_item.columns.get_level_values('Ticker').unique() if inst_name.lower() not in flawed]))


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