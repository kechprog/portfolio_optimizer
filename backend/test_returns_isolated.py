"""
Isolated test comparing returns computation algorithms.
Uses the same price data for both to isolate computation differences.
"""

import asyncio
from datetime import date
from typing import Dict, List

import pandas as pd

from allocators.base import Portfolio as BackendPortfolio
from services.price_fetcher import get_price_data


async def fetch_test_data():
    """Fetch price data for test tickers."""
    tickers = ["AAPL", "MSFT"]
    start = date(2024, 6, 1)
    end = date(2024, 10, 1)

    price_data = {}
    for ticker in tickers:
        df = await get_price_data(ticker, start, end)
        price_data[ticker] = df

    return price_data, start, end


def compute_returns_original_algorithm(
    price_data: Dict[str, pd.DataFrame],
    segments: List[Dict],
    include_dividends: bool
) -> tuple:
    """
    Replicate the ORIGINAL app's returns computation algorithm.
    From portfolio.py lines 66-126.
    """
    dates_all = []
    values_all = []
    cumulative_factor = 1.0

    for seg in segments:
        start = seg['start_date']
        end = seg['end_date']
        allocs = {t: w for t, w in seg['allocations'].items() if abs(w) > 1e-9}

        if not allocs:
            continue

        # Build price DataFrame for this segment's tickers
        field = 'AdjClose' if include_dividends else 'Close'

        price_series = []
        for ticker in allocs.keys():
            if ticker in price_data:
                df = price_data[ticker]
                if field in df.columns:
                    # Filter to segment date range
                    mask = (df.index.date >= start) & (df.index.date <= end)
                    series = df.loc[mask, field].rename(ticker)
                    price_series.append(series)

        if not price_series:
            continue

        price_df = pd.concat(price_series, axis=1)
        price_df = price_df.ffill().bfill()

        # Calculate returns - THIS IS THE KEY PART
        returns = price_df.pct_change().dropna(how='all')
        returns = returns[returns.index.date >= start]

        if returns.empty:
            continue

        # Apply weights
        weights = pd.Series({col: allocs.get(col, 0.0) for col in returns.columns})
        port_ret = returns.mul(weights, axis=1).sum(axis=1)

        # Cumulative product
        cum_series = (1 + port_ret).cumprod() * cumulative_factor

        # Prepare points - INCLUDES START DATE WITH PRIOR FACTOR
        seg_dates = [start] + [ts.date() for ts in cum_series.index]
        seg_factors = [cumulative_factor] + cum_series.tolist()

        # Convert to percentage returns
        for dt, factor in zip(seg_dates, seg_factors):
            dates_all.append(dt)
            values_all.append((factor - 1.0) * 100.0)

        cumulative_factor = seg_factors[-1] if seg_factors else cumulative_factor

    return dates_all, values_all


def compute_returns_backend_algorithm(
    price_data: Dict[str, pd.DataFrame],
    segments: List[Dict],
    include_dividends: bool,
    fit_end_date: date,
    test_end_date: date
) -> tuple:
    """
    Replicate the BACKEND's returns computation algorithm.
    From services/portfolio.py compute_performance().
    """
    # Get all unique tickers
    all_tickers = set()
    for seg in segments:
        all_tickers.update(seg['allocations'].keys())

    if not all_tickers:
        return [], []

    # Build combined price DataFrame
    field = 'AdjClose' if include_dividends else 'Close'

    price_series_list = []
    for ticker in all_tickers:
        if ticker in price_data:
            df = price_data[ticker]
            if field in df.columns:
                series = df[field].rename(ticker)
                price_series_list.append(series)

    if not price_series_list:
        return [], []

    combined_prices = pd.concat(price_series_list, axis=1)
    combined_prices = combined_prices.sort_index()
    combined_prices = combined_prices.ffill().bfill()

    # Calculate daily returns
    daily_returns = combined_prices.pct_change()
    daily_returns = daily_returns.iloc[1:]  # Remove first NaN row

    if daily_returns.empty:
        return [], []

    # Calculate portfolio returns day by day
    dates_list = []
    cumulative_returns = []
    cumulative_factor = 1.0

    # Add initial point at fit_end_date with 0% return (matches original app behavior)
    dates_list.append(fit_end_date.isoformat())
    cumulative_returns.append(0.0)

    for idx, row in daily_returns.iterrows():
        if hasattr(idx, 'date'):
            current_date = idx.date()
        else:
            current_date = idx

        # Find active segment (use <= for end_date to match original app behavior)
        segment = None
        for seg in segments:
            if seg['start_date'] <= current_date <= seg['end_date']:
                segment = seg
                break

        if segment is None:
            continue

        # Calculate weighted return
        daily_portfolio_return = 0.0
        total_weight = 0.0

        for ticker, weight in segment['allocations'].items():
            if ticker in row.index and pd.notna(row[ticker]):
                daily_portfolio_return += weight * row[ticker]
                total_weight += weight

        if total_weight == 0:
            continue

        # Update cumulative factor
        cumulative_factor *= (1.0 + daily_portfolio_return)

        # Store results
        dates_list.append(current_date.isoformat())
        cumulative_returns.append((cumulative_factor - 1.0) * 100.0)

    return dates_list, cumulative_returns


