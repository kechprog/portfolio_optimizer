# data_getter.py
import logging
import pandas as pd
from typing import Set, List, Dict, Callable, Tuple, Optional, Any
import os
import sys
import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor, TimeoutError, as_completed
from dotenv import load_dotenv
from alpha_vantage.timeseries import TimeSeries
import pickle
import tempfile
import threading
import platform
import hashlib
from pathlib import Path
import shutil
import uuid

logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_TIMEOUT_PER_INSTRUMENT = 30  # seconds
DEFAULT_MAX_WORKERS = 4
CACHE_FILE_PREFIX = "av_cache_"
CACHE_LOCK_TIMEOUT = 5  # seconds to wait for cache access
MEMORY_CACHE_SIZE = 50  # number of instruments to keep in memory

# Global in-memory cache for ultra-fast access (shared across AsyncDataFetcher instances)
_memory_cache: Dict[str, Tuple[pd.DataFrame, float]] = {}  # {instrument: (dataframe, timestamp)}
_memory_cache_lock = threading.RLock()

def _get_cache_key(instrument: str) -> str:
    """Generate a consistent cache key for an instrument."""
    return instrument.upper().strip()

def _atomic_file_write(file_path: Path, data: pd.DataFrame) -> bool:
    """
    Cross-platform atomic file write using temporary file and rename.
    This prevents partial writes and corruption.
    """
    try:
        # Create parent directory
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temporary file first
        temp_file = file_path.with_suffix(f'.tmp_{uuid.uuid4().hex[:8]}')
        
        with open(temp_file, 'wb') as f:
            pickle.dump(data, f)
        
        # Atomic rename (works on Windows and Unix)
        if platform.system() == 'Windows':
            # On Windows, remove target first if it exists
            if file_path.exists():
                file_path.unlink()
        
        temp_file.rename(file_path)
        return True
        
    except Exception as e:
        # Clean up temp file if it exists
        try:
            if temp_file.exists():
                temp_file.unlink()
        except Exception:
            pass
        return False

def _safe_cache_read(cache_file: Path, instrument: str) -> Optional[pd.DataFrame]:
    """
    Ultra-fast cache read with memory layer and cross-platform file access.
    """
    cache_key = _get_cache_key(instrument)
    
    # First, check in-memory cache (fastest)
    with _memory_cache_lock:
        if cache_key in _memory_cache:
            cached_data, timestamp = _memory_cache[cache_key]
            # Check if memory cache is recent (within 1 hour)
            if time.time() - timestamp < 3600:
                return cached_data.copy()
            else:
                # Remove stale memory cache
                del _memory_cache[cache_key]
    
    # Check disk cache
    if not cache_file.exists():
        return None
    
    try:
        # Simple retry mechanism for cross-platform compatibility
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with open(cache_file, 'rb') as f:
                    data = pickle.load(f)
                
                # Update memory cache for future ultra-fast access
                with _memory_cache_lock:
                    # Limit memory cache size
                    if len(_memory_cache) >= MEMORY_CACHE_SIZE:
                        # Remove oldest entry
                        oldest_key = min(_memory_cache.keys(), 
                                       key=lambda k: _memory_cache[k][1])
                        del _memory_cache[oldest_key]
                    
                    _memory_cache[cache_key] = (data.copy(), time.time())
                
                return data
                
            except (OSError, IOError, pickle.PickleError) as e:
                if attempt == max_retries - 1:
                    # Last attempt failed
                    logger.warning(f"Failed to read cache for {instrument} after {max_retries} attempts: {e}")
                    return None
                # Wait briefly before retry
                time.sleep(0.05 * (attempt + 1))
        
    except Exception as e:
        logger.warning(f"Unexpected error reading cache for {instrument}: {e}")
        return None

def _safe_cache_write(cache_file: Path, data: pd.DataFrame, instrument: str) -> bool:
    """
    Ultra-fast cache write with memory layer and atomic file operations.
    """
    cache_key = _get_cache_key(instrument)
    
    # Always update memory cache first (fastest for subsequent reads)
    with _memory_cache_lock:
        # Limit memory cache size
        if len(_memory_cache) >= MEMORY_CACHE_SIZE:
            # Remove oldest entry
            oldest_key = min(_memory_cache.keys(), 
                           key=lambda k: _memory_cache[k][1])
            del _memory_cache[oldest_key]
        
        _memory_cache[cache_key] = (data.copy(), time.time())
    
    # Write to disk cache atomically
    return _atomic_file_write(cache_file, data)

