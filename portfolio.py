
from datetime import date, timedelta
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
from data_getter import av_fetcher

class Portfolio:
    """
    Manages a portfolio whose allocations can change over discrete time periods.
    """

    def __init__(self, start_date: date):
        """
        Initializes the Portfolio with a global start date.

        Args:
            start_date: The date from which the first segment of the portfolio will begin.
        """
        if not isinstance(start_date, date):
            raise TypeError("start_date must be a datetime.date object.")
        self.initial_start_date: date = start_date
        self.segments: List[Dict[str, Any]] = []
        # Each segment is a dict: {'start_date': date, 'end_date': date, 'allocations': Dict[str, float]}

    def append(self, end_date: date, allocations: Dict[str, float]) -> None:
        """
        Appends a new allocation segment to the portfolio.
        """
        if not isinstance(end_date, date):
            raise TypeError("end_date must be a datetime.date object.")
        if not isinstance(allocations, dict):
            raise TypeError("allocations must be a dictionary.")
        for ticker, weight in allocations.items():
            if not isinstance(ticker, str) or not isinstance(weight, (float, int)):
                raise TypeError("Allocations must have string keys and float/int values.")
        if not self.segments:
            segment_start = self.initial_start_date
        else:
            segment_start = self.segments[-1]['end_date']
        if end_date <= segment_start:
            raise ValueError(f"end_date ({end_date}) must be after start_date ({segment_start}).")
        self.segments.append({
            'start_date': segment_start,
            'end_date': end_date,
            'allocations': allocations.copy()
        })

    def get(self, query_end_date: date) -> List[Dict[str, Any]]:
        """
        Retrieves a list of portfolio segments up to a specified end date.
        """
        if not isinstance(query_end_date, date):
            raise TypeError("query_end_date must be a datetime.date object.")
        if query_end_date < self.initial_start_date:
            return []
        result = []
        for seg in self.segments:
            if seg['start_date'] >= query_end_date:
                continue
            start = seg['start_date']
            end = min(seg['end_date'], query_end_date)
            if end > start:
                result.append({'start_date': start, 'end_date': end, 'allocations': seg['allocations']})
        return result

    def plot(self, ax: Any, query_end_date: date, include_dividends: bool = False, label: str = ""):
        """
        Plots the portfolio's performance up to a given date on the provided Axes.

        Args:
            ax: A matplotlib Axes object to draw on.
            query_end_date: The date up to which to plot.
            include_dividends: Whether to use adjusted close prices.
            label: Label for this portfolio (used in legend).
        """
        if not isinstance(query_end_date, date):
            raise TypeError("query_end_date must be a datetime.date object.")

        segments = self.get(query_end_date)
        if not segments:
            ax.plot([], [], label=f"{label} (No data)")
            return

        # Accumulate a single continuous series
        dates_all = []
        values_all = []
        cumulative_factor = 1.0
        for seg in segments:
            start = seg['start_date']
            end = seg['end_date']
            allocs = {t: w for t, w in seg['allocations'].items() if abs(w) > 1e-9}
            if not allocs:
                continue
            tickers = {t.upper() for t in allocs}
            try:
                raw_df, _ = av_fetcher(
                    tickers,
                    pd.to_datetime(start),
                    pd.to_datetime(end)
                )
            except Exception:
                continue
            field = 'AdjClose' if include_dividends else 'Close'
            try:
                price_df = raw_df.xs(field, level='Field', axis=1, drop_level=True)
            except Exception:
                continue
            price_df = price_df.ffill().bfill()
            returns = price_df.pct_change().dropna(how='all')
            returns = returns[returns.index.date >= start]
            if returns.empty:
                continue
            weights = pd.Series({col: allocs.get(col, 0.0) for col in returns.columns})
            port_ret = returns.mul(weights, axis=1).sum(axis=1)
            cum_series = (1 + port_ret).cumprod() * cumulative_factor
            # Prepare points
            seg_dates = [start] + [ts.date() for ts in cum_series.index]
            seg_factors = [cumulative_factor] + cum_series.tolist()
            # Convert to percentage returns
            for dt, factor in zip(seg_dates, seg_factors):
                dates_all.append(dt)
                values_all.append((factor - 1.0) * 100.0)
            cumulative_factor = seg_factors[-1] if seg_factors else cumulative_factor

        # Single plot call
        ax.plot(dates_all, values_all, linestyle='-', label=label)

    def plot_distribution(self, ax: Any, end_date: date):
        """
        Plots the distribution of the portfolio's assets over time.

        Args:
            ax: A matplotlib Axes object to draw on.
            end_date: The date up to which to plot.
        """
        segments = self.get(end_date)
        if not segments:
            return

        # Create a DataFrame to hold the allocation history
        dates = sorted(list(set([seg['start_date'] for seg in segments] + [end_date])))
        all_tickers = sorted(list(set(ticker for seg in segments for ticker in seg['allocations'])))        
        alloc_df = pd.DataFrame(index=dates, columns=all_tickers, data=0.0)

        for seg in segments:
            for ticker, weight in seg['allocations'].items():
                alloc_df.loc[seg['start_date']:seg['end_date'], ticker] = weight*100

        # Plot the stacked area chart
        ax.stackplot(alloc_df.index, alloc_df.T, labels=alloc_df.columns)
        ax.set_ylim(0, 100)
        ax.set_ylabel("Allocation (%)")
        ax.legend(loc='upper left')

    @staticmethod
    def merge(portfolios_with_weights: List[Tuple['Portfolio', float]], 
              start_date: date, end_date: date) -> 'Portfolio':
        """
        Merges multiple portfolios with specified weights into a single portfolio.
        
        This function combines portfolios like Riemann partitions - it finds all segment
        boundaries across all portfolios and creates a new portfolio where each segment
        contains the weighted combination of allocations from all constituent portfolios.
        
        Args:
            portfolios_with_weights: List of tuples (portfolio, weight) where weights should sum to 1.0
            start_date: Start date for the merged portfolio
            end_date: End date for the merged portfolio
            
        Returns:
            A new Portfolio object containing the merged allocations
            
        Raises:
            ValueError: If weights don't sum to approximately 1.0
            TypeError: If inputs are not of correct types
        """
        if not portfolios_with_weights:
            # Return empty portfolio if no input portfolios
            empty_portfolio = Portfolio(start_date)
            empty_portfolio.append(end_date, {})
            return empty_portfolio
        
        # Validate weights
        total_weight = sum(weight for _, weight in portfolios_with_weights)
        if abs(total_weight - 1.0) > 1e-6:
            raise ValueError(f"Portfolio weights must sum to 1.0, got {total_weight}")
        
        # Collect all segment boundaries from all portfolios
        all_boundaries = {start_date, end_date}
        
        for portfolio, _ in portfolios_with_weights:
            # Get all segments up to end_date
            segments = portfolio.get(end_date)
            for segment in segments:
                all_boundaries.add(segment['start_date'])
                all_boundaries.add(segment['end_date'])
        
        # Sort boundaries to create intervals
        sorted_boundaries = sorted(all_boundaries)
        
        # Create the merged portfolio
        merged_portfolio = Portfolio(start_date)
        
        # Process each interval between consecutive boundaries
        for i in range(len(sorted_boundaries) - 1):
            interval_start = sorted_boundaries[i]
            interval_end = sorted_boundaries[i + 1]
            
            # Skip intervals outside our target range
            if interval_end <= start_date or interval_start >= end_date:
                continue
            
            # Clip interval to our target range
            actual_start = max(interval_start, start_date)
            actual_end = min(interval_end, end_date)
            
            if actual_start >= actual_end:
                continue
            
            # Find the midpoint of this interval to query allocations
            midpoint = actual_start + (actual_end - actual_start) // 2
            
            # Combine allocations from all portfolios for this interval
            combined_allocations = {}
            
            for portfolio, weight in portfolios_with_weights:
                # Get segments that cover the midpoint
                covering_segments = portfolio.get(midpoint)
                
                if covering_segments:
                    # Find the segment that actually contains the midpoint
                    active_allocation = None
                    for segment in covering_segments:
                        if segment['start_date'] <= midpoint < segment['end_date']:
                            active_allocation = segment['allocations']
                            break
                    
                    # If no exact match, use the last segment
                    if active_allocation is None and covering_segments:
                        active_allocation = covering_segments[-1]['allocations']
                    
                    # Add weighted allocations
                    if active_allocation:
                        for instrument, allocation in active_allocation.items():
                            if instrument not in combined_allocations:
                                combined_allocations[instrument] = 0.0
                            combined_allocations[instrument] += allocation * weight
            
            # Filter out negligible allocations
            filtered_allocations = {
                instrument: alloc 
                for instrument, alloc in combined_allocations.items() 
                if abs(alloc) > 1e-9
            }
            
            # Add this segment to the merged portfolio
            if filtered_allocations or i == len(sorted_boundaries) - 2:  # Always add last segment
                merged_portfolio.append(actual_end, filtered_allocations)
        
        return merged_portfolio

if __name__ == "__main__":
    # Simple test of Portfolio functionality
    portfolio = Portfolio(start_date=date(2023, 1, 1))
    portfolio.append(date(2023, 6, 30), {'AAPL': 0.5, 'GOOG': 0.5})
    portfolio.append(date(2023, 12, 31), {'AAPL': 0.3, 'GOOG': 0.3, 'MSFT': 0.4})
    
    print(f"Portfolio has {len(portfolio.segments)} segments")
    
    # Test merge functionality
    portfolio2 = Portfolio(start_date=date(2023, 1, 1))
    portfolio2.append(date(2023, 12, 31), {'NVDA': 0.6, 'TSLA': 0.4})
    
    merged = Portfolio.merge(
        [(portfolio, 0.7), (portfolio2, 0.3)], 
        date(2023, 1, 1), 
        date(2023, 12, 31)
    )
    
    print(f"Merged portfolio has {len(merged.segments)} segments")
    print("Portfolio merge test completed successfully")
