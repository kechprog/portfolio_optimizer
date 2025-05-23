# allocator/manual.py

from datetime import date, timedelta
from typing import Set, Dict, List, Optional, Type

import matplotlib.axes
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import pandas as pd
import numpy as np # For calculations like cumprod

# --- Import DataGetter ---
# This assumes app.py is run from the project root, making data_getter accessible.
# If running this file standalone or in a different context, sys.path might need adjustment.
try:
    from ..data_getter import YahooFinanceDataGetter
except ImportError:
    # Fallback for environments where data_getter isn't directly on the path during development/testing
    # This is generally not recommended for production code; structuring as a proper package is better.
    import sys
    import os
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from data_getter import YahooFinanceDataGetter

# Assuming PortfolioAllocator is in allocator.py in the same directory
from .allocator import PortfolioAllocator # Relative import for PortfolioAllocator

class ManualAllocator(PortfolioAllocator):
    """
    An allocator where the user manually specifies the allocation percentages
    for each instrument. It now fetches data and plots actual portfolio performance.
    """
    def __init__(self, name: str, initial_allocations: Optional[Dict[str, float]] = None):
        super().__init__(name)
        if initial_allocations is not None:
            self._allocations = {k: v for k, v in initial_allocations.items() if isinstance(v, (int,float))}
        self._problematic_tickers_during_plot_prep: List[str] = []


    def on_instruments_changed(self, new_instrument_set: Set[str]) -> None:
        updated_allocs: Dict[str, float] = {}
        changed = False
        for instrument in new_instrument_set:
            updated_allocs[instrument] = self._allocations.get(instrument, 0.0)
            if instrument not in self._allocations:
                changed = True
        
        for old_instrument in list(self._allocations.keys()):
            if old_instrument not in new_instrument_set:
                changed = True
                break 
        
        self._allocations = updated_allocs
        if changed:
            current_sum = sum(self._allocations.values())
            print(f"INFO ({self.name}): Allocations adjusted. Current sum: {current_sum:.4f}.")
            if abs(current_sum - 1.0) > 1e-7 and self._allocations:
                 print(f"WARNING ({self.name}): Allocations sum to {current_sum:.4f}, may need reconfiguration.")


    @classmethod
    def configure_or_create(cls: Type['ManualAllocator'],
                            parent_window: tk.Misc,
                            current_instruments: Set[str],
                            existing_allocator: Optional[PortfolioAllocator] = None,
                           ) -> Optional['ManualAllocator']:
        initial_name = f"Manual Allocator {str(uuid.uuid4())[:4]}" # Ensure unique default
        initial_allocs_for_dialog = {}

        if existing_allocator and isinstance(existing_allocator, ManualAllocator):
            initial_name = existing_allocator.name
            temp_existing_allocs = existing_allocator.allocations
            for instrument in current_instruments:
                initial_allocs_for_dialog[instrument] = temp_existing_allocs.get(instrument, 0.0)
        else:
            for instrument in current_instruments:
                initial_allocs_for_dialog[instrument] = 0.0

        dialog_title = f"Configure: {initial_name}" if existing_allocator else "Create New Manual Allocator"
        
        dialog = ManualAllocationDialog(parent_window,
                                        title=dialog_title,
                                        instruments=current_instruments,
                                        initial_allocations_percent= {k: v * 100.0 for k, v in initial_allocs_for_dialog.items()},
                                        initial_name=initial_name)

        if dialog.result_name is not None and dialog.result_allocations_percent is not None:
            final_allocations_decimal = {
                inst: perc / 100.0 for inst, perc in dialog.result_allocations_percent.items()
            }
            new_instance = cls(name=dialog.result_name, initial_allocations=final_allocations_decimal)
            print(f"INFO: ManualAllocator '{new_instance.name}' configured/created successfully.")
            return new_instance
        
        print(f"INFO: ManualAllocator configuration/creation cancelled for '{initial_name}'.")
        return None

    def prepare_plot_data(self, fitting_start_date_of_plot: date, plot_end_date: date) -> Optional[List[str]]:
        """
        Fetches historical data, calculates portfolio performance, and prepares for plotting.
        Returns a list of problematic tickers if data fetching/validation fails for any, else None.
        """
        self._plot_dates = []
        self._plot_values = []
        self._problematic_tickers_during_plot_prep = []

        instruments_to_fetch = {
            inst for inst, alloc_val in self.allocations.items() if isinstance(alloc_val, (float, int)) and alloc_val > 1e-9  # Use a small epsilon
        }

        if not instruments_to_fetch:
            print(f"INFO ({self.name}): No instruments with non-zero allocation. Nothing to plot for performance.")
            # Prepare a y=0 line as a fallback/indicator of no active investment
            current_date_iter = fitting_start_date_of_plot
            while current_date_iter <= plot_end_date:
                self._plot_dates.append(current_date_iter)
                self._plot_values.append(0.0)
                current_date_iter += timedelta(days=1)
            return None # No problematic tickers because none were required

        if fitting_start_date_of_plot > plot_end_date:
            print(f"WARNING ({self.name}): Plot start date is after plot end date. No performance data will be generated.")
            return None

        print(f"INFO ({self.name}): Fetching data for {instruments_to_fetch} from {fitting_start_date_of_plot} to {plot_end_date}")
        
        # Data fetching needs to cover the day before fitting_start_date_of_plot to calculate first pct_change
        fetch_start_date = fitting_start_date_of_plot - timedelta(days=7) # Fetch a bit more to find a trading day
                                                                       # and ensure we have data for pct_change on plot_start_date
        
        # Find the actual first trading day available before or on fitting_start_date_of_plot for pct_change base
        temp_data_for_start = YahooFinanceDataGetter.fetch(instruments_to_fetch, fetch_start_date, fitting_start_date_of_plot, interval="1d")
        
        actual_calc_start_date = fitting_start_date_of_plot
        if not temp_data_for_start.empty:
            # Get the last available date from this temp fetch. That will be our base for the first pct_change.
            # If temp_data_for_start.index contains fitting_start_date_of_plot, use that.
            # Otherwise, use the latest date available in temp_data_for_start.
            valid_indices_for_start = temp_data_for_start.index[temp_data_for_start.index.date <= fitting_start_date_of_plot]
            if not valid_indices_for_start.empty:
                fetch_start_date = valid_indices_for_start.max().date() # This date's close will be T-1 for pct_change
                actual_calc_start_date = fetch_start_date # The plot will effectively start showing changes *after* this date
            else: # No data found even before fitting_start_date_of_plot
                 print(f"WARNING ({self.name}): Could not find any trading day data up to {fitting_start_date_of_plot} for {instruments_to_fetch}.")
                 self._problematic_tickers_during_plot_prep = list(instruments_to_fetch) # Mark all as problematic
                 return self._problematic_tickers_during_plot_prep


        historical_data = YahooFinanceDataGetter.fetch(
            instruments_to_fetch,
            fetch_start_date, # Start fetching from adjusted date for pct_change
            plot_end_date,
            interval="1d"
        )

        if historical_data.empty:
            print(f"WARNING ({self.name}): No historical data returned for any requested instrument.")
            self._problematic_tickers_during_plot_prep = list(instruments_to_fetch)
            return self._problematic_tickers_during_plot_prep

        close_prices_frames = []
        for instrument in instruments_to_fetch:
            try:
                # yfinance returns MultiIndex columns: (Field, Ticker)
                # e.g., ('Close', 'AAPL')
                instrument_close_prices = historical_data[('Close', instrument)]
                if instrument_close_prices.isnull().all():
                    print(f"WARNING ({self.name}): All 'Close' prices for {instrument} are NaN.")
                    self._problematic_tickers_during_plot_prep.append(instrument)
                    continue
                instrument_close_prices = instrument_close_prices.ffill().bfill() # Fill NaNs
                if instrument_close_prices.isnull().any(): # Still NaNs after fill (e.g. full NaN series)
                    print(f"WARNING ({self.name}): 'Close' prices for {instrument} still contain NaNs after fill.")
                    self._problematic_tickers_during_plot_prep.append(instrument)
                    continue
                close_prices_frames.append(instrument_close_prices.rename(instrument)) # Rename Series to ticker name
            except KeyError:
                print(f"WARNING ({self.name}): 'Close' price data not found for {instrument}.")
                self._problematic_tickers_during_plot_prep.append(instrument)
        
        if self._problematic_tickers_during_plot_prep:
            # Even if some tickers are problematic, we might proceed with valid ones
            # Or decide to fail all if any one fails. For now, let's see if any valid data remains.
            print(f"INFO ({self.name}): Problematic tickers: {self._problematic_tickers_during_plot_prep}. Attempting to plot with remaining.")


        if not close_prices_frames:
            print(f"WARNING ({self.name}): No valid 'Close' price data available for any allocated instrument after validation.")
            return self._problematic_tickers_during_plot_prep # Return all initially problematic ones

        close_prices_df = pd.concat(close_prices_frames, axis=1)
        
        # Filter for the actual plotting period for returns calculation
        # pct_change needs one prior day, so data from actual_calc_start_date is used.
        # The returns themselves will be for dates > actual_calc_start_date.
        close_prices_for_returns = close_prices_df[close_prices_df.index.date >= actual_calc_start_date]


        if len(close_prices_for_returns) < 2: # Need at least two data points to calculate one return
            print(f"WARNING ({self.name}): Not enough data points ({len(close_prices_for_returns)}) to calculate returns after date filtering.")
            # Still return problematic tickers if any were identified earlier
            return self._problematic_tickers_during_plot_prep if self._problematic_tickers_during_plot_prep else None


        daily_returns = close_prices_for_returns.pct_change() # First row will be NaN
        
        # Align daily_returns with the requested plot start date (fitting_start_date_of_plot)
        # The first actual return will be for the day *after* the first date in daily_returns.index (if pct_change uses T and T-1)
        # So, if daily_returns.index[0] is actual_calc_start_date, then daily_returns.iloc[1] is the return for actual_calc_start_date+1day
        
        # We need to ensure daily_returns align with dates from fitting_start_date_of_plot onwards for the sum.
        # The pct_change is calculated on close_prices_for_returns which starts from actual_calc_start_date.
        # So the first valid return in daily_returns.iloc[1] corresponds to the change from actual_calc_start_date to actual_calc_start_date+1.
        # We want our plot to start showing 0% at fitting_start_date_of_plot.
        
        relevant_daily_returns = daily_returns[daily_returns.index.date >= fitting_start_date_of_plot].copy()
        relevant_daily_returns.dropna(how='all', inplace=True) # Drop rows where all returns are NaN (like the very first one if not handled)
        
        if relevant_daily_returns.empty:
            print(f"WARNING ({self.name}): No daily returns available in the plotting period starting {fitting_start_date_of_plot}.")
            # Fallback to y=0 plot if calculation fails but no tickers were "problematic" for data fetching
            current_date_iter = fitting_start_date_of_plot
            while current_date_iter <= plot_end_date:
                self._plot_dates.append(current_date_iter)
                self._plot_values.append(0.0)
                current_date_iter += timedelta(days=1)
            return self._problematic_tickers_during_plot_prep # Still report if any

        # Ensure allocations only for columns present in relevant_daily_returns
        allocations_for_calc = {
            inst: self.allocations.get(inst, 0.0) for inst in relevant_daily_returns.columns if inst in self.allocations
        }
        # Normalize allocations if they don't sum to 1 (e.g. if some tickers were dropped)
        current_alloc_sum = sum(allocations_for_calc.values())
        if current_alloc_sum > 1e-9 : # Avoid division by zero
            alloc_series = pd.Series({inst: alloc / current_alloc_sum for inst, alloc in allocations_for_calc.items()})
        else: # All allocated instruments had issues or 0 allocation
            alloc_series = pd.Series(allocations_for_calc) # Will result in 0 portfolio return

        # Filter relevant_daily_returns columns to match alloc_series index
        # This ensures dot product works correctly if some instruments were dropped.
        cols_to_use = [col for col in alloc_series.index if col in relevant_daily_returns.columns]
        filtered_daily_returns = relevant_daily_returns[cols_to_use]
        aligned_alloc_series = alloc_series[cols_to_use]

        if filtered_daily_returns.empty: # If all instruments with allocation had no return data
             print(f"WARNING ({self.name}): No return data for any allocated and valid instrument.")
             current_date_iter = fitting_start_date_of_plot
             while current_date_iter <= plot_end_date:
                self._plot_dates.append(current_date_iter)
                self._plot_values.append(0.0)
                current_date_iter += timedelta(days=1)
             return self._problematic_tickers_during_plot_prep


        portfolio_daily_returns = filtered_daily_returns.mul(aligned_alloc_series, axis=1).sum(axis=1)

        # Cumulative returns calculation
        # Start plot with 0% return on fitting_start_date_of_plot
        self._plot_dates.append(fitting_start_date_of_plot)
        self._plot_values.append(0.0)

        # Calculate cumulative product for subsequent days
        # Ensure portfolio_daily_returns index starts from fitting_start_date_of_plot
        # If the first date in portfolio_daily_returns.index is fitting_start_date_of_plot,
        # its value is the return FOR that day (relative to previous).
        # We need to align this carefully.

        # Let's ensure portfolio_daily_returns are only for dates > fitting_start_date_of_plot if the first day is 0.
        # The first data point in portfolio_daily_returns is the return on its index date.
        
        # If fitting_start_date_of_plot is not in portfolio_daily_returns.index,
        # it means no return was calculated for that specific day (e.g. non-trading day)
        # or it was the base day.
        
        # Correct approach:
        # The returns in portfolio_daily_returns are for the date in their index.
        # (1 + r).cumprod() - 1 gives cumulative return.
        # The plot starts at (fitting_start_date_of_plot, 0%).
        # The next point is (first_return_date, (1+first_return)-1).

        cumulative_returns_calc = (1 + portfolio_daily_returns).cumprod() - 1
        
        # Add these calculated points
        # Ensure that the dates added are strictly after fitting_start_date_of_plot
        # if fitting_start_date_of_plot itself is already added with 0%
        for idx_date, cum_ret_val in cumulative_returns_calc.items():
            current_dt = idx_date.date() if isinstance(idx_date, pd.Timestamp) else idx_date
            if current_dt > fitting_start_date_of_plot: # Add if not already the start date
                if not self._plot_dates or current_dt > self._plot_dates[-1]: # Ensure chronological and no duplicates
                    self._plot_dates.append(current_dt)
                    self._plot_values.append(cum_ret_val * 100.0) # Convert to percentage
            elif current_dt == fitting_start_date_of_plot: # If returns start on fitting_start_date_of_plot
                # Update the 0.0 value if it was already added for this date
                if self._plot_dates and self._plot_dates[0] == fitting_start_date_of_plot:
                    self._plot_values[0] = cum_ret_val * 100.0
                else: # This case should be rare if logic is correct
                    self._plot_dates.append(current_dt)
                    self._plot_values.append(cum_ret_val * 100.0)

        # If after all calculations, plot_dates still only has the initial (start_date, 0.0) point,
        # it means no valid subsequent returns were computed.
        if len(self._plot_dates) <= 1 and not self._problematic_tickers_during_plot_prep:
            print(f"INFO ({self.name}): Performance calculation resulted in no subsequent data points after {fitting_start_date_of_plot}.")
            # Keep the (start_date, 0.0) to indicate it tried but had no further returns.
            # Or revert to y=0 line for the whole period if that's preferred.
            # For now, it will just plot the single 0% point, or y=0 if instruments_to_fetch was empty.

        return self._problematic_tickers_during_plot_prep if self._problematic_tickers_during_plot_prep else None


    def draw_plot(self, ax: matplotlib.axes.Axes) -> None:
        if self._plot_dates and self._plot_values:
            label_suffix = " (Performance)"
            if self._problematic_tickers_during_plot_prep:
                label_suffix += f" - Partial data, issues with: {', '.join(self._problematic_tickers_during_plot_prep[:2])}{'...' if len(self._problematic_tickers_during_plot_prep)>2 else ''}"
            elif not any(v > 1e-9 for v in self._allocations.values()): # Check if all allocations are effectively zero
                 label_suffix = " (No Allocation)"

            ax.plot(self._plot_dates, self._plot_values, linestyle='-', label=f"{self.name}{label_suffix}")
        else: # No data prepared, or calculation failed to produce points
            ax.plot([],[], label=f"{self.name} (No performance data)") # Add to legend that it's missing
            print(f"DEBUG ({self.name}): No plot data to draw. Dates: {len(self._plot_dates)}, Values: {len(self._plot_values)}")