async def main():
    print("=" * 70)
    print("ISOLATED RETURNS COMPUTATION COMPARISON")
    print("=" * 70)

    # Fetch data
    print("\nFetching price data...")
    price_data, start, end = await fetch_test_data()

    allocations = {"AAPL": 0.6, "MSFT": 0.4}
    include_dividends = True

    segments = [{
        'start_date': start,
        'end_date': end,
        'allocations': allocations
    }]

    print(f"Test period: {start} to {end}")
    print(f"Allocations: {allocations}")
    print(f"Include dividends: {include_dividends}")

    # Show price data info
    for ticker, df in price_data.items():
        print(f"\n{ticker} price data:")
        print(f"  Shape: {df.shape}")
        print(f"  Date range: {df.index.min()} to {df.index.max()}")
        print(f"  Columns: {list(df.columns)}")
        print(f"  First AdjClose: {df['AdjClose'].iloc[0]}")
        print(f"  Last AdjClose: {df['AdjClose'].iloc[-1]}")

    # Compute using ORIGINAL algorithm
    print("\n" + "-" * 70)
    print("ORIGINAL ALGORITHM (from og_app portfolio.py)")
    print("-" * 70)
    dates_orig, values_orig = compute_returns_original_algorithm(
        price_data, segments, include_dividends
    )
    print(f"Total points: {len(dates_orig)}")
    if dates_orig:
        print(f"First: {dates_orig[0]} = {values_orig[0]:.6f}%")
        print(f"Last: {dates_orig[-1]} = {values_orig[-1]:.6f}%")

    # Compute using BACKEND algorithm
    print("\n" + "-" * 70)
    print("BACKEND ALGORITHM (from services/portfolio.py)")
    print("-" * 70)
    dates_back, values_back = compute_returns_backend_algorithm(
        price_data, segments, include_dividends, start, end
    )
    print(f"Total points: {len(dates_back)}")
    if dates_back:
        print(f"First: {dates_back[0]} = {values_back[0]:.6f}%")
        print(f"Last: {dates_back[-1]} = {values_back[-1]:.6f}%")

    # COMPARISON
    print("\n" + "=" * 70)
    print("COMPARISON")
    print("=" * 70)

    # Convert original dates to strings
    dates_orig_str = [d.isoformat() if hasattr(d, 'isoformat') else str(d) for d in dates_orig]

    print(f"\nPoint count: Original={len(dates_orig)}, Backend={len(dates_back)}")
    print(f"Difference: {len(dates_orig) - len(dates_back)} points")

    # Check for the first date issue
    if dates_orig_str and dates_back:
        print(f"\nOriginal first date: {dates_orig_str[0]}")
        print(f"Backend first date: {dates_back[0]}")

        if dates_orig_str[0] != dates_back[0]:
            print("*** FIRST DATE MISMATCH ***")

    # Find value differences
    if dates_orig_str and dates_back:
        orig_dict = dict(zip(dates_orig_str, values_orig))
        back_dict = dict(zip(dates_back, values_back))

        common_dates = sorted(set(dates_orig_str) & set(dates_back))
        print(f"\nCommon dates: {len(common_dates)}")

        if common_dates:
            print("\nFirst 10 common date comparisons:")
            for i, d in enumerate(common_dates[:10]):
                orig_v = orig_dict.get(d, None)
                back_v = back_dict.get(d, None)
                diff = abs(orig_v - back_v) if orig_v and back_v else "N/A"
                print(f"  {d}: Original={orig_v:.6f}%, Backend={back_v:.6f}%, Diff={diff}")

            # Check last values
            print("\nLast 5 common date comparisons:")
            for d in common_dates[-5:]:
                orig_v = orig_dict.get(d, None)
                back_v = back_dict.get(d, None)
                diff = abs(orig_v - back_v) if orig_v and back_v else "N/A"
                print(f"  {d}: Original={orig_v:.6f}%, Backend={back_v:.6f}%, Diff={diff}")

            # Calculate total discrepancy
            total_diff = 0
            max_diff = 0
            max_diff_date = None
            for d in common_dates:
                orig_v = orig_dict.get(d)
                back_v = back_dict.get(d)
                if orig_v is not None and back_v is not None:
                    diff = abs(orig_v - back_v)
                    total_diff += diff
                    if diff > max_diff:
                        max_diff = diff
                        max_diff_date = d

            print(f"\nTotal absolute difference across all common dates: {total_diff:.6f}%")
            print(f"Max single-date difference: {max_diff:.6f}% on {max_diff_date}")

    # Show dates unique to each
    if dates_orig_str and dates_back:
        orig_only = set(dates_orig_str) - set(dates_back)
        back_only = set(dates_back) - set(dates_orig_str)

        if orig_only:
            print(f"\nDates ONLY in Original ({len(orig_only)}):")
            for d in sorted(orig_only)[:5]:
                print(f"  {d} = {orig_dict[d]:.6f}%")

        if back_only:
            print(f"\nDates ONLY in Backend ({len(back_only)}):")
            for d in sorted(back_only)[:5]:
                print(f"  {d} = {back_dict[d]:.6f}%")


if __name__ == "__main__":
    asyncio.run(main())
