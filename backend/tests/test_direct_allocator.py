"""
Direct test of MaxSharpe allocator to diagnose empty segments issue.
"""

import asyncio
from datetime import date

from allocators.max_sharpe import MaxSharpeAllocator
from services.price_fetcher import get_price_data


async def test_max_sharpe_direct():
    """Test MaxSharpe allocator directly without WebSocket."""
    print("\n" + "=" * 70)
    print("  DIRECT MAX SHARPE ALLOCATOR TEST")
    print("=" * 70)

    # Create allocator
    allocator = MaxSharpeAllocator(
        name="Direct Test MaxSharpe",
        instruments=["AAPL", "MSFT", "GOOG"],
        allow_shorting=False,
        use_adj_close=True,
        update_enabled=False,
        update_interval_value=30,
        update_interval_unit="days"
    )

    print(f"\nAllocator created: {allocator.name}")
    print(f"Instruments: {allocator.get_instruments()}")

    # Define date range
    fit_start = date(2023, 1, 1)
    fit_end = date(2023, 12, 31)
    test_end = date(2024, 6, 1)

    print(f"\nDate range:")
    print(f"  Fit: {fit_start} to {fit_end}")
    print(f"  Test: {fit_end} to {test_end}")

    # Test price fetching first
    print("\n[1] Testing price fetching...")
    for ticker in ["AAPL", "MSFT", "GOOG"]:
        try:
            df = await get_price_data(ticker, fit_start, fit_end)
            print(f"  {ticker}: {len(df)} rows, from {df.index[0].date()} to {df.index[-1].date()}")
            print(f"    Columns: {list(df.columns)}")
            if "AdjClose" in df.columns:
                print(f"    First AdjClose: ${df['AdjClose'].iloc[0]:.2f}")
                print(f"    Last AdjClose: ${df['AdjClose'].iloc[-1]:.2f}")
        except Exception as e:
            print(f"  {ticker}: ERROR - {e}")

    # Run compute
    print("\n[2] Running MaxSharpe compute...")

    async def progress_callback(msg: str, current: int, total: int):
        print(f"  Progress [{current}/{total}]: {msg}")

    try:
        portfolio = await allocator.compute(
            fit_start_date=fit_start,
            fit_end_date=fit_end,
            test_end_date=test_end,
            include_dividends=True,
            price_fetcher=get_price_data,
            progress_callback=progress_callback
        )

        print("\n[3] Results:")
        print(f"  Number of segments: {len(portfolio.segments)}")

        if portfolio.segments:
            for i, segment in enumerate(portfolio.segments):
                print(f"\n  Segment {i}:")
                print(f"    Period: {segment.start_date} to {segment.end_date}")
                print(f"    Allocations:")
                for ticker, weight in segment.allocations.items():
                    print(f"      {ticker}: {weight:.4f} ({weight*100:.2f}%)")
                total_weight = sum(segment.allocations.values())
                print(f"    Total weight: {total_weight:.4f}")
        else:
            print("\n  WARNING: No segments returned!")
            print("  This means the allocator.compute() returned an empty Portfolio")

    except Exception as e:
        print(f"\n  ERROR during compute: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_max_sharpe_direct())
