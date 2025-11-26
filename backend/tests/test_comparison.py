"""
Comprehensive comparison test between original app logic and new backend logic.

This test runs identical test cases on both implementations and compares:
- Portfolio segment allocations
- Cumulative returns
- Number of segments
- Date ranges
"""

import sys
import os
from datetime import date
from typing import Dict, List, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
import functools

# Add paths for both original and new backend
ORIGINAL_APP_PATH = r"C:\Users\Eduar\projects\portfolio_optimizer"
NEW_BACKEND_PATH = r"C:\Users\Eduar\projects\portfolio_optimizer_react\backend"

sys.path.insert(0, ORIGINAL_APP_PATH)
sys.path.insert(0, NEW_BACKEND_PATH)

# Import from original app
from allocator.manual import ManualAllocator as OriginalManualAllocator
from allocator.mpt.max_sharpe import MaxSharpeAllocator as OriginalMaxSharpeAllocator
from allocator.mpt.min_volatility import MinVolatilityAllocator as OriginalMinVolatilityAllocator
from portfolio import Portfolio as OriginalPortfolio

# Import from new backend
from allocators.manual import ManualAllocator as NewManualAllocator
from allocators.max_sharpe import MaxSharpeAllocator as NewMaxSharpeAllocator
from allocators.min_volatility import MinVolatilityAllocator as NewMinVolatilityAllocator
from allocators.base import Portfolio as NewPortfolio
from services.price_fetcher import get_price_data
from services.portfolio import compute_performance

# Test configuration
FIT_START = date(2023, 1, 1)
FIT_END = date(2023, 12, 31)
TEST_END = date(2024, 6, 1)
TOLERANCE = 0.0001  # 0.01% tolerance for returns

# Thread pool for running original allocator computations (to avoid event loop conflicts)
executor = ThreadPoolExecutor(max_workers=1)


async def run_in_thread(func, *args, **kwargs):
    """Run a synchronous function in a thread pool to avoid event loop conflicts."""
    loop = asyncio.get_event_loop()
    partial_func = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(executor, partial_func)


class ComparisonResult:
    """Stores comparison results for a single test case."""

    def __init__(self, test_name: str):
        self.test_name = test_name
        self.passed = True
        self.messages: List[str] = []

    def add_pass(self, message: str):
        """Add a passing check."""
        self.messages.append(f"  [PASS] {message}")

    def add_fail(self, message: str):
        """Add a failing check."""
        self.passed = False
        self.messages.append(f"  [FAIL] {message}")

    def add_info(self, message: str):
        """Add an informational message."""
        self.messages.append(f"    INFO: {message}")

    def print_results(self):
        """Print all results for this test."""
        status = "PASS" if self.passed else "FAIL"
        print(f"\n{'='*80}")
        print(f"Test: {self.test_name}")
        print(f"Status: {status}")
        print(f"{'='*80}")
        for msg in self.messages:
            print(msg)


def compare_allocations(
    result: ComparisonResult,
    original_allocs: Dict[str, float],
    new_allocs: Dict[str, float],
    segment_name: str = "segment"
) -> None:
    """Compare two allocation dictionaries."""

    # Check if both have the same tickers
    original_tickers = set(original_allocs.keys())
    new_tickers = set(new_allocs.keys())

    if original_tickers != new_tickers:
        result.add_fail(f"{segment_name}: Ticker mismatch")
        result.add_info(f"Original tickers: {sorted(original_tickers)}")
        result.add_info(f"New tickers: {sorted(new_tickers)}")
        return

    # Compare allocations for each ticker
    all_match = True
    for ticker in sorted(original_tickers):
        orig_val = original_allocs[ticker]
        new_val = new_allocs[ticker]
        diff = abs(orig_val - new_val)

        if diff > TOLERANCE:
            all_match = False
            result.add_fail(
                f"{segment_name}: {ticker} allocation mismatch: "
                f"original={orig_val:.6f}, new={new_val:.6f}, diff={diff:.6f}"
            )
        else:
            result.add_info(
                f"{ticker}: {orig_val:.6f} (both implementations match)"
            )

    if all_match:
        result.add_pass(f"{segment_name}: All allocations match within tolerance")


def get_original_portfolio_segments(portfolio: OriginalPortfolio, query_end_date: date) -> List[Dict[str, Any]]:
    """Get segments from original Portfolio object."""
    return portfolio.get(query_end_date)


