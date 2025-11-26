"""
Database module for async SQLite operations with price caching.
"""
import asyncio
import json
import aiosqlite
from datetime import date, datetime
from typing import Optional, Dict, Any

from config import DATABASE_PATH

# Track if database has been initialized
_db_initialized = False
_db_init_lock = asyncio.Lock()


async def init_database() -> None:
    """Initialize the database schema."""
    global _db_initialized

    async with _db_init_lock:
        if _db_initialized:
            return

        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS price_cache (
                    ticker TEXT PRIMARY KEY,
                    data JSON NOT NULL,
                    first_date DATE NOT NULL,
                    last_date DATE NOT NULL,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
            print(f"Database initialized at {DATABASE_PATH}")

        _db_initialized = True


async def get_cached_price_data(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached price data for a ticker.

    Args:
        ticker: The stock ticker symbol

    Returns:
        Dictionary with keys: 'data', 'first_date', 'last_date', 'fetched_at'
        or None if not cached
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT data, first_date, last_date, fetched_at FROM price_cache WHERE ticker = ?",
            (ticker,)
        ) as cursor:
            row = await cursor.fetchone()

            if row is None:
                return None

            try:
                return {
                    'data': json.loads(row['data']),
                    'first_date': datetime.strptime(row['first_date'], '%Y-%m-%d').date(),
                    'last_date': datetime.strptime(row['last_date'], '%Y-%m-%d').date(),
                    'fetched_at': datetime.fromisoformat(row['fetched_at'])
                }
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Warning: Failed to parse cached data for {ticker}: {e}")
                return None


async def store_price_data(
    ticker: str,
    data: Dict[str, Any],
    first_date: date,
    last_date: date
) -> None:
    """
    Store price data in the cache.

    Args:
        ticker: The stock ticker symbol
        data: The time series data (dictionary with date strings as keys)
        first_date: The earliest date in the data
        last_date: The latest date in the data
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO price_cache (ticker, data, first_date, last_date, fetched_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            ticker,
            json.dumps(data),
            first_date.isoformat(),
            last_date.isoformat()
        ))
        await db.commit()
        print(f"Cached price data for {ticker} ({first_date} to {last_date})")


async def delete_cached_price_data(ticker: str) -> bool:
    """
    Delete cached price data for a ticker.

    Args:
        ticker: The stock ticker symbol

    Returns:
        True if data was deleted, False if ticker was not in cache
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM price_cache WHERE ticker = ?",
            (ticker,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def clear_all_cache() -> int:
    """
    Clear all cached price data.

    Returns:
        Number of entries deleted
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("DELETE FROM price_cache")
        await db.commit()
        return cursor.rowcount


async def get_cache_info() -> list[Dict[str, Any]]:
    """
    Get information about all cached tickers.

    Returns:
        List of dictionaries with ticker, first_date, last_date, fetched_at
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT ticker, first_date, last_date, fetched_at FROM price_cache ORDER BY ticker"
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    'ticker': row['ticker'],
                    'first_date': row['first_date'],
                    'last_date': row['last_date'],
                    'fetched_at': row['fetched_at']
                }
                for row in rows
            ]