def _clear_memory_cache(instrument: Optional[str] = None) -> None:
    """Clear memory cache for specific instrument or all instruments."""
    with _memory_cache_lock:
        if instrument:
            cache_key = _get_cache_key(instrument)
            _memory_cache.pop(cache_key, None)
        else:
            _memory_cache.clear()

def _fetch_single_instrument(args: Tuple[str, Optional[str], pd.Timestamp, pd.Timestamp, str]) -> Tuple[str, Optional[pd.DataFrame], Optional[str]]:
    """
    Fetch data for a single instrument in a separate process.
    
    Args:
        args: Tuple of (instrument_ticker, api_key, start_date, end_date, cache_dir)
    
    Returns:
        Tuple of (instrument_ticker, dataframe_or_none, error_message_or_none)
    """
    instrument_ticker, api_key, start_date, end_date, cache_dir = args
    
    # Set up logging for this process
    process_logger = logging.getLogger(f"{__name__}.{instrument_ticker}")
    
    col_map = {
        "open": "Open",
        "high": "High", 
        "low": "Low",
        "close": "Close",
        "adjusted close": "AdjClose",
        "volume": "Volume",
        "dividend amount": "DividendAmount",
        "split coefficient": "SplitCoef"
    }
    
    try:
        # Check for cached data first (memory + disk)
        cache_file = Path(cache_dir) / f"{CACHE_FILE_PREFIX}{instrument_ticker}.pkl"
        cached_df = _safe_cache_read(cache_file, instrument_ticker)
        
        if cached_df is not None:
            process_logger.info(f"Cache hit for: `{instrument_ticker}` (ultra-fast access)")
            # Filter for the requested period
            filtered_df = cached_df[(start_date <= cached_df.index) & (cached_df.index <= end_date)]
            return instrument_ticker, filtered_df, None
        
        # Fetch from API
        process_logger.info(f"Cache miss for: `{instrument_ticker}`. Fetching from API.")
        timeseries_client = TimeSeries(api_key, output_format="pandas")
        
        # Fetch full data with timeout considerations
        raw_df_from_api, _ = timeseries_client.get_daily_adjusted(instrument_ticker, outputsize="full")
        
        # Process columns
        current_columns = list(raw_df_from_api.columns)
        mapped_columns = []
        for col_name in current_columns:
            processed_col_name = col_name.split('. ', 1)[-1] if '. ' in col_name else col_name
            mapped_columns.append(col_map.get(processed_col_name.lower(), processed_col_name))
        
        raw_df_from_api.columns = mapped_columns
        raw_df_from_api.index = pd.to_datetime(raw_df_from_api.index)
        
        # Validate for NaNs
        if raw_df_from_api.isnull().values.any():
            error_msg = f"Fetched data contains NaN values"
            process_logger.warning(f"Instrument {instrument_ticker}: {error_msg}")
            return instrument_ticker, None, error_msg
        
        # Cache the validated DataFrame with atomic write and memory cache
        if _safe_cache_write(cache_file, raw_df_from_api.copy(), instrument_ticker):
            process_logger.info(f"Successfully cached data for {instrument_ticker} (memory + disk)")
        else:
            process_logger.warning(f"Failed to cache data to disk for {instrument_ticker} (memory cache still updated)")
        
        # Filter for the requested period
        filtered_df = raw_df_from_api[(start_date <= raw_df_from_api.index) & (raw_df_from_api.index <= end_date)]
        
        process_logger.info(f"Successfully fetched and processed {instrument_ticker}. Shape: {filtered_df.shape}")
        return instrument_ticker, filtered_df, None
        
    except Exception as e:
        error_msg = f"API Fetch Error: {str(e)}"
        process_logger.error(f"Error fetching {instrument_ticker}: {error_msg}", exc_info=True)
        return instrument_ticker, None, error_msg


