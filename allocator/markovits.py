# portfolio_optimizer/allocator/markovits.py

from typing import Set, Dict, Optional, Type, Any, List # Added List
from datetime import date
import pandas as pd
from pypfopt import EfficientFrontier
from pypfopt import risk_models
from pypfopt import expected_returns
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import uuid

from .allocator import PortfolioAllocator, AllocatorState, PAL 
from config import get_fetcher
Fetcher = get_fetcher()

class MarkovitsAllocator(PortfolioAllocator):
    OPTIMIZATION_TARGETS = {
        "Maximize Sharpe Ratio": "max_sharpe",
        "Minimize Volatility": "min_volatility",
        # Future: "Efficient Return": "efficient_return",
        # Future: "Efficient Risk": "efficient_risk",
    }
    DEFAULT_OPTIMIZATION_TARGET_KEY = "Maximize Sharpe Ratio" # User-facing key
    DEFAULT_OPTIMIZATION_TARGET_INTERNAL = OPTIMIZATION_TARGETS[DEFAULT_OPTIMIZATION_TARGET_KEY]

    def __init__(self, **state: AllocatorState):
        super().__init__(**state)
        
        # Internal attributes are derived from the state passed to super().__init__
        # which stores it in self._state.
        self._allow_shorting: bool = bool(self._state.get('allow_shorting', False))
        
        raw_opt_target = str(self._state.get('optimization_target', self.DEFAULT_OPTIMIZATION_TARGET_INTERNAL))
        if raw_opt_target not in self.OPTIMIZATION_TARGETS.values():
            print(f"Warning ({self.get_name()}): Invalid optimization_target '{raw_opt_target}' in state. Defaulting to {self.DEFAULT_OPTIMIZATION_TARGET_INTERNAL}.")
            self.optimization_target: str = self.DEFAULT_OPTIMIZATION_TARGET_INTERNAL
        else:
            self.optimization_target: str = raw_opt_target

        self.target_return_value: Optional[float] = self._state.get('target_return_value')
        if self.target_return_value is not None:
            try:
                self.target_return_value = float(self.target_return_value)
            except (ValueError, TypeError):
                print(f"Warning ({self.get_name()}): Invalid target_return_value '{self.target_return_value}'. Setting to None.")
                self.target_return_value = None
        
        self._use_adj_close: bool = bool(self._state.get('use_adj_close', True)) # Default to True

        # Allocations are computed, not stored directly in state init beyond what super() does.
        self._allocations: Dict[str, float] = {} 

        # Update the state dictionary with coerced/defaulted values if they were missing or invalid
        self._state['allow_shorting'] = self._allow_shorting
        self._state['optimization_target'] = self.optimization_target
        self._state['target_return_value'] = self.target_return_value
        self._state['use_adj_close'] = self._use_adj_close
        # Instruments are handled by get_instruments() which reads from self._state['instruments']

    def get_state(self) -> AllocatorState:
        """Returns the current state of the allocator."""
        # Ensure all configurable parameters are correctly in self._state before returning
        current_state = self._state.copy()
        current_state['allow_shorting'] = self._allow_shorting
        current_state['optimization_target'] = self.optimization_target
        current_state['target_return_value'] = self.target_return_value
        current_state['use_adj_close'] = self._use_adj_close
        # 'name' and 'instruments' are assumed to be managed by base or Dialog->state pipeline
        return current_state

    def compute_allocations(self, fitting_start_date: date, fitting_end_date: date) -> Dict[str, float]:
        current_instruments = self.get_instruments()
        self._allocations = {instrument: 0.0 for instrument in current_instruments}

        if not current_instruments:
            print(f"WARNING ({self.get_name()}): No instruments defined. Cannot compute allocations.")
            return self._allocations.copy()

        print(f"INFO ({self.get_name()}): Computing allocations for {current_instruments} from {fitting_start_date} to {fitting_end_date}. AdjClose: {self._use_adj_close}")
        
        requested_instruments_upper = {t.upper() for t in current_instruments}
        upper_to_original_ticker_map = {t.upper(): t for t in current_instruments}

        try:
            # For Markovits, dividends are often important, so include_dividends=True is common.
            # The self._use_adj_close flag will determine which column ('AdjClose' or 'Close') is chosen later.
            raw_data_df, flawed_tickers_from_fetcher_upper = Fetcher.fetch(
                list(requested_instruments_upper),
                fitting_start_date,
                fitting_end_date,
                interval="1d",
                include_dividends=True # Fetch comprehensive data; selection of Close/AdjClose happens next
            )
        except Exception as e:
            print(f"ERROR ({self.get_name()}): Data fetching call failed: {e}")
            return self._allocations.copy()

        if raw_data_df.empty:
            print(f"WARNING ({self.get_name()}): No data returned from fetcher for {current_instruments}. Flawed tickers reported: {flawed_tickers_from_fetcher_upper}")
            return self._allocations.copy()

        valid_instruments_upper = requested_instruments_upper - set(flawed_tickers_from_fetcher_upper)
        
        if not valid_instruments_upper:
            print(f"WARNING ({self.get_name()}): No valid instruments after fetcher processing. Flawed: {flawed_tickers_from_fetcher_upper}")
            return self._allocations.copy()

        prices_df_list = []
        # Determine field based on the allocator's use_adj_close setting
        data_field_to_use = 'AdjClose' if self._use_adj_close else 'Close'
        fallback_field = 'Close' if self._use_adj_close else 'AdjClose' # Less critical fallback logic path

        for ticker_upper in valid_instruments_upper:
            original_ticker = upper_to_original_ticker_map[ticker_upper]
            price_series: Optional[pd.Series] = None
            
            if (data_field_to_use, ticker_upper) in raw_data_df.columns:
                price_series = raw_data_df[(data_field_to_use, ticker_upper)]
            elif (fallback_field, ticker_upper) in raw_data_df.columns: # Try fallback
                price_series = raw_data_df[(fallback_field, ticker_upper)]
                print(f"INFO ({self.get_name()}): Using fallback field '{fallback_field}' for {original_ticker} ({ticker_upper}) as primary '{data_field_to_use}' not found.")
            else:
                print(f"WARNING ({self.get_name()}): Price data for {original_ticker} ({ticker_upper}) (field: {data_field_to_use}) not in fetched columns. Skipping.")
                continue

            if price_series is not None and not price_series.dropna().empty:
                prices_df_list.append(price_series.dropna().rename(original_ticker))
            else:
                print(f"WARNING ({self.get_name()}): All price data for {original_ticker} ({ticker_upper}) was NaN or series was None. Skipping.")
        
        if not prices_df_list:
            print(f"WARNING ({self.get_name()}): No valid price series found for any instrument after extraction. Cannot compute.")
            return self._allocations.copy()
            
        prices = pd.concat(prices_df_list, axis=1).sort_index()
        
        if prices.shape[0] > 1 and prices.shape[1] > 0:
            common_start = prices.apply(lambda col: col.first_valid_index()).max()
            common_end = prices.apply(lambda col: col.last_valid_index()).min()
            if pd.notna(common_start) and pd.notna(common_end) and common_start < common_end:
                prices = prices.loc[common_start:common_end]
            else:
                print(f"WARNING ({self.get_name()}): Could not determine common date range. Start: {common_start}, End: {common_end}. Using available data.")
        
        prices = prices.ffill().bfill()
        prices.dropna(axis=1, how='all', inplace=True) 

        if prices.empty or prices.shape[0] < 2 or prices.shape[1] == 0 :
            print(f"WARNING ({self.get_name()}): Not enough historical data points or instruments ({prices.shape}) after processing. Cannot compute.")
            return self._allocations.copy()

        try:
            mu = expected_returns.mean_historical_return(prices, compounding=True, frequency=252)
            S = risk_models.CovarianceShrinkage(prices, frequency=252).ledoit_wolf()
        except Exception as e:
            print(f"ERROR ({self.get_name()}): Could not calculate mu/S: {e}. Prices Columns: {prices.columns}")
            return self._allocations.copy()

        weight_bounds = (-1.0 if self._allow_shorting else 0.0, 1.0)
        ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)

        try:
            if self.optimization_target == "max_sharpe":
                ef.max_sharpe()
            elif self.optimization_target == "min_volatility":
                ef.min_volatility()
            # Add other targets when implemented (e.g. efficient_risk, efficient_return)
            # elif self.optimization_target == "efficient_return" and self.target_return_value is not None:
            #     ef.efficient_return(self.target_return_value)
            else: 
                print(f"WARNING ({self.get_name()}): Unknown or misconfigured optimization target '{self.optimization_target}'. Defaulting to max_sharpe.")
                ef.max_sharpe()
            
            cleaned_weights = ef.clean_weights()
            for ticker, weight in cleaned_weights.items():
                if ticker in self._allocations: 
                    self._allocations[ticker] = weight
                else:
                    print(f"WARNING ({self.get_name()}): Ticker {ticker} from optimization results not in original instrument list. This is unexpected.")

            print(f"INFO ({self.get_name()}): Computed allocations: {self._allocations}")
            return self._allocations.copy()

        except ValueError as ve:
             print(f"ERROR ({self.get_name()}): Optimization failed for '{self.optimization_target}': {ve}")
             return self._allocations.copy()
        except Exception as e:
            print(f"ERROR ({self.get_name()}): Unexpected error during optimization for '{self.optimization_target}': {e}")
            return self._allocations.copy()

    @classmethod
    def configure(cls: Type['MarkovitsAllocator'],
                  parent_window: tk.Misc,
                  existing_state: Optional[AllocatorState] = None
                 ) -> Optional[AllocatorState]:

        # ---- Set initial values for the dialog ----
        initial_name = f"Markovits Allocator {str(uuid.uuid4())[:4]}"
        initial_instruments_str = ""
        initial_allow_shorting = False
        initial_opt_target_key = cls.DEFAULT_OPTIMIZATION_TARGET_KEY # User-facing key
        initial_use_adj_close = True # Default for new
        # target_return_value is not directly handled by a simple dialog field in this iteration.

        if existing_state:
            initial_name = str(existing_state.get('name', initial_name))
            
            instruments_data = existing_state.get('instruments')
            if isinstance(instruments_data, (set, list, tuple)):
                initial_instruments_str = ", ".join(sorted(list(set(map(str, instruments_data)))))
            
            initial_allow_shorting = bool(existing_state.get('allow_shorting', False))
            initial_use_adj_close = bool(existing_state.get('use_adj_close', True))
            
            internal_opt_target = str(existing_state.get('optimization_target', cls.DEFAULT_OPTIMIZATION_TARGET_INTERNAL))
            for k, v_internal in cls.OPTIMIZATION_TARGETS.items():
                if v_internal == internal_opt_target:
                    initial_opt_target_key = k
                    break
        
        dialog = MarkovitsConfigDialog(
            parent_window,
            title=f"Configure: {initial_name}" if existing_state else "Create Markovits Allocator",
            initial_name=initial_name,
            initial_instruments_str=initial_instruments_str,
            initial_allow_shorting=initial_allow_shorting,
            initial_use_adj_close=initial_use_adj_close,
            initial_optimization_target_key=initial_opt_target_key,
            available_targets_map=cls.OPTIMIZATION_TARGETS
        )
        
        if dialog.result_is_ok: # Check a flag that indicates successful completion
            new_state: AllocatorState = {
                "name": str(dialog.result_name),
                "instruments": set(dialog.result_instruments_set), # Comes from dialog as set
                "allow_shorting": bool(dialog.result_allow_shorting),
                "optimization_target": str(cls.OPTIMIZATION_TARGETS[dialog.result_optimization_target_key]), # Store internal value
                "use_adj_close": bool(dialog.result_use_adj_close),
                "target_return_value": None # Or retrieve if dialog supports it
            }
            
            try: # Validate state by attempting to instantiate
                _ = cls(**new_state) 
            except ValueError as e:
                messagebox.showerror("Configuration Error", f"Failed to create allocator state: {e}", parent=parent_window)
                return None

            print(f"INFO: MarkovitsAllocator '{new_state['name']}' configuration resulted in state: {new_state}")
            return new_state
        
        print(f"INFO: MarkovitsAllocator configuration/creation cancelled for '{initial_name}'.")
        return None