def get_new_portfolio_segments(portfolio: NewPortfolio) -> List[Dict[str, Any]]:
    """Get segments from new Portfolio object."""
    segments = []
    for seg in portfolio.segments:
        segments.append({
            'start_date': seg.start_date,
            'end_date': seg.end_date,
            'allocations': seg.allocations
        })
    return segments


async def compute_new_portfolio_returns(
    portfolio: NewPortfolio,
    end_date: date,
    include_dividends: bool = False
) -> float:
    """Compute cumulative return for new backend portfolio."""
    try:
        # Get fit_end_date from the portfolio's first segment
        if not portfolio.segments:
            return 0.0

        fit_end_date = portfolio.segments[0].start_date

        performance = await compute_performance(
            portfolio=portfolio,
            fit_end_date=fit_end_date,
            test_end_date=end_date,
            include_dividends=include_dividends,
            price_fetcher=get_price_data
        )

        # Return the final cumulative return if available
        if performance["cumulative_returns"]:
            return performance["cumulative_returns"][-1]
        return 0.0
    except Exception as e:
        print(f"Error computing new portfolio returns: {e}")
        import traceback
        traceback.print_exc()
        return 0.0


async def compute_original_portfolio_returns(
    portfolio: OriginalPortfolio,
    end_date: date,
    include_dividends: bool = False
) -> float:
    """
    Compute cumulative return for original portfolio.
    This mimics the plot() logic but returns the final cumulative return.
    Uses the new backend's price fetcher to avoid async event loop conflicts.
    """
    import pandas as pd

    segments = portfolio.get(end_date)
    if not segments:
        return 0.0

    cumulative_factor = 1.0
    for seg in segments:
        start = seg['start_date']
        end = seg['end_date']
        allocs = {t: w for t, w in seg['allocations'].items() if abs(w) > 1e-9}

        if not allocs:
            continue

        tickers = {t.upper() for t in allocs}

        # Fetch price data for all tickers using new backend
        try:
            price_dfs = {}
            for ticker in tickers:
                df = await get_price_data(ticker, start, end)
                if df is not None and not df.empty:
                    price_dfs[ticker] = df
        except Exception as e:
            print(f"Error fetching data for original portfolio: {e}")
            continue

        if not price_dfs:
            continue

        # Build price DataFrame similar to original format
        field = 'AdjClose' if include_dividends else 'Close'

        price_series = []
        for ticker, df in price_dfs.items():
            if field in df.columns:
                price_series.append(df[field].rename(ticker))

        if not price_series:
            continue

        price_df = pd.concat(price_series, axis=1)
        price_df = price_df.ffill().bfill()
        returns = price_df.pct_change().dropna(how='all')
        returns = returns[returns.index.date >= start]

        if returns.empty:
            continue

        weights = pd.Series({col: allocs.get(col, 0.0) for col in returns.columns})
        port_ret = returns.mul(weights, axis=1).sum(axis=1)
        cum_series = (1 + port_ret).cumprod() * cumulative_factor

        if len(cum_series) > 0:
            cumulative_factor = cum_series.iloc[-1]

    # Return as percentage
    return (cumulative_factor - 1.0) * 100.0


