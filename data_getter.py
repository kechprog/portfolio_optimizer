# data_getter.py
import logging
import pandas as pd
from typing import Set, List, Dict, Callable, Tuple, Optional
import os
import sys
from dotenv import load_dotenv
from alpha_vantage.timeseries import TimeSeries

logger = logging.getLogger(__name__)

def _get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def _create_fetcher() -> Callable[[Set[str], pd.Timestamp, pd.Timestamp], Tuple[pd.DataFrame, List[str]]]:
    # Load .env file from the correct location (works in both dev and compiled)
    env_path = _get_resource_path('.env')
    load_dotenv(env_path)

    cache: Dict[str, pd.DataFrame] = {}
    key = os.getenv("ALPHA_KEY")

    col_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "adjusted close": "AdjClose",
        "volume": "Volume",
        "dividend amount": "DividendAmount", # Corrected typo
        "split coefficient": "SplitCoef"
    }

    def _inner(instruments: Set[str], start: pd.Timestamp, end: pd.Timestamp) -> Tuple[pd.DataFrame, List[str]]:
        flawed: List[str] = []
        data_to_combine: List[pd.DataFrame] = []

        for instrument_ticker in instruments: # Expects uppercase tickers
            df_for_period: Optional[pd.DataFrame] = None

            if instrument_ticker in cache:
                logger.info(f"Cache hit for: `{instrument_ticker}` (full data)")
                full_instrument_df = cache[instrument_ticker]
                # Filter for the period
                df_for_period = full_instrument_df[(start <= full_instrument_df.index) & (full_instrument_df.index <= end)]
            else:
                logger.info(f"Cache miss for: `{instrument_ticker}`. Fetching from API.")
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

                    # Validate for NaNs in the raw fetched data BEFORE caching
                    if raw_df_from_api.isnull().values.any():
                        logger.warning(f"Instrument {instrument_ticker}: Fetched data contains NaN values. Will not cache or use.")
                        flawed.append(instrument_ticker)
                        continue # Move to the next instrument

                    # Cache the full, validated DataFrame
                    cache[instrument_ticker] = raw_df_from_api.copy()
                    logger.info(f"API Fetch: Successfully fetched and cached full validated data for {instrument_ticker}.")
                    
                    # Now, filter the newly fetched data for the requested period
                    df_for_period = raw_df_from_api[(start <= raw_df_from_api.index) & (raw_df_from_api.index <= end)]

                except Exception as e:
                    logger.error(f"API Fetch Error for {instrument_ticker}: {e}", exc_info=True)
                    flawed.append(instrument_ticker)
                    continue # Move to the next instrument
            
            if df_for_period is None : 
                 if instrument_ticker not in flawed: 
                    logger.warning(f"Instrument {instrument_ticker}: df_for_period is None unexpectedly after cache/fetch logic. Marking as flawed.")
                    flawed.append(instrument_ticker)
                 continue

            if df_for_period.empty:
                logger.warning(f"Instrument {instrument_ticker}: No data points found within the requested period {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')} (after cache/fetch).")
                if instrument_ticker not in flawed: # Not an API error, but no data for period
                    flawed.append(instrument_ticker)
                continue 
            
            df_for_period.columns = pd.MultiIndex.from_product(
                [df_for_period.columns, [instrument_ticker]], 
                names=["Field", "Ticker"]
            )
            data_to_combine.append(df_for_period)
            logger.info(f"Processed {instrument_ticker} for period {start.strftime('%Y-%m-%d')}-{end.strftime('%Y-%m-%d')}. Shape: {df_for_period.shape}")

        if not data_to_combine:
            logger.info("No data to combine after processing all instruments.")
            return pd.DataFrame(), list(set(flawed))

        try:
            # Concatenate along columns (axis=1)
            final_df = pd.concat(data_to_combine, axis=1).sort_index()
            logger.info(f"Successfully concatenated {len(data_to_combine)} dataframes. Final shape: {final_df.shape}")
        except Exception as e:
            logger.error(f"Error during final pd.concat or sort_index: {e}", exc_info=True)
            involved_tickers = set()
            for df_item in data_to_combine:
                if isinstance(df_item.columns, pd.MultiIndex) and 'Ticker' in df_item.columns.names:
                    involved_tickers.update(df_item.columns.get_level_values('Ticker').unique())
            return pd.DataFrame(), list(set(flawed + list(involved_tickers)))

        return final_df, list(set(flawed))

    return _inner

av_fetcher = _create_fetcher()