# --- ManualAllocationDialog (mostly same as before, ensure it's using % for display/input) ---
# Minor change: initial_allocations_percent in __init__ for clarity.
# No changes needed to ManualAllocationDialog from `allocator_py_v3` based on this request's focus.
# It already handles name and allocations in percent.
# The import 'uuid' was in ManualAllocator.configure_or_create, so it needs to be at the top of manual.py
import uuid # For unique default names if needed

class ManualAllocationDialog(simpledialog.Dialog):
    def __init__(self, parent, title: str, instruments: Set[str],
                 initial_allocations_percent: Dict[str, float], # Expects 0-100 scale
                 initial_name: str):
        self.instruments = sorted(list(instruments))
        self.initial_allocations_percent = initial_allocations_percent # 0-100 scale
        self.initial_name = initial_name

        self.name_var = tk.StringVar(value=self.initial_name)
        self.entries: Dict[str, tk.Entry] = {}
        self.sum_label_var = tk.StringVar()
        self.sum_label_widget: Optional[ttk.Label] = None

        self.result_name: Optional[str] = None
        self.result_allocations_percent: Optional[Dict[str, float]] = None # 0-100 scale
        super().__init__(parent, title)

    def body(self, master_frame: tk.Frame) -> tk.Entry | None:
        master_frame.pack_configure(padx=10, pady=10)

        name_frame = ttk.Frame(master_frame)
        name_frame.pack(side="top", fill="x", pady=(0, 10))
        ttk.Label(name_frame, text="Allocator Name:").pack(side="left", padx=(0,5))
        name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=30)
        name_entry.pack(side="left", fill="x", expand=True)

        ttk.Separator(master_frame, orient='horizontal').pack(side="top", fill='x', pady=5)
        
        alloc_area_frame = ttk.Frame(master_frame)
        alloc_area_frame.pack(side="top", fill="both", expand=True)

        canvas = tk.Canvas(alloc_area_frame, borderwidth=0, width=380, height=250)
        scrollbar = ttk.Scrollbar(alloc_area_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        if len(self.instruments) > 7:
            scrollbar.pack(side="right", fill="y")

        ttk.Label(scrollable_frame, text="Instrument", font=('Helvetica', 10, 'bold')).grid(row=0, column=0, padx=5, pady=3, sticky="w")
        ttk.Label(scrollable_frame, text="Allocation (%)", font=('Helvetica', 10, 'bold')).grid(row=0, column=1, padx=5, pady=3, sticky="w")

        vcmd = (master_frame.register(self._validate_percentage_input), '%P')

        for i, instrument_name in enumerate(self.instruments):
            ttk.Label(scrollable_frame, text=instrument_name + ":").grid(row=i + 1, column=0, padx=5, pady=3, sticky="w")
            entry = ttk.Entry(scrollable_frame, width=10, validate="key", validatecommand=vcmd)
            initial_val_str = f"{self.initial_allocations_percent.get(instrument_name, 0.0):.2f}"
            entry.insert(0, initial_val_str)
            entry.grid(row=i + 1, column=1, padx=5, pady=3, sticky="ew")
            entry.bind("<KeyRelease>", self._update_sum)
            entry.bind("<FocusOut>", self._update_sum)
            self.entries[instrument_name] = entry
        
        sum_frame = ttk.Frame(master_frame)
        sum_frame.pack(side="top", fill="x", pady=(10,0))
        ttk.Label(sum_frame, text="Current Sum (%):").pack(side="left", padx=5)
        self.sum_label_widget = ttk.Label(sum_frame, textvariable=self.sum_label_var)
        self.sum_label_widget.pack(side="left")
        self._update_sum()

        return name_entry

    def _validate_percentage_input(self, P: str) -> bool:
        if P == "": return True
        try:
            val = float(P)
            return 0.0 <= val <= 100.0
        except ValueError:
            return False

    def _update_sum(self, event=None) -> None:
        current_sum = 0.0
        for entry_widget in self.entries.values():
            try:
                val_str = entry_widget.get()
                if val_str: current_sum += float(val_str)
            except ValueError: pass
        
        self.sum_label_var.set(f"{current_sum:.2f}")
        if self.sum_label_widget:
            if abs(current_sum - 100.0) < 1e-7 or (not self.instruments and abs(current_sum) < 1e-7): # Handles case with no instruments sum=0 is ok
                self.sum_label_widget.configure(foreground="green")
            else:
                self.sum_label_widget.configure(foreground="red")

    def validate(self) -> bool:
        allocator_name = self.name_var.get().strip()
        if not allocator_name:
            messagebox.showerror("Validation Error", "Allocator Name cannot be empty.", parent=self)
            try: self.winfo_children()[0].winfo_children()[1].focus_set()
            except Exception: pass
            return False
        self.result_name = allocator_name

        current_sum = 0.0
        temp_allocations_percent = {}
        if not self.instruments:
            self.result_allocations_percent = {}
            return True

        for instrument_name, entry_widget in self.entries.items():
            try:
                val_str = entry_widget.get()
                if not val_str: val_str = "0.0"
                percentage = float(val_str)
                if not (0.0 <= percentage <= 100.0):
                    messagebox.showerror("Validation Error", f"Allocation for {instrument_name} must be between 0 and 100.", parent=self)
                    entry_widget.focus_set()
                    return False
                temp_allocations_percent[instrument_name] = percentage
                current_sum += percentage
            except ValueError:
                messagebox.showerror("Validation Error", f"Invalid number for {instrument_name}.", parent=self)
                entry_widget.focus_set()
                return False
        
        if abs(current_sum - 100.0) > 1e-7:
            messagebox.showerror("Validation Error", f"Allocations must sum to 100%. Current sum is {current_sum:.2f}%.", parent=self)
            return False
        
        self.result_allocations_percent = temp_allocations_percent
        return True

    def apply(self) -> None:
        pass

    def buttonbox(self) -> None:
        box = ttk.Frame(self)
        self.ok_button = ttk.Button(box, text="Save Allocator", width=15, command=self.ok, default=tk.ACTIVE)
        self.ok_button.pack(side=tk.LEFT, padx=5, pady=5)
        cancel_button = ttk.Button(box, text="Cancel", width=10, command=self.cancel)
        cancel_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack(side=tk.BOTTOM, pady=5)