async def test_manual_allocator():
    """Test ManualAllocator implementation comparison."""
    result = ComparisonResult("ManualAllocator - AAPL 60% / MSFT 40%")

    allocations = {"AAPL": 0.6, "MSFT": 0.4}

    # Original implementation
    original_state = {
        "name": "Test Manual",
        "instruments": set(allocations.keys()),
        "allocations": allocations
    }
    original_allocator = OriginalManualAllocator(**original_state)
    original_portfolio = await run_in_thread(
        original_allocator.compute_allocations,
        FIT_START, FIT_END, TEST_END
    )

    # New implementation
    new_allocator = NewManualAllocator(name="Test Manual", allocations=allocations)
    new_portfolio = await new_allocator.compute(
        fit_start_date=FIT_START,
        fit_end_date=FIT_END,
        test_end_date=TEST_END,
        include_dividends=False,
        price_fetcher=get_price_data,
        progress_callback=None
    )

    # Compare segments
    original_segments = get_original_portfolio_segments(original_portfolio, TEST_END)
    new_segments = get_new_portfolio_segments(new_portfolio)

    result.add_info(f"Original segments: {len(original_segments)}")
    result.add_info(f"New segments: {len(new_segments)}")

    if len(original_segments) != len(new_segments):
        result.add_fail(f"Number of segments mismatch: original={len(original_segments)}, new={len(new_segments)}")
    else:
        result.add_pass(f"Number of segments match: {len(original_segments)}")

    # Compare each segment
    for i, (orig_seg, new_seg) in enumerate(zip(original_segments, new_segments)):
        result.add_info(f"Segment {i+1}: {orig_seg['start_date']} to {orig_seg['end_date']}")

        # Check dates
        if orig_seg['start_date'] != new_seg['start_date']:
            result.add_fail(f"Segment {i+1} start_date mismatch")
        if orig_seg['end_date'] != new_seg['end_date']:
            result.add_fail(f"Segment {i+1} end_date mismatch")

        # Check allocations
        compare_allocations(result, orig_seg['allocations'], new_seg['allocations'], f"Segment {i+1}")

    # Compare cumulative returns
    try:
        original_return = await compute_original_portfolio_returns(original_portfolio, TEST_END, False)
        new_return = await compute_new_portfolio_returns(new_portfolio, TEST_END, False)

        result.add_info(f"Original cumulative return: {original_return:.4f}%")
        result.add_info(f"New cumulative return: {new_return:.4f}%")

        return_diff = abs(original_return - new_return)
        if return_diff <= TOLERANCE * 100:  # TOLERANCE is in decimal, returns are in percentage
            result.add_pass(f"Cumulative returns match within tolerance (diff={return_diff:.6f}%)")
        else:
            result.add_fail(f"Cumulative returns differ by {return_diff:.6f}%")
    except Exception as e:
        result.add_fail(f"Error computing returns: {e}")

    result.print_results()
    return result.passed


async def test_max_sharpe_allocator():
    """Test MaxSharpeAllocator implementation comparison."""
    result = ComparisonResult("MaxSharpeAllocator - AAPL/MSFT/GOOG, no shorting")

    instruments = ["AAPL", "MSFT", "GOOG"]

    # Original implementation
    original_state = {
        "name": "Test MaxSharpe",
        "instruments": set(instruments),
        "allow_shorting": False
    }
    original_allocator = OriginalMaxSharpeAllocator(**original_state)
    original_portfolio = await run_in_thread(
        original_allocator.compute_allocations,
        FIT_START, FIT_END, TEST_END
    )

    # New implementation
    new_allocator = NewMaxSharpeAllocator(
        name="Test MaxSharpe",
        instruments=instruments,
        allow_shorting=False
    )
    new_portfolio = await new_allocator.compute(
        fit_start_date=FIT_START,
        fit_end_date=FIT_END,
        test_end_date=TEST_END,
        include_dividends=False,
        price_fetcher=get_price_data,
        progress_callback=None
    )

    # Compare segments
    original_segments = get_original_portfolio_segments(original_portfolio, TEST_END)
    new_segments = get_new_portfolio_segments(new_portfolio)

    result.add_info(f"Original segments: {len(original_segments)}")
    result.add_info(f"New segments: {len(new_segments)}")

    if len(original_segments) != len(new_segments):
        result.add_fail(f"Number of segments mismatch: original={len(original_segments)}, new={len(new_segments)}")
    else:
        result.add_pass(f"Number of segments match: {len(original_segments)}")

    # Compare each segment
    for i, (orig_seg, new_seg) in enumerate(zip(original_segments, new_segments)):
        result.add_info(f"Segment {i+1}: {orig_seg['start_date']} to {orig_seg['end_date']}")

        # Check dates
        if orig_seg['start_date'] != new_seg['start_date']:
            result.add_fail(f"Segment {i+1} start_date mismatch")
        if orig_seg['end_date'] != new_seg['end_date']:
            result.add_fail(f"Segment {i+1} end_date mismatch")

        # Check allocations
        compare_allocations(result, orig_seg['allocations'], new_seg['allocations'], f"Segment {i+1}")

    # Compare cumulative returns
    try:
        original_return = await compute_original_portfolio_returns(original_portfolio, TEST_END, False)
        new_return = await compute_new_portfolio_returns(new_portfolio, TEST_END, False)

        result.add_info(f"Original cumulative return: {original_return:.4f}%")
        result.add_info(f"New cumulative return: {new_return:.4f}%")

        return_diff = abs(original_return - new_return)
        if return_diff <= TOLERANCE * 100:
            result.add_pass(f"Cumulative returns match within tolerance (diff={return_diff:.6f}%)")
        else:
            result.add_fail(f"Cumulative returns differ by {return_diff:.6f}%")
    except Exception as e:
        result.add_fail(f"Error computing returns: {e}")

    result.print_results()
    return result.passed


