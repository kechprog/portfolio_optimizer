"""
Direct test of price fetcher to debug the issue
"""

import asyncio
from datetime import date
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.price_fetcher import get_price_data


async def main():
    print("Testing price fetcher directly...")
    print("=" * 70)

    ticker = "AAPL"
    start_date = date(2023, 12, 31)
    end_date = date(2024, 6, 1)

    print(f"\nFetching {ticker} from {start_date} to {end_date}")

    try:
        df = await get_price_data(ticker, start_date, end_date)

        print(f"\nResult DataFrame shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        print(f"\nFirst 5 rows:")
        print(df.head())
        print(f"\nLast 5 rows:")
        print(df.tail())
        print(f"\nIndex type: {type(df.index)}")
        print(f"Index range: {df.index[0]} to {df.index[-1]}")

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
