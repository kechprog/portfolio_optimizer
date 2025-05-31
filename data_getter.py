# data_getter.py

from abc import ABC, abstractmethod
from datetime import date
import pandas as pd
from typing import Set
import time

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
# TODO: add other fetchers?
def _create_fetcher() -> Callable[[Set[str], pd.Timestamp, pd.Timestamp], Tuple[pd.DataFrame, List[str]]]:
    load_dotenv()

    cache: Dict[str, pd.DataFrame] = {}
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
        flawed = []
        ok = []
        for i in instruments:
            f: pd.DataFrame
            if i in cache and start in cache[i].index and end in cache[i].index:
                logging.info(f"Got cache hit on: `{i}`")
                f = cache[i]
            else:
                logging.info(f"didn't get a cache hit on: `{i}`")
                t = TimeSeries(key, output_format="pandas")

                try:
                    f, _ = t.get_daily_adjusted(   # type: ignore
                        i, outputsize="full")
                except Exception as e:
                    flawed.append(i)
                    continue

                f.columns = list(map(lambda c: col_map[c[3:]], f.columns))
                f.index = pd.to_datetime(f.index)

                cache[i] = f

            # TODO: add verification for time frame correctness
            f = f[(start <= f.index) & (f.index <= end)]
            f.columns = pd.MultiIndex.from_product(
                [f.columns, [i.upper()]],
                names=["Field", "Ticker"]
            )
            ok.append(f)

        return (
            pd.concat(ok, axis=1).sort_index(),
            flawed
        )

    return _inner


av_fetcher = _create_fetcher()


class AlphaVantageDataGetter(DataGetter):
    @classmethod
    def fetch(cls,
            instruments: Set[str],
              start_date: date,
              end_date: date,
              include_dividends: bool = False,
              interval: str = "1d"
            ) -> pd.DataFrame:
        return av_fetcher(instruments, pd.to_datetime(start_date), pd.to_datetime(end_date))[0]