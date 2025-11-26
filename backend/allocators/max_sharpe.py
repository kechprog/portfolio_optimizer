"""
MaxSharpe allocator implementation using Modern Portfolio Theory.

Uses PyPortfolioOpt library to compute optimal portfolio weights
that maximize the Sharpe ratio.
"""

from typing import Any, Dict, List, Set
import logging
import math

import pandas as pd
from pypfopt import EfficientFrontier, expected_returns, risk_models

from .base import OptimizationAllocatorBase

# Try to import PyPortfolioOpt's OptimizationError if available
try:
    from pypfopt.exceptions import OptimizationError
except ImportError:
    # Fallback if pypfopt doesn't expose OptimizationError
    OptimizationError = Exception

logger = logging.getLogger(__name__)


class MaxSharpeAllocator(OptimizationAllocatorBase):
    """
    An allocator that uses Modern Portfolio Theory to maximize the Sharpe ratio.

    Uses PyPortfolioOpt library to compute expected returns and covariance
    matrices, then optimizes for maximum Sharpe ratio.
    """

    def __init__(
        self,
        name: str,
        instruments: List[str],
        allow_shorting: bool = False,
        use_adj_close: bool = True,
        update_enabled: bool = False,
        update_interval_value: int = 1,
        update_interval_unit: str = "days"
    ):
        """
        Initializes the MaxSharpeAllocator.

        Args:
            name: The name of this allocator instance.
            instruments: List of ticker symbols to include in the portfolio.
            allow_shorting: If True, allows negative weights (short positions).
            use_adj_close: If True, uses adjusted close prices; otherwise uses close prices.
            update_enabled: If True, rebalances portfolio at regular intervals.
            update_interval_value: Number of time units between rebalancing.
            update_interval_unit: Time unit for rebalancing ('days', 'weeks', or 'months').
        """
        super().__init__(
            name=name,
            instruments=instruments,
            allow_shorting=allow_shorting,
            use_adj_close=use_adj_close,
            update_enabled=update_enabled,
            update_interval_value=update_interval_value,
            update_interval_unit=update_interval_unit
        )

    def _get_optimization_name(self) -> str:
        """Returns the name of the optimization strategy for progress messages."""
        return "MaxSharpe"

    def _optimize(
        self,
        prices: pd.DataFrame,
        instruments: Set[str]
    ) -> Dict[str, float]:
        """
        Runs PyPortfolioOpt calculations to compute optimal allocations.

        Args:
            prices: DataFrame of historical prices with tickers as columns.
            instruments: Set of instrument tickers to compute allocations for.

        Returns:
            Dictionary mapping tickers to their optimal weights.
        """
        try:
            mu = expected_returns.mean_historical_return(
                prices, compounding=True, frequency=252
            )
            S = risk_models.CovarianceShrinkage(prices, frequency=252).ledoit_wolf()

            bounds = self._get_weight_bounds()
            ef = EfficientFrontier(mu, S, weight_bounds=bounds)
            ef.max_sharpe()
            computed_allocations = ef.clean_weights()

            # Validate weights don't contain NaN or Inf
            validated_allocations = {}
            for ticker, weight in computed_allocations.items():
                if math.isnan(weight) or math.isinf(weight):
                    logger.warning(
                        f"Invalid weight for {ticker}: {weight}, replacing with 0.0"
                    )
                    validated_allocations[ticker] = 0.0
                else:
                    validated_allocations[ticker] = weight

            return {
                inst: validated_allocations.get(inst, 0.0)
                for inst in instruments
            }

        except (ValueError, OptimizationError) as e:
            logger.error(f"MaxSharpe optimization failed: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error in MaxSharpe optimization: {e}")
            return {}

    def get_config(self) -> Dict[str, Any]:
        """
        Returns the configuration for serialization.

        Returns:
            Dictionary with all configuration needed to recreate this allocator.
        """
        return {
            "type": "max_sharpe",
            "name": self._name,
            "instruments": sorted(list(self._instruments)),
            "allow_shorting": self._allow_shorting,
            "use_adj_close": self._use_adj_close,
            "update_enabled": self._update_enabled,
            "update_interval_value": self._update_interval_value,
            "update_interval_unit": self._update_interval_unit
        }

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "MaxSharpeAllocator":
        """
        Creates a MaxSharpeAllocator from a configuration dictionary.

        Args:
            config: Dictionary with allocator configuration.

        Returns:
            MaxSharpeAllocator instance.
        """
        # Validate instruments type
        instruments = config.get("instruments", [])
        if not isinstance(instruments, list) or not all(isinstance(i, str) for i in instruments):
            raise ValueError("instruments must be a list of strings")

        return cls(
            name=config.get("name", "MaxSharpe Allocator"),
            instruments=instruments,
            allow_shorting=config.get("allow_shorting", False),
            use_adj_close=config.get("use_adj_close", True),
            update_enabled=config.get("update_enabled", False),
            update_interval_value=config.get("update_interval_value", 1),
            update_interval_unit=config.get("update_interval_unit", "days")
        )