class AsyncDataFetcher:
    """
    Asynchronous data fetcher that uses multiprocessing to fetch multiple instruments concurrently.
    """
    
    def __init__(self, 
                 max_workers: Optional[int] = None,
                 timeout_per_instrument: float = DEFAULT_TIMEOUT_PER_INSTRUMENT,
                 cache_dir: Optional[str] = None):
        """
        Initialize the async data fetcher.
        
        Args:
            max_workers: Maximum number of worker processes. Defaults to min(4, cpu_count)
            timeout_per_instrument: Timeout in seconds for each instrument fetch
            cache_dir: Directory for persistent cache. Defaults to temp directory
        """
        # Handle .env file location for both development and compiled executable
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            env_path = os.path.join(sys._MEIPASS, '.env')
        else:
            # Running as script - look in project root
            env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        
        load_dotenv(env_path)
        self.api_key = os.getenv("ALPHA_KEY")
        if not self.api_key:
            raise ValueError("ALPHA_KEY environment variable is required")
        
        self.max_workers = max_workers or min(DEFAULT_MAX_WORKERS, mp.cpu_count())
        self.timeout_per_instrument = timeout_per_instrument
        self.cache_dir = cache_dir or tempfile.mkdtemp(prefix="portfolio_cache_")
        
        # Create cache directory
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"AsyncDataFetcher initialized with {self.max_workers} workers, "
                   f"{timeout_per_instrument}s timeout, cache_dir: {self.cache_dir}")
    
    def fetch_data(self, 
                   instruments: Set[str], 
                   start: pd.Timestamp, 
                   end: pd.Timestamp,
                   progress_callback: Optional[Callable[[str, int, int], None]] = None) -> Tuple[pd.DataFrame, List[str]]:
        """
        Fetch data for multiple instruments concurrently.
        
        Args:
            instruments: Set of instrument tickers (expected to be uppercase)
            start: Start date for data
            end: End date for data
            progress_callback: Optional callback function(ticker, completed, total) for progress updates
        
        Returns:
            Tuple of (combined_dataframe, list_of_flawed_instruments)
        """
        if not instruments:
            logger.info("No instruments to fetch")
            return pd.DataFrame(), []
        
        logger.info(f"Starting async fetch for {len(instruments)} instruments: {instruments}")
        start_time = time.time()
        
        # Prepare arguments for each worker process
        fetch_args = [
            (ticker, self.api_key, start, end, self.cache_dir)
            for ticker in instruments
        ]
        
        successful_data: Dict[str, pd.DataFrame] = {}
        flawed_instruments: List[str] = []
        completed_count = 0
        total_count = len(instruments)
        
        # Use ProcessPoolExecutor for better control and error handling
        try:
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                future_to_ticker = {
                    executor.submit(_fetch_single_instrument, args): args[0] 
                    for args in fetch_args
                }
                
                # Calculate overall timeout (with some buffer)
                overall_timeout = self.timeout_per_instrument * total_count + 30
                
                try:
                    # Process completed tasks as they finish
                    for future in as_completed(future_to_ticker, timeout=overall_timeout):
                        ticker = future_to_ticker[future]
                        completed_count += 1
                        
                        try:
                            # Get result with per-instrument timeout
                            result_ticker, dataframe, error_msg = future.result(timeout=self.timeout_per_instrument)
                            
                            if dataframe is not None and not dataframe.empty:
                                # Add multi-index columns
                                dataframe.columns = pd.MultiIndex.from_product(
                                    [list(dataframe.columns), [result_ticker]], 
                                    names=["Field", "Ticker"]
                                )
                                successful_data[result_ticker] = dataframe
                                logger.info(f"Successfully processed {result_ticker} ({completed_count}/{total_count})")
                            else:
                                flawed_instruments.append(result_ticker)
                                logger.warning(f"No data for {result_ticker}: {error_msg}")
                            
                        except TimeoutError:
                            flawed_instruments.append(ticker)
                            logger.error(f"Timeout fetching {ticker} after {self.timeout_per_instrument}s")
                        
                        except Exception as e:
                            flawed_instruments.append(ticker)
                            logger.error(f"Error processing {ticker}: {e}", exc_info=True)
                        
                        # Call progress callback if provided
                        if progress_callback:
                            try:
                                progress_callback(ticker, completed_count, total_count)
                            except Exception as e:
                                logger.warning(f"Progress callback error: {e}")
                
                except TimeoutError:
                    logger.error(f"Overall timeout after {overall_timeout}s - some instruments may not have completed")
                    # Mark remaining futures as failed
                    for future, ticker in future_to_ticker.items():
                        if not future.done():
                            future.cancel()
                            flawed_instruments.append(ticker)
                            logger.warning(f"Cancelled {ticker} due to overall timeout")
                
                except KeyboardInterrupt:
                    logger.info("Interrupted by user - cancelling remaining tasks")
                    # Cancel all pending futures
                    for future in future_to_ticker.keys():
                        future.cancel()
                    # Mark all remaining as failed
                    for ticker in instruments:
                        if ticker not in successful_data and ticker not in flawed_instruments:
                            flawed_instruments.append(ticker)
                    raise
                    
        except Exception as e:
            logger.error(f"Error in ProcessPoolExecutor: {e}", exc_info=True)
            # If executor fails completely, mark all instruments as failed
            return pd.DataFrame(), list(instruments)
        
        # Combine successful data
        if not successful_data:
            logger.info("No successful data to combine")
            return pd.DataFrame(), flawed_instruments
        
        try:
            # Concatenate along columns (axis=1)
            data_frames = list(successful_data.values())
            final_df = pd.concat(data_frames, axis=1).sort_index()
            
            elapsed_time = time.time() - start_time
            logger.info(f"Successfully fetched {len(successful_data)} instruments in {elapsed_time:.2f}s. "
                       f"Final shape: {final_df.shape}. Failed: {len(flawed_instruments)}")
            
            return final_df, flawed_instruments
            
        except Exception as e:
            logger.error(f"Error during final concatenation: {e}", exc_info=True)
            # Return empty DataFrame and mark all instruments as flawed
            all_tickers = list(instruments)
            return pd.DataFrame(), all_tickers
    
    def clear_cache(self, specific_instruments: Optional[Set[str]] = None, memory_only: bool = False) -> None:
        """
        Clear cache (memory and/or disk).
        
        Args:
            specific_instruments: If provided, only clear cache for these instruments.
                                 If None, clear all cache.
            memory_only: If True, only clear memory cache (ultra-fast operation).
        """
        if specific_instruments:
            # Clear memory cache for specific instruments
            for instrument in specific_instruments:
                _clear_memory_cache(instrument)
                logger.info(f"Cleared memory cache for {instrument}")
            
            if not memory_only:
                # Clear disk cache for specific instruments
                cache_path = Path(self.cache_dir)
                for instrument in specific_instruments:
                    cache_file = cache_path / f"{CACHE_FILE_PREFIX}{instrument}.pkl"
                    if cache_file.exists():
                        try:
                            cache_file.unlink()
                            logger.info(f"Cleared disk cache for {instrument}")
                        except Exception as e:
                            logger.warning(f"Failed to clear disk cache for {instrument}: {e}")
        else:
            # Clear all memory cache
            _clear_memory_cache()
            logger.info("Cleared all memory cache")
            
            if not memory_only:
                # Clear all disk cache files
                cache_path = Path(self.cache_dir)
                for cache_file in cache_path.glob(f"{CACHE_FILE_PREFIX}*.pkl"):
                    try:
                        cache_file.unlink()
                        logger.info(f"Cleared disk cache file: {cache_file.name}")
                    except Exception as e:
                        logger.warning(f"Failed to clear disk cache file {cache_file.name}: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about cache usage for monitoring and optimization.
        """
        memory_stats = {}
        with _memory_cache_lock:
            memory_stats = {
                'memory_cache_size': len(_memory_cache),
                'memory_cache_instruments': list(_memory_cache.keys()),
                'memory_cache_max_size': MEMORY_CACHE_SIZE
            }
        
        # Get disk cache stats
        cache_path = Path(self.cache_dir)
        disk_files = list(cache_path.glob(f"{CACHE_FILE_PREFIX}*.pkl"))
        disk_stats = {
            'disk_cache_files': len(disk_files),
            'disk_cache_instruments': [f.stem.replace(CACHE_FILE_PREFIX, '') for f in disk_files],
            'cache_directory': str(cache_path)
        }
        
        return {
            **memory_stats,
            **disk_stats
        }
    
    def warm_cache(self, instruments: Set[str], start: pd.Timestamp, end: pd.Timestamp) -> None:
        """
        Pre-warm the cache for specified instruments (useful for performance optimization).
        This fetches data in the background without returning it.
        """
        logger.info(f"Warming cache for {len(instruments)} instruments")
        try:
            # Use fetch_data but ignore the result
            self.fetch_data(instruments, start, end)
            logger.info("Cache warming completed")
        except Exception as e:
            logger.warning(f"Cache warming failed: {e}")


def _create_fetcher() -> Callable[[Set[str], pd.Timestamp, pd.Timestamp], Tuple[pd.DataFrame, List[str]]]:
    """
    Create the main data fetcher using the async implementation.
    """
    # Initialize the async fetcher
    async_fetcher = AsyncDataFetcher()
    
    def _fetcher_wrapper(instruments: Set[str], start: pd.Timestamp, end: pd.Timestamp) -> Tuple[pd.DataFrame, List[str]]:
        """
        Wrapper function that maintains the same interface as the original fetcher.
        """
        return async_fetcher.fetch_data(instruments, start, end)
    
    return _fetcher_wrapper


# Create the main fetcher (now using async implementation)
av_fetcher = _create_fetcher()