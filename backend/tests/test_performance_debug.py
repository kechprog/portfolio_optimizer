"""
Debug performance calculation
"""

import asyncio
from datetime import date
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from allocators.base import Portfolio
from services.portfolio import compute_performance
from services.price_fetcher import get_price_data


async def main():
    print("Testing performance calculation...")
    print("=" * 70)

    # Create a portfolio with one segment
    portfolio = Portfolio()
    portfolio.append_segment(
        start_date=date(2023, 12, 31),
        end_date=date(2024, 6, 1),
        allocations={"AAPL": 0.6, "MSFT": 0.4}
    )

    print(f"\nPortfolio segments: {len(portfolio.segments)}")
    for i, seg in enumerate(portfolio.segments):
        print(f"  Segment {i}: {seg.start_date} to {seg.end_date}")
        print(f"    Allocations: {seg.allocations}")

    # Create price fetcher
    async def price_fetcher(ticker: str, start: date, end: date):
        return await get_price_data(ticker, start, end)

    # Calculate performance
    fit_end_date = date(2023, 12, 31)
    test_end_date = date(2024, 6, 1)
    include_dividends = True

    print(f"\nComputing performance from {fit_end_date} to {test_end_date}")
    print(f"Include dividends: {include_dividends}")

    try:
        performance = await compute_performance(
            portfolio=portfolio,
            fit_end_date=fit_end_date,
            test_end_date=test_end_date,
            include_dividends=include_dividends,
            price_fetcher=price_fetcher
        )

        print(f"\nPerformance result:")
        print(f"  Dates: {len(performance['dates'])} points")
        print(f"  Returns: {len(performance['cumulative_returns'])} points")

        if performance['dates']:
            print(f"\n  First 5 dates:")
            for i in range(min(5, len(performance['dates']))):
                print(f"    {performance['dates'][i]}: {performance['cumulative_returns'][i]:.4f}%")

            print(f"\n  Last 5 dates:")
            for i in range(max(0, len(performance['dates'])-5), len(performance['dates'])):
                print(f"    {performance['dates'][i]}: {performance['cumulative_returns'][i]:.4f}%")
        else:
            print("\n  WARNING: No performance data!")

            # Debug: Check if date comparison is working
            print("\n  Debugging:")
            print(f"    test_end_date > fit_end_date: {test_end_date > fit_end_date}")
            print(f"    test_end_date <= fit_end_date: {test_end_date <= fit_end_date}")

            # Check tickers
            all_tickers = portfolio.get_all_tickers()
            print(f"    All tickers: {all_tickers}")

            # Try fetching one ticker
            if all_tickers:
                ticker = list(all_tickers)[0]
                print(f"\n    Fetching test data for {ticker}...")
                df = await price_fetcher(ticker, fit_end_date, test_end_date)
                print(f"    DataFrame shape: {df.shape}")
                print(f"    DataFrame empty: {df.empty}")
                if not df.empty:
                    print(f"    Date range: {df.index[0]} to {df.index[-1]}")
                    print(f"    Columns: {list(df.columns)}")

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
