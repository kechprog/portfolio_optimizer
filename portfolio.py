\
from datetime import date
from typing import List, Dict, Any, Optional

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

        The new segment starts where the previous one ended, or from the
        portfolio\'s initial_start_date if this is the first segment.

        Args:
            end_date: The end date for this new allocation segment.
            allocations: A dictionary representing the asset allocations
                         (e.g., {"TICKER": 0.6, "OTHER": 0.4}) for this segment.

        Raises:
            TypeError: If arguments are of incorrect types.
            ValueError: If end_date is not after the segment\'s start_date.
        """
        if not isinstance(end_date, date):
            raise TypeError("end_date must be a datetime.date object.")
        if not isinstance(allocations, dict):
            raise TypeError("allocations must be a dictionary.")
        for ticker, weight in allocations.items():
            if not isinstance(ticker, str) or not isinstance(weight, (float, int)):
                raise TypeError(
                    "Allocations dictionary must have string keys and float/int values."
                )

        current_segment_start_date: date
        if not self.segments:
            current_segment_start_date = self.initial_start_date
        else:
            current_segment_start_date = self.segments[-1]['end_date']

        if end_date <= current_segment_start_date:
            raise ValueError(
                f"The end_date ({end_date}) must be after the segment\'s start_date ({current_segment_start_date})."
            )

        self.segments.append({
            'start_date': current_segment_start_date,
            'end_date': end_date,
            'allocations': allocations.copy() # Store a copy
        })

    def get(self, query_end_date: date) -> List[Dict[str, Any]]:
        """
        Retrieves a list of portfolio segments up to a specified end date.

        Segments are "cropped" if the query_end_date falls within them.
        Only segments (or parts of segments) that occur before or at query_end_date
        and after or at initial_start_date are returned.

        Args:
            query_end_date: The date up to which portfolio segments should be retrieved.

        Returns:
            A list of segment dictionaries. Each dictionary contains:
            {'start_date': date, 'end_date': date, 'allocations': Dict[str, float]}.
            Returns an empty list if query_end_date is before initial_start_date
            or no segments are defined.
        """
        if not isinstance(query_end_date, date):
            raise TypeError("query_end_date must be a datetime.date object.")

        if query_end_date < self.initial_start_date:
            return []

        result_segments: List[Dict[str, Any]] = []
        for segment in self.segments:
            # Skip segments that entirely start after or at the query_end_date
            if segment['start_date'] >= query_end_date:
                continue

            # Determine the effective start and end for this segment based on query_end_date
            effective_segment_start = segment['start_date']
            effective_segment_end = min(segment['end_date'], query_end_date)

            # Only include the segment if it has a valid, positive duration within the query range
            if effective_segment_end > effective_segment_start:
                result_segments.append({
                    'start_date': effective_segment_start,
                    'end_date': effective_segment_end,
                    'allocations': segment['allocations'] # Already a copy from append
                })
        
        return result_segments

    def plot(self, plotter_handle: Any, query_end_date: date) -> None:
        """
        Visualizes the portfolio\'s segments up to a specified end date.

        For now, this method prints the segments that would be plotted.
        The actual plotting logic using plotter_handle will be implemented later.

        Args:
            plotter_handle: A handle to a plotting utility (e.g., matplotlib Axes object).
                            Currently unused beyond being an argument.
            query_end_date: The date up to which the portfolio should be plotted.
        """
        if not isinstance(query_end_date, date):
            raise TypeError("query_end_date must be a datetime.date object.")

        segments_to_plot = self.get(query_end_date)

        if not segments_to_plot:
            print(f"Portfolio.plot: No segments to plot up to {query_end_date}.")
            return

        print(f"Portfolio.plot: Visualizing portfolio up to {query_end_date} using plotter_handle ({type(plotter_handle)}):")
        for i, segment in enumerate(segments_to_plot):
            print(
                f"  Segment {i+1}: From {segment['start_date']} to {segment['end_date']}, "
                f"Allocations: {segment['allocations']}"
            )
        # In a future implementation, this is where plotter_handle would be used
        # to draw the performance/allocations for each segment.
        # This would involve:
        # 1. For each segment:
        #    a. Fetching historical price data for assets in segment['allocations']
        #       between segment['start_date'] and segment['end_date'].
        #    b. Calculating portfolio daily returns based on segment['allocations'].
        #    c. Calculating cumulative returns for this segment.
        #    d. Plotting these cumulative returns, potentially chaining them visually
        #       if there are multiple segments.
        print("Portfolio.plot: (Actual plotting logic to be implemented)")