async def test_min_volatility_allocator():
    """Test MinVolatilityAllocator implementation comparison."""
    result = ComparisonResult("MinVolatilityAllocator - AAPL/MSFT/GOOG, no shorting")

    instruments = ["AAPL", "MSFT", "GOOG"]

    # Original implementation
    original_state = {
        "name": "Test MinVol",
        "instruments": set(instruments),
        "allow_shorting": False
    }
    original_allocator = OriginalMinVolatilityAllocator(**original_state)
    original_portfolio = await run_in_thread(
        original_allocator.compute_allocations,
        FIT_START, FIT_END, TEST_END
    )

    # New implementation
    new_allocator = NewMinVolatilityAllocator(
        name="Test MinVol",
        instruments=instruments,
        allow_shorting=False
    )
    new_portfolio = await new_allocator.compute(
        fit_start_date=FIT_START,
        fit_end_date=FIT_END,
        test_end_date=TEST_END,
        include_dividends=False,
        price_fetcher=get_price_data,
        progress_callback=None
    )

    # Compare segments
    original_segments = get_original_portfolio_segments(original_portfolio, TEST_END)
    new_segments = get_new_portfolio_segments(new_portfolio)

    result.add_info(f"Original segments: {len(original_segments)}")
    result.add_info(f"New segments: {len(new_segments)}")

    if len(original_segments) != len(new_segments):
        result.add_fail(f"Number of segments mismatch: original={len(original_segments)}, new={len(new_segments)}")
    else:
        result.add_pass(f"Number of segments match: {len(original_segments)}")

    # Compare each segment
    for i, (orig_seg, new_seg) in enumerate(zip(original_segments, new_segments)):
        result.add_info(f"Segment {i+1}: {orig_seg['start_date']} to {orig_seg['end_date']}")

        # Check dates
        if orig_seg['start_date'] != new_seg['start_date']:
            result.add_fail(f"Segment {i+1} start_date mismatch")
        if orig_seg['end_date'] != new_seg['end_date']:
            result.add_fail(f"Segment {i+1} end_date mismatch")

        # Check allocations
        compare_allocations(result, orig_seg['allocations'], new_seg['allocations'], f"Segment {i+1}")

    # Compare cumulative returns
    try:
        original_return = await compute_original_portfolio_returns(original_portfolio, TEST_END, False)
        new_return = await compute_new_portfolio_returns(new_portfolio, TEST_END, False)

        result.add_info(f"Original cumulative return: {original_return:.4f}%")
        result.add_info(f"New cumulative return: {new_return:.4f}%")

        return_diff = abs(original_return - new_return)
        if return_diff <= TOLERANCE * 100:
            result.add_pass(f"Cumulative returns match within tolerance (diff={return_diff:.6f}%)")
        else:
            result.add_fail(f"Cumulative returns differ by {return_diff:.6f}%")
    except Exception as e:
        result.add_fail(f"Error computing returns: {e}")

    result.print_results()
    return result.passed


async def main():
    """Run all comparison tests."""
    print("\n" + "="*80)
    print("COMPREHENSIVE COMPARISON TEST")
    print("Original App vs New Backend")
    print("="*80)
    print(f"\nTest Configuration:")
    print(f"  Fit period: {FIT_START} to {FIT_END}")
    print(f"  Test end: {TEST_END}")
    print(f"  Tolerance: {TOLERANCE*100:.4f}%")

    results = []

    # Run all tests
    print("\n" + "="*80)
    print("Running Test 1: ManualAllocator")
    print("="*80)
    results.append(await test_manual_allocator())

    print("\n" + "="*80)
    print("Running Test 2: MaxSharpeAllocator")
    print("="*80)
    results.append(await test_max_sharpe_allocator())

    print("\n" + "="*80)
    print("Running Test 3: MinVolatilityAllocator")
    print("="*80)
    results.append(await test_min_volatility_allocator())

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")

    if all(results):
        print("\n[SUCCESS] ALL TESTS PASSED - Implementations are equivalent!")
    else:
        print("\n[FAILURE] SOME TESTS FAILED - Implementations differ!")

    return all(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
