"""
Test script to compare returns computation between original app and backend.
Run this to identify discrepancies.
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

import pandas as pd

# Add original app to path
ORIGINAL_APP_PATH = Path(__file__).parent.parent.parent / "portfolio_optimizer"
sys.path.insert(0, str(ORIGINAL_APP_PATH))

# Import from original app
from data_getter import av_fetcher
from portfolio import Portfolio as OriginalPortfolio

# Import from backend
from allocators.base import Portfolio as BackendPortfolio, PortfolioSegment
from services.portfolio import compute_performance
from services.price_fetcher import get_price_data


async def run_comparison():
    """Compare returns between original app and backend."""

    # Test parameters - simple single-segment portfolio
    fit_start = date(2024, 1, 1)
    fit_end = date(2024, 6, 1)
    test_end = date(2024, 10, 1)
    include_dividends = True

    # Simple allocation: 60% AAPL, 40% MSFT
    allocations = {"AAPL": 0.6, "MSFT": 0.4}

    print("=" * 60)
    print("RETURNS COMPUTATION COMPARISON TEST")
    print("=" * 60)
    print(f"Fit period: {fit_start} to {fit_end}")
    print(f"Test period: {fit_end} to {test_end}")
    print(f"Include dividends: {include_dividends}")
    print(f"Allocations: {allocations}")
    print("=" * 60)

    # =========================================
    # ORIGINAL APP COMPUTATION
    # =========================================
    print("\n--- ORIGINAL APP ---")

    # Original Portfolio API: __init__(start_date), append(end_date, allocations)
    original_portfolio = OriginalPortfolio(start_date=fit_end)
    original_portfolio.append(end_date=test_end, allocations=allocations)

    # Get segments
    segments = original_portfolio.get(test_end)
    print(f"Segments: {segments}")

    # Replicate the original app's plot() logic
    dates_original = []
    values_original = []
    cumulative_factor = 1.0

    for seg in segments:
        start = seg['start_date']
        end = seg['end_date']
        allocs = {t: w for t, w in seg['allocations'].items() if abs(w) > 1e-9}

        if not allocs:
            continue

        tickers = {t.upper() for t in allocs}
        print(f"Fetching data for segment {start} to {end}, tickers: {tickers}")

        try:
            raw_df, failed = av_fetcher(
                tickers,
                pd.to_datetime(start),
                pd.to_datetime(end)
            )
            if failed:
                print(f"Failed tickers: {failed}")
        except Exception as e:
            print(f"Error fetching data: {e}")
            continue

        field = 'AdjClose' if include_dividends else 'Close'
        try:
            price_df = raw_df.xs(field, level='Field', axis=1, drop_level=True)
        except Exception as e:
            print(f"Error extracting {field}: {e}")
            continue

        print(f"Price data shape: {price_df.shape}")
        print(f"Price data head:\n{price_df.head()}")

        price_df = price_df.ffill().bfill()
        returns = price_df.pct_change().dropna(how='all')
        returns = returns[returns.index.date >= start]

        print(f"Returns shape: {returns.shape}")
        print(f"Returns head:\n{returns.head()}")

        if returns.empty:
            continue

        weights = pd.Series({col: allocs.get(col, 0.0) for col in returns.columns})
        port_ret = returns.mul(weights, axis=1).sum(axis=1)

        print(f"Portfolio returns head:\n{port_ret.head()}")

        cum_series = (1 + port_ret).cumprod() * cumulative_factor

        # Prepare points
        seg_dates = [start] + [ts.date() for ts in cum_series.index]
        seg_factors = [cumulative_factor] + cum_series.tolist()

        # Convert to percentage returns
        for dt, factor in zip(seg_dates, seg_factors):
            dates_original.append(dt)
            values_original.append((factor - 1.0) * 100.0)

        cumulative_factor = seg_factors[-1] if seg_factors else cumulative_factor

    print(f"\nOriginal app results:")
    print(f"  Total data points: {len(dates_original)}")
    print(f"  First date: {dates_original[0] if dates_original else 'N/A'}")
    print(f"  Last date: {dates_original[-1] if dates_original else 'N/A'}")
    print(f"  First return: {values_original[0] if values_original else 'N/A'}%")
    print(f"  Last return: {values_original[-1] if values_original else 'N/A'}%")

    # =========================================
    # BACKEND COMPUTATION
    # =========================================
    print("\n--- BACKEND ---")

    backend_portfolio = BackendPortfolio()
    backend_portfolio.append_segment(
        start_date=fit_end,
        end_date=test_end,
        allocations=allocations
    )

    print(f"Backend segments: {backend_portfolio.segments}")

    # Use backend's compute_performance
    result = await compute_performance(
        portfolio=backend_portfolio,
        fit_end_date=fit_end,
        test_end_date=test_end,
        include_dividends=include_dividends,
        price_fetcher=get_price_data
    )

    dates_backend = result['dates']
    values_backend = result['cumulative_returns']

    print(f"\nBackend results:")
    print(f"  Total data points: {len(dates_backend)}")
    print(f"  First date: {dates_backend[0] if dates_backend else 'N/A'}")
    print(f"  Last date: {dates_backend[-1] if dates_backend else 'N/A'}")
    print(f"  First return: {values_backend[0] if values_backend else 'N/A'}%")
    print(f"  Last return: {values_backend[-1] if values_backend else 'N/A'}%")

    # =========================================
    # COMPARISON
    # =========================================
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)

    # Convert original dates to strings for comparison
    dates_original_str = [d.isoformat() if hasattr(d, 'isoformat') else str(d) for d in dates_original]

    print(f"\nDate count: Original={len(dates_original)}, Backend={len(dates_backend)}")

    if dates_original_str and dates_backend:
        # Find common dates
        common_dates = set(dates_original_str) & set(dates_backend)
        print(f"Common dates: {len(common_dates)}")

        # Compare values on common dates
        orig_dict = dict(zip(dates_original_str, values_original))
        back_dict = dict(zip(dates_backend, values_backend))

        discrepancies = []
        for d in sorted(common_dates):
            orig_val = orig_dict.get(d)
            back_val = back_dict.get(d)
            if orig_val is not None and back_val is not None:
                diff = abs(orig_val - back_val)
                if diff > 0.001:  # More than 0.001% difference
                    discrepancies.append((d, orig_val, back_val, diff))

        if discrepancies:
            print(f"\nDiscrepancies found ({len(discrepancies)}):")
            for d, o, b, diff in discrepancies[:10]:  # Show first 10
                print(f"  {d}: Original={o:.4f}%, Backend={b:.4f}%, Diff={diff:.4f}%")
            if len(discrepancies) > 10:
                print(f"  ... and {len(discrepancies) - 10} more")
        else:
            print("\nNo significant discrepancies found!")

        # Show first few values side by side
        print("\nFirst 5 values comparison:")
        for i in range(min(5, len(dates_original_str), len(dates_backend))):
            orig_d = dates_original_str[i] if i < len(dates_original_str) else "N/A"
            orig_v = values_original[i] if i < len(values_original) else "N/A"
            back_d = dates_backend[i] if i < len(dates_backend) else "N/A"
            back_v = values_backend[i] if i < len(values_backend) else "N/A"
            print(f"  [{i}] Original: {orig_d}={orig_v}, Backend: {back_d}={back_v}")

        # Show last few values
        print("\nLast 5 values comparison:")
        for i in range(-5, 0):
            orig_d = dates_original_str[i] if abs(i) <= len(dates_original_str) else "N/A"
            orig_v = values_original[i] if abs(i) <= len(values_original) else "N/A"
            back_d = dates_backend[i] if abs(i) <= len(dates_backend) else "N/A"
            back_v = values_backend[i] if abs(i) <= len(values_backend) else "N/A"
            print(f"  [{i}] Original: {orig_d}={orig_v}, Backend: {back_d}={back_v}")


if __name__ == "__main__":
    asyncio.run(run_comparison())
