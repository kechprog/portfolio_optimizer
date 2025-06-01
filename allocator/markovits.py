# portfolio_optimizer/allocator/markovits.py

from typing import Set, Dict, Optional, Type, Any # Added Any
from datetime import date
import pandas as pd
from pypfopt import EfficientFrontier # Removed objective_functions as not directly used by name
from pypfopt import risk_models
from pypfopt import expected_returns
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import uuid

from .allocator import PortfolioAllocator, PAL
from config import get_fetcher
Fetcher = get_fetcher()

class MarkovitsAllocator(PortfolioAllocator):
    OPTIMIZATION_TARGETS = {
        "Maximize Sharpe Ratio": "max_sharpe",
        "Minimize Volatility": "min_volatility",
        # Future: "Efficient Return": "efficient_return",
        # Future: "Efficient Risk": "efficient_risk",
    }
    # Default target if not specified or invalid
    DEFAULT_OPTIMIZATION_TARGET = "min_volatility"


    def __init__(self, name: str,
                 initial_instruments: Optional[Set[str]] = None, # Kept for direct instantiation if needed
                 allow_shorting: bool = False, # Default for new instances
                 optimization_target: str = DEFAULT_OPTIMIZATION_TARGET, # Default for new
                 target_return_value: Optional[float] = None):
        super().__init__(name)
        self._instruments: Set[str] = initial_instruments if initial_instruments is not None else set()
        self._allow_shorting: bool = allow_shorting
        # Ensure optimization_target is a valid internal value
        if optimization_target not in self.OPTIMIZATION_TARGETS.values():
            print(f"Warning ({name}): Invalid optimization_target '{optimization_target}' provided to __init__. Defaulting to {self.DEFAULT_OPTIMIZATION_TARGET}.")
            self.optimization_target: str = self.DEFAULT_OPTIMIZATION_TARGET
        else:
            self.optimization_target: str = optimization_target
        self.target_return_value: Optional[float] = target_return_value # For future "efficient_return"
        self._allocations: Dict[str, float] = {} # Computed allocations

    def on_instruments_changed(self, new_instruments: Set[str]) -> None:
        if self._instruments != new_instruments:
            self._instruments = new_instruments.copy()
            self._allocations = {} # Clear previously computed allocations as instrument set changed
            print(f"INFO ({self.name}): Instruments changed. Allocations cleared and will be recomputed.")


    def compute_allocations(self, fitting_start_date: date, fitting_end_date: date) -> Dict[str, float]:
        # Initialize allocations to zero for all requested instruments
        self._allocations = {instrument: 0.0 for instrument in self._instruments}

        if not self._instruments:
            print(f"WARNING ({self.name}): No instruments supplied. Cannot compute allocations.")
            return self._allocations.copy()

        print(f"INFO ({self.name}): Computing allocations for {self._instruments} from {fitting_start_date} to {fitting_end_date}.")
        
        # Fetcher now returns (DataFrame, Set[str] of flawed tickers)
        # The fetcher handles normalization of tickers for API calls (e.g., to uppercase for AV)
        # We expect the 'Ticker' level in the returned MultiIndex to match the case of our internal self._instruments
        # if the fetcher is designed to map back. Let's assume for now fetcher returns Tickers in the casing it received them
        # or we use a mapping if Fetcher standardizes output Ticker casing (e.g. always uppercase).
        # Given _create_fetcher returns uppercase tickers in MultiIndex, adapt here.
        
        requested_instruments_upper = {t.upper() for t in self._instruments}
        # Keep a mapping from the upper-cased version back to the original for final allocations
        # This is important if self._instruments can have mixed casing.
        upper_to_original_ticker_map = {t.upper(): t for t in self._instruments}

        try:
            raw_data_df, flawed_tickers_from_fetcher_upper = Fetcher.fetch(
                requested_instruments_upper, # Pass uppercase set to fetcher
                fitting_start_date,
                fitting_end_date,
                interval="1d",
                include_dividends=True # Markovits typically uses adjusted prices
            )
        except Exception as e: # Catch broad exceptions from fetcher call itself
            print(f"ERROR ({self.name}): Data fetching call failed: {e}")
            return self._allocations.copy() # Returns all zeros

        if raw_data_df.empty:
            print(f"WARNING ({self.name}): No data returned from fetcher. All instruments ({self._instruments}) might be flawed.")
            # All allocations remain 0.0
            return self._allocations.copy()

        # Determine valid instruments for optimization based on fetcher's feedback
        # Flawed tickers from fetcher are uppercase. Ensure it's a set for the difference operation.
        valid_instruments_upper = requested_instruments_upper - set(flawed_tickers_from_fetcher_upper)
        
        if not valid_instruments_upper:
            print(f"WARNING ({self.name}): No valid instruments after fetcher processing. Flawed: {flawed_tickers_from_fetcher_upper}")
            return self._allocations.copy() # All allocations remain 0.0

        prices_df_list = []
        
        # The fetcher should ideally return 'AdjClose' if include_dividends was True and successful,
        # otherwise 'Close'. We check for 'AdjClose' first.
        # The Ticker level in raw_data_df.columns should be uppercase based on _create_fetcher.
        preferred_field = 'AdjClose'
        fallback_field = 'Close'

        for ticker_upper in valid_instruments_upper:
            original_ticker = upper_to_original_ticker_map[ticker_upper] # Get original case for series name
            price_series: Optional[pd.Series] = None
            
            if (preferred_field, ticker_upper) in raw_data_df.columns:
                price_series = raw_data_df[(preferred_field, ticker_upper)]
                # print(f"INFO ({self.name}): Using '{preferred_field}' data for {original_ticker} ({ticker_upper})")
            elif (fallback_field, ticker_upper) in raw_data_df.columns:
                price_series = raw_data_df[(fallback_field, ticker_upper)]
                print(f"INFO ({self.name}): Using '{fallback_field}' data for {original_ticker} ({ticker_upper}) as '{preferred_field}' not found.")
            else:
                print(f"WARNING ({self.name}): Price data for {original_ticker} ({ticker_upper}) not found in fetched data columns. Skipping.")
                # This ticker, though not in flawed_tickers_from_fetcher, doesn't have expected data columns.
                # It will be excluded from optimization. Allocations will remain 0.
                continue

            if price_series is not None and not price_series.dropna().empty:
                prices_df_list.append(price_series.dropna().rename(original_ticker))
            else:
                print(f"WARNING ({self.name}): All price data for {original_ticker} ({ticker_upper}) was NaN or series was None. Skipping.")
                # This ticker will be excluded. Allocations will remain 0.
        
        if not prices_df_list:
            print(f"WARNING ({self.name}): No valid price series found for any of the instruments post-extraction. Cannot compute.")
            return self._allocations.copy() # All allocations remain 0.0
            
        prices = pd.concat(prices_df_list, axis=1).sort_index()
        
        # Date alignment: find common date range after individual series processing
        if prices.shape[0] > 1 and prices.shape[1] > 0:
            # Ensure all series start and end on common ground for reliable cov matrix
            common_start = prices.apply(lambda col: col.first_valid_index()).max()
            common_end = prices.apply(lambda col: col.last_valid_index()).min()
            if pd.notna(common_start) and pd.notna(common_end) and common_start < common_end:
                prices = prices.loc[common_start:common_end]
            else:
                print(f"WARNING ({self.name}): Could not determine common date range. Start: {common_start}, End: {common_end}. Using available data.")
        
        prices = prices.ffill().bfill() # Fill any gaps
        prices.dropna(axis=1, how='all', inplace=True) # Drop columns that are still all NaN

        if prices.empty or prices.shape[0] < 2 or prices.shape[1] == 0 :
            print(f"WARNING ({self.name}): Not enough historical data points or instruments ({prices.shape}) after processing. Cannot compute.")
            return self._allocations.copy()

        # Check for instruments that were intended for optimization but got dropped (e.g. all NaN)
        final_instruments_for_opt = set(prices.columns) # These are original cased tickers
        
        # At this point, `prices` DataFrame has original-cased tickers as columns
        try:
            mu = expected_returns.mean_historical_return(prices, compounding=True, frequency=252)
            S = risk_models.CovarianceShrinkage(prices, frequency=252).ledoit_wolf()
        except Exception as e:
            print(f"ERROR ({self.name}): Could not calculate mu/S: {e}. Prices shape: {prices.shape}, Columns: {prices.columns}")
            return self._allocations.copy()

        weight_bounds = (-1.0 if self._allow_shorting else 0.0, 1.0)
        
        # mu and S are indexed by original_ticker names
        ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)

        try:
            if self.optimization_target == "max_sharpe":
                ef.max_sharpe()
            elif self.optimization_target == "min_volatility":
                ef.min_volatility()
            else: 
                print(f"WARNING ({self.name}): Unknown optimization target '{self.optimization_target}'. Defaulting to max_sharpe.")
                ef.max_sharpe()
            
            cleaned_weights = ef.clean_weights() # These weights are for original_ticker names
            
            # Update the self._allocations (initialized to all zeros) with the computed weights
            for ticker, weight in cleaned_weights.items():
                if ticker in self._allocations: # Should always be true if ticker was in final_instruments_for_opt
                    self._allocations[ticker] = weight
                else: # Should not happen if logic is correct
                    print(f"WARNING ({self.name}): Ticker {ticker} from optimization not in original instrument list. This is unexpected.")

            print(f"INFO ({self.name}): Computed allocations: {self._allocations}")
            return self._allocations.copy()

        except ValueError as ve: # Often from pypfopt if optimization is impossible
             print(f"ERROR ({self.name}): Optimization failed for '{self.optimization_target}': {ve}")
             # self._allocations already reflects zeros for uncomputed instruments
             return self._allocations.copy()
        except Exception as e:
            print(f"ERROR ({self.name}): Unexpected error during optimization: {e}")
            return self._allocations.copy()

    @classmethod
    def configure_or_create(cls: Type['MarkovitsAllocator'],
                            parent_window: tk.Misc,
                            current_instruments: Set[str],
                            existing_allocator: Optional[PortfolioAllocator] = None
                           ) -> Optional['MarkovitsAllocator']:
        initial_name = f"Markovits Allocator {str(uuid.uuid4())[:4]}"
        initial_allow_shorting = False
        initial_opt_target_key = "Maximize Sharpe Ratio" # Default display key

        if existing_allocator and isinstance(existing_allocator, MarkovitsAllocator):
            initial_name = existing_allocator.name
            initial_allow_shorting = existing_allocator._allow_shorting
            for k, v_internal in cls.OPTIMIZATION_TARGETS.items():
                if v_internal == existing_allocator.optimization_target:
                    initial_opt_target_key = k
                    break
        
        dialog = MarkovitsConfigDialog(parent_window,
                                       title=f"Configure: {initial_name}" if existing_allocator else "Create Markovits Allocator",
                                       initial_name=initial_name,
                                       initial_allow_shorting=initial_allow_shorting,
                                       initial_optimization_target_key=initial_opt_target_key,
                                       available_targets=cls.OPTIMIZATION_TARGETS)
        
        if dialog.result_name is not None:
            # Create instance with configured parameters
            new_instance = cls(name=dialog.result_name,
                               initial_instruments=current_instruments.copy(), # Set instruments at creation
                               allow_shorting=dialog.result_allow_shorting,
                               optimization_target=cls.OPTIMIZATION_TARGETS[dialog.result_optimization_target_key])
            # on_instruments_changed is implicitly handled by passing initial_instruments if structure is consistent
            # Or can be called explicitly if there's a need for further reconciliation logic
            # new_instance.on_instruments_changed(current_instruments.copy()) 
            print(f"INFO ({new_instance.name}): Configured/created.")
            return new_instance
        return None

    def save_state(self) -> Dict[str, Any]:
        """Serializes the allocator's configuration."""
        return {
            "allow_shorting": self._allow_shorting,
            "optimization_target": self.optimization_target,
            "target_return_value": self.target_return_value,
            # Optionally, could save self._allocations if they are meant to be persistent
            # across sessions without recomputing, but typically these are recomputed.
            # "last_computed_allocations": self._allocations.copy() 
        }

    def load_state(self, config_params: Dict[str, Any], current_instruments: Set[str]) -> None:
        """Restores the allocator's state from configuration parameters."""
        self._allow_shorting = config_params.get("allow_shorting", False)
        loaded_opt_target = config_params.get("optimization_target", self.DEFAULT_OPTIMIZATION_TARGET)
        
        if loaded_opt_target not in self.OPTIMIZATION_TARGETS.values():
            print(f"Warning ({self.name}): Invalid optimization_target '{loaded_opt_target}' in saved state. Defaulting to {self.DEFAULT_OPTIMIZATION_TARGET}.")
            self.optimization_target = self.DEFAULT_OPTIMIZATION_TARGET
        else:
            self.optimization_target = loaded_opt_target
            
        self.target_return_value = config_params.get("target_return_value", None)
        # self._allocations = config_params.get("last_computed_allocations", {}) # If saving allocations

        # Crucially, update internal instrument set and clear/prepare for recomputation
        self.on_instruments_changed(current_instruments)
        print(f"INFO ({self.name}): State loaded. Allow Shorting: {self._allow_shorting}, Opt Target: {self.optimization_target}")


