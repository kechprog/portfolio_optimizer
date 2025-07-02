# data_getter.py
import logging
import pandas as pd
from typing import Set, List, Dict, Callable, Tuple, Optional
import os
import sys
from dotenv import load_dotenv
import aiohttp
import asyncio

logger = logging.getLogger(__name__)

def _get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS  # type: ignore
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def _create_fetcher() -> Callable[[Set[str], pd.Timestamp, pd.Timestamp], Tuple[pd.DataFrame, List[str]]]:
    # Load .env file from the correct location (works in both dev and compiled)
    env_path = _get_resource_path('.env')
    load_dotenv(env_path)

    cache: Dict[str, pd.DataFrame] = {}
    key = os.getenv("ALPHA_KEY")


    async def fetch_ticker_data(session: aiohttp.ClientSession, ticker: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """Fetch data for a single ticker asynchronously"""
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "apikey": key,
            "outputsize": "full",
            "datatype": "json"
        }
        
        try:
            logger.info(f"Fetching data for {ticker} from API...")
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"API Error for {ticker}: HTTP {response.status}")
                    return None, ticker
                
                data = await response.json()
                
                # Check for API error messages
                if "Error Message" in data:
                    logger.error(f"API Error for {ticker}: {data['Error Message']}")
                    return None, ticker
                elif "Note" in data:
                    logger.error(f"API Rate Limit for {ticker}: {data['Note']}")
                    return None, ticker
                
                # Extract time series data
                time_series_key = "Time Series (Daily)"
                if time_series_key not in data:
                    logger.error(f"No time series data found for {ticker}")
                    return None, ticker
                
                time_series = data[time_series_key]
                
                # Convert to DataFrame
                df_data = []
                for date_str, daily_data in time_series.items():
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
                
                df = pd.DataFrame(df_data)
                df.set_index('date', inplace=True)
                df.sort_index(inplace=True)
                
                # Validate for NaNs
                if df.isnull().values.any():
                    logger.warning(f"Instrument {ticker}: Fetched data contains NaN values")
                    return None, ticker
                
                logger.info(f"Successfully fetched data for {ticker}")
                return df, None
                
        except asyncio.TimeoutError:
            logger.error(f"Timeout error for {ticker}")
            return None, ticker
        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e}", exc_info=True)
            return None, ticker

    async def fetch_all_tickers(tickers: List[str]) -> Tuple[Dict[str, pd.DataFrame], List[str]]:
        """Fetch data for all tickers concurrently"""
        results = {}
        flawed = []
        
        # Create session with timeout
        timeout = aiohttp.ClientTimeout(total=30)
        connector = aiohttp.TCPConnector(limit=5)  # Limit concurrent connections
        
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            # Create tasks for all tickers
            tasks = [fetch_ticker_data(session, ticker) for ticker in tickers]
            
            # Execute all tasks concurrently
            responses = await asyncio.gather(*tasks)
            
            # Process results
            for ticker, (df, error_ticker) in zip(tickers, responses):
                if df is not None:
                    results[ticker] = df
                else:
                    flawed.append(error_ticker or ticker)
        
        return results, flawed

    def _inner(instruments: Set[str], start: pd.Timestamp, end: pd.Timestamp) -> Tuple[pd.DataFrame, List[str]]:
        flawed: List[str] = []
        data_to_combine: List[pd.DataFrame] = []
        tickers_to_fetch: List[str] = []

        # Check cache first
        for instrument_ticker in instruments:
            if instrument_ticker in cache:
                logger.info(f"Cache hit for: `{instrument_ticker}` (full data)")
                full_instrument_df = cache[instrument_ticker]
                # Filter for the period
                df_for_period = full_instrument_df[(start <= full_instrument_df.index) & (full_instrument_df.index <= end)]
                
                if df_for_period.empty:
                    logger.warning(f"Instrument {instrument_ticker}: No data points found within the requested period")
                    flawed.append(instrument_ticker)
                    continue
                
                df_for_period.columns = pd.MultiIndex.from_product(
                    [df_for_period.columns.tolist(), [instrument_ticker]], 
                    names=["Field", "Ticker"]
                )
                data_to_combine.append(df_for_period)
            else:
                tickers_to_fetch.append(instrument_ticker)

        # Fetch missing tickers asynchronously
        if tickers_to_fetch:
            logger.info(f"Fetching {len(tickers_to_fetch)} tickers from API...")
            
            # Run async fetch
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                fetched_data, fetch_errors = loop.run_until_complete(
                    fetch_all_tickers(tickers_to_fetch)
                )
            finally:
                loop.close()
            
            # Process fetched data
            flawed.extend(fetch_errors)
            
            for ticker, df in fetched_data.items():
                # Cache the full data
                cache[ticker] = df.copy()
                
                # Filter for the requested period
                df_for_period = df[(start <= df.index) & (df.index <= end)]
                
                if df_for_period.empty:
                    logger.warning(f"Instrument {ticker}: No data points found within the requested period")
                    flawed.append(ticker)
                    continue
                
                df_for_period.columns = pd.MultiIndex.from_product(
                    [df_for_period.columns.tolist(), [ticker]], 
                    names=["Field", "Ticker"]
                )
                data_to_combine.append(df_for_period)
                logger.info(f"Processed {ticker} for period. Shape: {df_for_period.shape}")

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