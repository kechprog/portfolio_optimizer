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


class AlphaVantageDataGetter(DataGetter):
    """Alpha Vantage data getter without caching with concurrent fetching"""
    
    _last_request_time = None  # Simple rate limiting
    
    @classmethod
    def fetch(cls,
              instruments: Set[str],
              start_date: date,
              end_date: date,
              include_dividends: bool = False,
              interval: str = "1d"
             ) -> pd.DataFrame:
        
        # Currently only daily data is supported for AlphaVantage
        if interval != "1d":
            print(f"ERROR: AlphaVantage currently only supports daily data (interval='1d'). "
                  f"Using '1d' instead of {interval}.")
            exit(1)
            interval = "1d"
        
        if not instruments:
            print("INFO: No instruments provided to fetch. Returning empty DataFrame.")
            return pd.DataFrame()
        
        print(f"INFO: Fetching {len(instruments)} instruments with Alpha Vantage "
              f"({start_date} to {end_date}, dividends: {include_dividends})")
        
        # API key setup
        load_dotenv()
        api_key = os.getenv("ALPHA_KEY")
        if not api_key:
            print("ERROR: ALPHA_KEY environment variable not set")
            return pd.DataFrame()
        
        ts = TimeSeries(api_key, output_format='pandas')
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1)
        all_data = []
        
        # Use concurrency for reduced request time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def fetch_instrument(ticker):
            try:
                # Rate limiting: one mutex for all threads
                current_time = time.time()
                if cls._last_request_time:
                    elapsed = current_time - cls._last_request_time
                    if elapsed < 12:  # 5 requests/min = 12 sec/request
                        to_wait = 12 - elapsed
                        time.sleep(to_wait)
                
                # Actually fetch data
                if include_dividends:
                    data, _ = ts.get_daily_adjusted(ticker, outputsize="full")
                    col_map = {
                        "1. open": "Open",
                        "2. high": "High",
                        "3. low": "Low",
                        "4. close": "Close",
                        "5. volume": "Volume",
                        "7. dividend amount": "Dividends"
                    }
                    # For adjusted data, we use the adjusted close price as the close
                    # The API already incorporates the dividend adjustments into the close price
                else:
                    data, _ = ts.get_daily(ticker, outputsize="full")
                    col_map = {
                        "1. open": "Open",
                        "2. high": "High",
                        "3. low": "Low",
                        "4. close": "Close",
                        "5. volume": "Volume"
                    }
                    data["Dividends"] = 0.0
                
                # Process data
                data.rename(columns=col_map, inplace=True)
                data.index = pd.to_datetime(data.index)
                data = data[(data.index >= start_ts) & (data.index < end_ts)]
                
                if data.empty:
                    print(f"  WARNING: No data for {ticker} in date range")
                    return None
                
                # Convert to MultiIndex
                data.columns = pd.MultiIndex.from_product(
                    [data.columns, [ticker.upper()]],
                    names=["Field", "Ticker"]
                )
                
                # Update last request time under lock protection
                cls._last_request_time = time.time()
                return data
                
            except Exception as e:
                print(f"  ERROR fetching {ticker}: {str(e)}")
                return None
        
        # Create thread pool
        with ThreadPoolExecutor(max_workers=15) as executor:
            # Don't use >1 worker as Alpha Vantage free key has strict rate limiting
            futures = {executor.submit(fetch_instrument, ticker): ticker 
                       for ticker in sorted(instruments)}
            
            for i, future in enumerate(as_completed(futures), 1):
                ticker = futures[future]
                print(f"  [{i}/{len(instruments)}] Completed {ticker}")
                result = future.result()
                if result is not None:
                    all_data.append(result)
        
        # Combine all instruments
        if not all_data:
            return pd.DataFrame()
        elif len(all_data) == 1:
            return all_data[0]
        
        # Align all data by date index
        combined_data = pd.concat(all_data, axis=1)
        return combined_data.sort_index()