# --- MarkovitsConfigDialog class definition remains the same ---
# (It was provided in the previous response and is correctly placed here)
class MarkovitsConfigDialog(simpledialog.Dialog):
    def __init__(self, parent, title: str, initial_name: str,
                 initial_allow_shorting: bool,
                 initial_optimization_target_key: str, # This is the display key
                 available_targets: Dict[str,str]): # Display Name -> Internal Value
        self.initial_name = initial_name
        self.initial_allow_shorting = initial_allow_shorting
        self.initial_optimization_target_key = initial_optimization_target_key # Display key
        self.available_targets_map = available_targets 
        self.available_target_keys = list(available_targets.keys()) # List of display keys

        self.name_var = tk.StringVar(value=self.initial_name)
        self.allow_shorting_var = tk.BooleanVar(value=self.initial_allow_shorting)
        self.optimization_target_var = tk.StringVar(value=self.initial_optimization_target_key) # Holds display key

        self.result_name: Optional[str] = None
        self.result_allow_shorting: bool = False
        self.result_optimization_target_key: Optional[str] = None # Stores the selected display key
        super().__init__(parent, title)

    def body(self, master_frame: tk.Frame) -> tk.Entry | None:
        master_frame.pack_configure(padx=10, pady=10, fill="both", expand=True)

        name_frame = ttk.Frame(master_frame)
        name_frame.pack(side="top", fill="x", pady=5)
        ttk.Label(name_frame, text="Allocator Name:").pack(side="left", padx=(0,5))
        name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=30)
        name_entry.pack(side="left", fill="x", expand=True)

        shorting_check = ttk.Checkbutton(master_frame, text="Allow Short Selling (-1 to 1 weights)",
                                         variable=self.allow_shorting_var)
        shorting_check.pack(side="top", fill="x", pady=5)

        target_frame = ttk.Frame(master_frame)
        target_frame.pack(side="top", fill="x", pady=5)
        ttk.Label(target_frame, text="Optimization Target:").pack(side="left", padx=(0,5))
        self.target_combo = ttk.Combobox(target_frame, textvariable=self.optimization_target_var,
                                         values=self.available_target_keys, state="readonly", width=25)
        if self.initial_optimization_target_key in self.available_target_keys:
            self.target_combo.set(self.initial_optimization_target_key)
        elif self.available_target_keys:
             self.target_combo.current(0) 
        self.target_combo.pack(side="left", fill="x", expand=True)
        
        return name_entry 

    def validate(self) -> bool:
        allocator_name = self.name_var.get().strip()
        if not allocator_name:
            messagebox.showerror("Validation Error", "Allocator Name cannot be empty.", parent=self)
            return False
        
        selected_target_key = self.optimization_target_var.get() # This is the display key
        if not selected_target_key or selected_target_key not in self.available_target_keys :
            messagebox.showerror("Validation Error", "Please select a valid optimization target.", parent=self)
            return False

        self.result_name = allocator_name
        self.result_allow_shorting = self.allow_shorting_var.get()
        self.result_optimization_target_key = selected_target_key # Store the selected display key
        return True

    def apply(self) -> None:
        pass