class MarkovitsConfigDialog(simpledialog.Dialog):
    def __init__(self, parent: tk.Misc, title: str, 
                 initial_name: str,
                 initial_instruments_str: str, # Comma-separated string
                 initial_allow_shorting: bool,
                 initial_use_adj_close: bool,
                 initial_optimization_target_key: str, # Display key
                 available_targets_map: Dict[str,str]): # Display Name -> Internal Value
        
        self.initial_name = initial_name
        self.initial_instruments_str = initial_instruments_str
        self.initial_allow_shorting = initial_allow_shorting
        self.initial_use_adj_close = initial_use_adj_close
        self.initial_optimization_target_key = initial_optimization_target_key
        self.available_targets_map = available_targets_map
        self.available_target_keys = list(available_targets_map.keys())

        # --- Tkinter Variables --- 
        self.name_var = tk.StringVar(value=self.initial_name)
        self.instruments_text_var = tk.StringVar(value=self.initial_instruments_str)
        self.allow_shorting_var = tk.BooleanVar(value=self.initial_allow_shorting)
        self.use_adj_close_var = tk.BooleanVar(value=self.initial_use_adj_close)
        self.optimization_target_var = tk.StringVar(value=self.initial_optimization_target_key)

        # --- Results --- (populated upon successful validation)
        self.result_is_ok: bool = False # Flag to indicate successful dialog completion
        self.result_name: Optional[str] = None
        self.result_instruments_set: Optional[Set[str]] = None
        self.result_allow_shorting: bool = False
        self.result_use_adj_close: bool = True
        self.result_optimization_target_key: Optional[str] = None # Stores the selected display key
        
        super().__init__(parent, title)

    def body(self, master_frame: tk.Frame) -> tk.Entry | None:
        master_frame.pack_configure(padx=10, pady=10, fill="both", expand=True)

        # --- Name ---
        name_frame = ttk.Frame(master_frame)
        name_frame.pack(side="top", fill="x", pady=5)
        ttk.Label(name_frame, text="Allocator Name:").pack(side="left", padx=(0,5))
        self.name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=40)
        self.name_entry.pack(side="left", fill="x", expand=True)

        # --- Instruments ---
        inst_frame = ttk.LabelFrame(master_frame, text="Instruments (comma-separated)")
        inst_frame.pack(side="top", fill="x", pady=5)
        self.instruments_entry = ttk.Entry(inst_frame, textvariable=self.instruments_text_var, width=50)
        self.instruments_entry.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        # Optionally, add a small info label about format or examples.

        # --- Options Checkboxes ---
        options_frame = ttk.Frame(master_frame)
        options_frame.pack(side="top", fill="x", pady=3)
        
        self.shorting_check = ttk.Checkbutton(options_frame, text="Allow Short Selling (-1 to 1 weights)",
                                         variable=self.allow_shorting_var)
        self.shorting_check.pack(side="top", fill="x", pady=2, anchor="w")

        self.adj_close_check = ttk.Checkbutton(options_frame, text="Use Adjusted Close Prices (recommended)",
                                          variable=self.use_adj_close_var)
        self.adj_close_check.pack(side="top", fill="x", pady=2, anchor="w")

        # --- Optimization Target ---
        target_frame = ttk.Frame(master_frame)
        target_frame.pack(side="top", fill="x", pady=5)
        ttk.Label(target_frame, text="Optimization Target:").pack(side="left", padx=(0,5))
        self.target_combo = ttk.Combobox(target_frame, textvariable=self.optimization_target_var,
                                         values=self.available_target_keys, state="readonly", width=30)
        # Pre-select from initial_optimization_target_key
        if self.initial_optimization_target_key in self.available_target_keys:
            self.target_combo.set(self.initial_optimization_target_key)
        elif self.available_target_keys: # Fallback to first if initial is invalid
             self.target_combo.current(0) 
        self.target_combo.pack(side="left", fill="x", expand=True)
        
        return self.name_entry # For initial focus by Dialog system

    def validate(self) -> bool:
        allocator_name = self.name_var.get().strip()
        if not allocator_name:
            messagebox.showerror("Validation Error", "Allocator Name cannot be empty.", parent=self)
            self.name_entry.focus_set()
            return False
        
        instruments_str = self.instruments_text_var.get().strip()
        if not instruments_str:
            if not messagebox.askyesno("No Instruments", "No instruments specified. Continue with an empty set?", parent=self):
                self.instruments_entry.focus_set()
                return False
            parsed_instruments_set: Set[str] = set()
        else:
            parsed_instruments_set = {s.strip().upper() for s in instruments_str.split(',') if s.strip()}
            if not parsed_instruments_set: # e.g. if input was just commas or whitespace
                messagebox.showerror("Validation Error", "Instruments field is non-empty but parsing resulted in no valid tickers. Please provide valid, comma-separated tickers.", parent=self)
                self.instruments_entry.focus_set()
                return False
            # Further validation on ticker format could go here (e.g. regex for valid chars)
        
        selected_target_key = self.optimization_target_var.get()
        if not selected_target_key or selected_target_key not in self.available_target_keys:
            messagebox.showerror("Validation Error", "Please select a valid optimization target.", parent=self)
            self.target_combo.focus_set()
            return False

        # If all validations pass, set results
        self.result_name = allocator_name
        self.result_instruments_set = parsed_instruments_set
        self.result_allow_shorting = self.allow_shorting_var.get()
        self.result_use_adj_close = self.use_adj_close_var.get()
        self.result_optimization_target_key = selected_target_key
        self.result_is_ok = True # Mark successful validation
        return True

    def apply(self) -> None:
        # Results are set in validate() if self.result_is_ok becomes True.
        # The simpledialog.Dialog base class handles the rest.
        pass

    # Override buttonbox or rely on default OK/Cancel from simpledialog.Dialog
    # If overriding, make sure to call self.ok() or self.cancel() which in turn call validate() and apply()