def compare_dataframes(yahoo_df: pd.DataFrame, alpha_df: pd.DataFrame, tolerance: float = 0.01) -> None:
    """
    Compares two dataframes side by side and reports differences.
    Input dataframes should both have MultiIndex columns (Field, Ticker).
    """
    print("\n" + "="*50)
    print("DATA COMPARISON REPORT")
    print("="*50)
    
    # Check if either is empty
    if yahoo_df.empty or alpha_df.empty:
        print("ERROR: One or both dataframes are empty")
        print(f"- Yahoo data empty: {yahoo_df.empty}")
        print(f"- Alpha data empty: {alpha_df.empty}")
        return

    # Find common dates
    common_dates = yahoo_df.index.intersection(alpha_df.index)
    if len(common_dates) == 0:
        print("WARNING: No common dates between datasets")
        return
    
    print(f"\nComparison period: {common_dates.min().date()} to {common_dates.max().date()}")
    print(f"- Common dates count: {len(common_dates)}")
    print(f"- Yahoo-only dates: {len(yahoo_df.index.difference(alpha_df.index))}")
    print(f"- Alpha-only dates: {len(alpha_df.index.difference(yahoo_df.index))}")
    
    # Get unique fields and tickers
    yahoo_fields = yahoo_df.columns.get_level_values(0).unique()
    alpha_fields = alpha_df.columns.get_level_values(0).unique()
    common_fields =  ['Open', 'High', 'Low', 'Close']
    
    # Track overall match status
    all_match = True
    
    print("\nFIELD COMPARISON:")
    for field in sorted(common_fields):
        field_matches = True
        
        print(f"\n{field} Field:")
        for ticker in test_instruments:
            alpha_ticker = ticker.upper()  # Alpha returns uppercase
            
            try:
                y_series = yahoo_df[(field, ticker)].loc[common_dates]
                a_series = alpha_df[(field, alpha_ticker)].loc[common_dates]
                
                # Check if series are identical
                if not y_series.equals(a_series):
                    field_matches = False
                    # Calculate metrics
                    mismatch_count = (abs(y_series - a_series) > tolerance).sum()
                    avg_diff = (y_series - a_series).mean()
                    max_diff = (y_series - a_series).abs().max()
                    
                    if mismatch_count > 0:
                        print(f"  {ticker}: ❌ {mismatch_count} mismatches")
                        print(f"    Avg difference: {avg_diff:.6f}, Max difference: {max_diff:.6f}")
                    
                else:
                    print(f"  {ticker}: ✅ Perfect match")
                    
            except KeyError as e:
                field_matches = False
                print(f"  {ticker}: ⚠️ Missing data - {e}")
        
        if not field_matches:
            all_match = False
    
    # Summary report
    print("\n" + "="*50)
    print("SUMMARY COMPARISON RESULT:")
    if all_match:
        print("✅ PERFECT MATCH ACROSS ALL FIELDS")
    else:
        print("❌ MISMATCHES FOUND IN ONE OR MORE FIELDS")
    
    # Instrument availability comparison
    print("\nINSTRUMENT AVAILABILITY:")
    yahoo_tickers = yahoo_df.columns.get_level_values(1).unique()
    alpha_tickers = alpha_df.columns.get_level_values(1).unique()
    print(f"- Yahoo had {len(yahoo_tickers)} tickers")
    print(f"- Alpha had {len(alpha_tickers)} tickers")
    print(f"- Common: {len(set(yahoo_tickers) & set(alpha_tickers))}")
    print(f"- Yahoo-only: {len(set(yahoo_tickers) - set(alpha_tickers))}")
    print(f"- Alpha-only: {len(set(alpha_tickers) - set(yahoo_tickers))}")

if __name__ == '__main__':
    # Test configuration
    test_instruments = {'F', 'SPY', 'IAU', 'NVDA', 'TLT', 'IEI', 'GM', 'AAPL', 'VGT'}
    start_date = date(2024, 6, 27)
    end_date = date(2025, 5, 27)
    
    print("\n[1/2] Fetching Yahoo Finance data...")
    yahoo_data = YahooFinanceDataGetter.fetch(test_instruments, start_date, end_date)
    
    print("\n[2/2] Fetching Alpha Vantage data...")
    alpha_data = AlphaVantageDataGetter.fetch(test_instruments, start_date, end_date)
    
    # Run comprehensive comparison
    print("\n[3/3] Comparing datasets...")
    compare_dataframes(yahoo_data, alpha_data)