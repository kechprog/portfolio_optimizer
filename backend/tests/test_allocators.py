"""
Direct test of allocators without WebSocket layer.
"""
import asyncio
import sys
from datetime import date

sys.path.insert(0, '..')

from allocators.manual import ManualAllocator
from allocators.max_sharpe import MaxSharpeAllocator
from services.price_fetcher import get_price_data
from services.portfolio import compute_performance


async def progress_callback(msg: str, step: int, total: int):
    print(f"  Progress: {msg} ({step}/{total})")


async def price_fetcher(ticker: str, start: date, end: date):
    print(f"  Fetching {ticker} from {start} to {end}...")
    df = await get_price_data(ticker, start, end)
    print(f"  Got {len(df)} rows for {ticker}")
    return df


async def test_manual_allocator():
    print("\n" + "=" * 60)
    print("TEST: Manual Allocator")
    print("=" * 60)

    allocator = ManualAllocator(
        name="Test Manual",
        allocations={"AAPL": 0.6, "MSFT": 0.4}
    )

    print(f"\nAllocator: {allocator.name}")
    print(f"Instruments: {allocator.get_instruments()}")

    # Compute
    print("\nComputing allocations...")
    portfolio = await allocator.compute(
        fit_start_date=date(2023, 1, 1),
        fit_end_date=date(2023, 12, 31),
        test_end_date=date(2024, 6, 1),
        include_dividends=True,
        price_fetcher=price_fetcher,
        progress_callback=progress_callback
    )

    print(f"\nPortfolio segments: {len(portfolio.segments)}")
    for seg in portfolio.segments:
        print(f"  {seg.start_date} to {seg.end_date}: {seg.allocations}")

    # Compute performance
    print("\nComputing performance...")
    perf = await compute_performance(
        portfolio=portfolio,
        fit_end_date=date(2023, 12, 31),
        test_end_date=date(2024, 6, 1),
        include_dividends=True,
        price_fetcher=price_fetcher
    )

    print(f"Performance dates: {len(perf['dates'])}")
    if perf['dates']:
        print(f"  First: {perf['dates'][0]}, Last: {perf['dates'][-1]}")
        print(f"  Final return: {perf['cumulative_returns'][-1]:.2f}%")
    else:
        print("  No performance data!")

    return len(portfolio.segments) > 0 and len(perf['dates']) > 0


async def test_max_sharpe_allocator():
    print("\n" + "=" * 60)
    print("TEST: MaxSharpe Allocator")
    print("=" * 60)

    allocator = MaxSharpeAllocator(
        name="Test MaxSharpe",
        instruments=["AAPL", "MSFT", "GOOG"],
        allow_shorting=False,
        use_adj_close=True,
        update_enabled=False
    )

    print(f"\nAllocator: {allocator.name}")
    print(f"Instruments: {allocator.get_instruments()}")

    # Compute
    print("\nComputing allocations...")
    try:
        portfolio = await allocator.compute(
            fit_start_date=date(2023, 1, 1),
            fit_end_date=date(2023, 12, 31),
            test_end_date=date(2024, 6, 1),
            include_dividends=True,
            price_fetcher=price_fetcher,
            progress_callback=progress_callback
        )

        print(f"\nPortfolio segments: {len(portfolio.segments)}")
        for seg in portfolio.segments:
            print(f"  {seg.start_date} to {seg.end_date}: {seg.allocations}")

        if len(portfolio.segments) == 0:
            print("  ERROR: No segments created!")
            return False

        # Compute performance
        print("\nComputing performance...")
        perf = await compute_performance(
            portfolio=portfolio,
            fit_end_date=date(2023, 12, 31),
            test_end_date=date(2024, 6, 1),
            include_dividends=True,
            price_fetcher=price_fetcher
        )

        print(f"Performance dates: {len(perf['dates'])}")
        if perf['dates']:
            print(f"  First: {perf['dates'][0]}, Last: {perf['dates'][-1]}")
            print(f"  Final return: {perf['cumulative_returns'][-1]:.2f}%")

        return len(portfolio.segments) > 0

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("=" * 60)
    print("Allocator Direct Test")
    print("=" * 60)

    result1 = await test_manual_allocator()
    result2 = await test_max_sharpe_allocator()

    print("\n" + "=" * 60)
    print("RESULTS:")
    print(f"  Manual Allocator: {'PASS' if result1 else 'FAIL'}")
    print(f"  MaxSharpe Allocator: {'PASS' if result2 else 'FAIL'}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
