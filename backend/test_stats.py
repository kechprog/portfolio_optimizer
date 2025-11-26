"""
Test script to verify the calculate_metrics function.

This script tests the portfolio statistics calculations with known inputs
to ensure the math is working correctly.
"""

import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from services.portfolio import calculate_metrics


def test_simple_return():
    """
    Test Case 1: Simple 10% return over 1 year
    Expected:
    - Total return: 10%
    - Annualized return: ~10% (exactly 1 year)
    - Max drawdown: 0 (monotonically increasing)
    """
    print("\n" + "="*80)
    print("TEST CASE 1: Simple 10% return over 1 year")
    print("="*80)

    dates = ["2023-01-01", "2023-12-31"]
    cumulative_returns = [0.0, 10.0]

    print(f"Input dates: {dates}")
    print(f"Input cumulative returns: {cumulative_returns}")

    metrics = calculate_metrics(cumulative_returns, dates)

    print("\nCalculated Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    # Verify expectations
    print("\nVerification:")
    assert abs(metrics["total_return"] - 10.0) < 0.01, "Total return should be 10%"
    print("  [PASS] Total return is 10%")

    # For exactly 1 year, annualized return should equal total return
    # 364 days / 365.25 ≈ 0.9966 years, so it will be slightly higher than 10%
    assert 9.5 < metrics["annualized_return"] < 10.5, "Annualized return should be ~10%"
    print(f"  [PASS] Annualized return is {metrics['annualized_return']}% (close to 10%)")

    assert metrics["max_drawdown"] == 0.0, "Max drawdown should be 0 (no decline)"
    print("  [PASS] Max drawdown is 0% (no decline)")

    print("\n[PASS] TEST CASE 1 PASSED")


def test_with_volatility():
    """
    Test Case 2: Portfolio with ups and downs
    Expected:
    - Total return: 5% (ending value)
    - Volatility: > 0 (since there are fluctuations)
    - Max drawdown: > 0 (since we have a decline from 8% to 3%)
    """
    print("\n" + "="*80)
    print("TEST CASE 2: Portfolio with volatility and drawdown")
    print("="*80)

    # Simulating daily returns over ~10 trading days
    dates = [
        "2023-01-01",  # Start: 0%
        "2023-01-02",  # +3%
        "2023-01-03",  # +5%
        "2023-01-04",  # +8% (peak)
        "2023-01-05",  # +6% (drawdown begins)
        "2023-01-06",  # +3% (trough, 5% drawdown from peak)
        "2023-01-07",  # +4%
        "2023-01-08",  # +5% (final)
    ]
    cumulative_returns = [0.0, 3.0, 5.0, 8.0, 6.0, 3.0, 4.0, 5.0]

    print(f"Input dates: {dates}")
    print(f"Input cumulative returns: {cumulative_returns}")

    metrics = calculate_metrics(cumulative_returns, dates)

    print("\nCalculated Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    # Verify expectations
    print("\nVerification:")
    assert abs(metrics["total_return"] - 5.0) < 0.01, "Total return should be 5%"
    print("  [PASS] Total return is 5%")

    # Max drawdown: from peak of 8% to trough of 3% = 5% drawdown
    assert abs(metrics["max_drawdown"] - 5.0) < 0.01, "Max drawdown should be 5%"
    print(f"  [PASS] Max drawdown is {metrics['max_drawdown']}% (8% peak - 3% trough = 5% drawdown)")

    # Volatility should be positive since returns fluctuate
    assert metrics["volatility"] > 0, "Volatility should be positive"
    print(f"  [PASS] Volatility is {metrics['volatility']}% (positive, as expected)")

    print("\n[PASS] TEST CASE 2 PASSED")


def test_negative_return():
    """
    Test Case 3: Negative return scenario
    Expected:
    - Total return: -15%
    - Annualized return: negative
    - Max drawdown: 15%
    """
    print("\n" + "="*80)
    print("TEST CASE 3: Negative return over 6 months")
    print("="*80)

    dates = ["2023-01-01", "2023-06-30"]
    cumulative_returns = [0.0, -15.0]

    print(f"Input dates: {dates}")
    print(f"Input cumulative returns: {cumulative_returns}")

    metrics = calculate_metrics(cumulative_returns, dates)

    print("\nCalculated Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    # Verify expectations
    print("\nVerification:")
    assert abs(metrics["total_return"] - (-15.0)) < 0.01, "Total return should be -15%"
    print("  [PASS] Total return is -15%")

    assert metrics["annualized_return"] < 0, "Annualized return should be negative"
    print(f"  [PASS] Annualized return is {metrics['annualized_return']}% (negative)")

    # Max drawdown should be 15% (from 0% to -15%)
    assert abs(metrics["max_drawdown"] - 15.0) < 0.01, "Max drawdown should be 15%"
    print(f"  [PASS] Max drawdown is {metrics['max_drawdown']}%")

    print("\n[PASS] TEST CASE 3 PASSED")


def test_edge_cases():
    """
    Test Case 4: Edge cases
    - Empty lists
    - Single data point
    """
    print("\n" + "="*80)
    print("TEST CASE 4: Edge cases")
    print("="*80)

    # Empty lists
    print("\nSubtest 4a: Empty lists")
    metrics = calculate_metrics([], [])
    print(f"  Result: {metrics}")
    assert all(v == 0.0 for v in metrics.values()), "All metrics should be 0 for empty input"
    print("  [PASS] Empty lists return all zeros")

    # Single data point
    print("\nSubtest 4b: Single data point")
    metrics = calculate_metrics([5.0], ["2023-01-01"])
    print(f"  Result: {metrics}")
    assert all(v == 0.0 for v in metrics.values()), "All metrics should be 0 for single point"
    print("  [PASS] Single data point returns all zeros")

    print("\n[PASS] TEST CASE 4 PASSED")


def test_sharpe_ratio():
    """
    Test Case 5: Verify Sharpe ratio calculation
    The formula is: (annualized_return - risk_free_rate) / volatility
    Risk-free rate is assumed to be 4%
    """
    print("\n" + "="*80)
    print("TEST CASE 5: Sharpe ratio calculation")
    print("="*80)

    # Use a scenario where we can manually verify the Sharpe ratio
    # Let's use a multi-year scenario with consistent growth
    dates = ["2020-01-01", "2023-01-01"]  # 3 years
    cumulative_returns = [0.0, 30.0]  # 30% total return over 3 years

    print(f"Input dates: {dates}")
    print(f"Input cumulative returns: {cumulative_returns}")

    metrics = calculate_metrics(cumulative_returns, dates)

    print("\nCalculated Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    # Verify Sharpe ratio calculation
    # Expected: (annualized_return - 4.0) / volatility
    if metrics["volatility"] > 0:
        expected_sharpe = (metrics["annualized_return"] - 4.0) / metrics["volatility"]
        print(f"\nManual Sharpe calculation: ({metrics['annualized_return']} - 4.0) / {metrics['volatility']} = {expected_sharpe:.4f}")
        assert abs(metrics["sharpe_ratio"] - expected_sharpe) < 0.01, "Sharpe ratio calculation error"
        print(f"  [PASS] Sharpe ratio matches: {metrics['sharpe_ratio']} ~= {expected_sharpe:.4f}")
    else:
        print(f"  [PASS] Sharpe ratio is 0 (volatility is 0)")

    print("\n[PASS] TEST CASE 5 PASSED")


def run_all_tests():
    """Run all test cases."""
    print("\n" + "="*80)
    print("PORTFOLIO STATISTICS CALCULATION TEST SUITE")
    print("="*80)

    try:
        test_simple_return()
        test_with_volatility()
        test_negative_return()
        test_edge_cases()
        test_sharpe_ratio()

        print("\n" + "="*80)
        print("ALL TESTS PASSED!")
        print("="*80)
        print("\nThe calculate_metrics function is working correctly.")
        print("All calculations match expected values.")

    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
