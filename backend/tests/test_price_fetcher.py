"""
Simple test for price fetcher to isolate threading issues.
"""
import asyncio
import sys
from datetime import date

sys.path.insert(0, '..')

from services.price_fetcher import get_price_data


async def test_single_fetch():
    """Test fetching a single ticker."""
    print("Testing single ticker fetch...")
    try:
        df = await get_price_data("AAPL", date(2023, 1, 1), date(2023, 12, 31))
        print(f"Fetched {len(df)} rows for AAPL")
        print(f"Columns: {list(df.columns)}")
        print(f"Date range: {df.index.min()} to {df.index.max()}")
        print(df.head())
        return True
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_multiple_fetch():
    """Test fetching multiple tickers sequentially."""
    print("\nTesting multiple ticker fetch (sequential)...")
    tickers = ["AAPL", "MSFT", "GOOG"]

    for ticker in tickers:
        try:
            df = await get_price_data(ticker, date(2023, 1, 1), date(2023, 12, 31))
            print(f"  {ticker}: {len(df)} rows")
        except Exception as e:
            print(f"  {ticker}: Error - {e}")
            return False

    return True


async def main():
    print("=" * 60)
    print("Price Fetcher Test")
    print("=" * 60)

    # Test 1: Single fetch
    result1 = await test_single_fetch()

    # Test 2: Multiple sequential fetches
    result2 = await test_multiple_fetch()

    print("\n" + "=" * 60)
    print("Results:")
    print(f"  Single fetch: {'PASS' if result1 else 'FAIL'}")
    print(f"  Multiple fetch: {'PASS' if result2 else 'FAIL'}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
