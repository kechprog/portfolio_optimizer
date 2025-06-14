# portfolio_optimizer/allocator/mpt/max_sharpe.py
import logging
from typing import Set, Dict, Optional, Type, Any, List
from datetime import date
import pandas as pd
from pypfopt import EfficientFrontier, risk_models, expected_returns
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import uuid

from allocator.allocator import PortfolioAllocator, AllocatorState, PAL # Adjusted import
from allocator.util import InstrumentListManagerWidget # Adjusted import
from portfolio import Portfolio # Adjusted import
from data_getter import av_fetcher # Adjusted import

logger = logging.getLogger(__name__)

class MaxSharpeAllocator(PortfolioAllocator):
    OPTIMIZATION_TARGET_INTERNAL = "max_sharpe" # Fixed for this allocator

    def __init__(self, **state: AllocatorState):
        super().__init__(**state)
        
        self._allow_shorting: bool = bool(self._state.get('allow_shorting', False))
        self._use_adj_close: bool = bool(self._state.get('use_adj_close', True))

        # Ensure these are in the state for get_state()
        self._state['allow_shorting'] = self._allow_shorting
        self._state['use_adj_close'] = self._use_adj_close
        # Dynamic update configuration (not yet supported)
        self._update_enabled: bool = bool(self._state.get('update_enabled', False))
        self._update_interval_value: int = int(self._state.get('update_interval_value', 1))
        self._update_interval_unit: str = str(self._state.get('update_interval_unit', 'days'))
        self._state['update_enabled'] = self._update_enabled
        self._state['update_interval_value'] = self._update_interval_value
        self._state['update_interval_unit'] = self._update_interval_unit
        # 'optimization_target' is implicitly max_sharpe
        # No separate _allocations dict needed here as it's computed on demand and returned in Portfolio

    def get_state(self) -> AllocatorState:
        current_state = self._state.copy()
        current_state['allow_shorting'] = self._allow_shorting
        current_state['use_adj_close'] = self._use_adj_close
        # Dynamic update settings
        current_state['update_enabled'] = getattr(self, '_update_enabled', False)
        current_state['update_interval_value'] = getattr(self, '_update_interval_value', 1)
        current_state['update_interval_unit'] = getattr(self, '_update_interval_unit', 'days')
        return current_state

    def compute_allocations(self, fitting_start_date: date, fitting_end_date: date, test_end_date: date) -> Portfolio:
        portfolio = Portfolio(start_date=fitting_start_date)
        current_instruments = self.get_instruments()

        if not current_instruments:
            logger.warning(f"({self.get_name()} - MaxSharpe): No instruments. Returning empty portfolio.")
            return portfolio

        logger.info(f"({self.get_name()} - MaxSharpe): Computing for {current_instruments} from {fitting_start_date} to {fitting_end_date}. AdjClose: {self._use_adj_close}")
        
        requested_instruments_upper = {t.upper() for t in current_instruments}
        upper_to_original_ticker_map = {t.upper(): t for t in current_instruments}

        try:
            raw_data_df, flawed_tickers_from_fetcher_upper = av_fetcher(
                requested_instruments_upper,
                pd.to_datetime(fitting_start_date),
                pd.to_datetime(fitting_end_date)
            )
        except Exception as e:
            logger.error(f"({self.get_name()} - MaxSharpe): Data fetch failed: {e}", exc_info=True)
            return portfolio

        if raw_data_df.empty:
            logger.warning(f"({self.get_name()} - MaxSharpe): No data from fetcher. Flawed: {flawed_tickers_from_fetcher_upper}")
            return portfolio

        valid_instruments_upper = requested_instruments_upper - set(flawed_tickers_from_fetcher_upper)
        if not valid_instruments_upper:
            logger.warning(f"({self.get_name()} - MaxSharpe): No valid instruments after fetch. Flawed: {flawed_tickers_from_fetcher_upper}")
            return portfolio

        prices_df_list = []
        data_field_to_use = 'AdjClose' if self._use_adj_close else 'Close'
        fallback_field = 'Close' if self._use_adj_close else 'AdjClose'

        for ticker_upper in valid_instruments_upper:
            original_ticker = upper_to_original_ticker_map[ticker_upper]
            price_series: Optional[pd.Series] = None
            if (data_field_to_use, ticker_upper) in raw_data_df.columns:
                price_series = raw_data_df[(data_field_to_use, ticker_upper)]
            elif (fallback_field, ticker_upper) in raw_data_df.columns:
                price_series = raw_data_df[(fallback_field, ticker_upper)]
                logger.info(f"({self.get_name()} - MaxSharpe): Using fallback '{fallback_field}' for {original_ticker} ({ticker_upper}).")
            else:
                logger.warning(f"({self.get_name()} - MaxSharpe): No price data for {original_ticker} ({ticker_upper}). Skipping.")
                continue
            if price_series is not None and not price_series.dropna().empty:
                prices_df_list.append(price_series.dropna().rename(original_ticker))
            else:
                logger.warning(f"({self.get_name()} - MaxSharpe): All data for {original_ticker} ({ticker_upper}) was NaN. Skipping.")
        
        if not prices_df_list:
            logger.warning(f"({self.get_name()} - MaxSharpe): No valid price series after extraction.")
            return portfolio
            
        prices = pd.concat(prices_df_list, axis=1).sort_index()
        if prices.shape[0] > 1 and prices.shape[1] > 0: #Align dates
            common_start = prices.apply(lambda col: col.first_valid_index()).max()
            common_end = prices.apply(lambda col: col.last_valid_index()).min()
            if pd.notna(common_start) and pd.notna(common_end) and common_start < common_end:
                prices = prices.loc[common_start:common_end]
        prices = prices.ffill().bfill().dropna(axis=1, how='all')

        if prices.empty or prices.shape[0] < 2 or prices.shape[1] == 0:
            logger.warning(f"({self.get_name()} - MaxSharpe): Not enough data points ({prices.shape[0]}) or instruments ({prices.shape[1]}) after processing.")
            return portfolio

        try:
            mu = expected_returns.mean_historical_return(prices, compounding=True, frequency=252)
            S = risk_models.CovarianceShrinkage(prices, frequency=252).ledoit_wolf()
        except Exception as e:
            logger.error(f"({self.get_name()} - MaxSharpe): Could not calc mu/S: {e}. Prices Cols: {prices.columns}", exc_info=True)
            return portfolio

        weight_bounds = (-1.0 if self._allow_shorting else 0.0, 1.0)
        ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)

        try:
            ef.max_sharpe() # Key difference
            computed_allocations = ef.clean_weights()
            
            # Ensure only requested instruments are in final allocations, with 0 for those not in results
            final_allocs_for_segment = {inst: 0.0 for inst in current_instruments}
            for ticker, weight in computed_allocations.items():
                if ticker in final_allocs_for_segment: # ticker should be original case from prices.columns
                     final_allocs_for_segment[ticker] = weight
                else: # Should not happen if prices.columns align with current_instruments
                    logger.warning(f"({self.get_name()} - MaxSharpe): Optimized ticker {ticker} not in current_instruments. Check mapping.")

            logger.info(f"({self.get_name()} - MaxSharpe): Computed allocations for segment: {final_allocs_for_segment}")
            if fitting_end_date > fitting_start_date:
                portfolio.append(end_date=fitting_end_date, allocations=final_allocs_for_segment)
            else:
                 logger.warning(f"({self.get_name()} - MaxSharpe): fitting_end_date not after fitting_start_date. Segment not added.")
            return portfolio
        except Exception as e: # Covers ValueError from PyPortfolioOpt or other issues
            logger.error(f"({self.get_name()} - MaxSharpe): Optimization failed: {e}", exc_info=True)
            return portfolio

    @classmethod
    def configure(cls: Type['MaxSharpeAllocator'],
                  parent_window: tk.Misc,
                  existing_state: Optional[AllocatorState] = None
                 ) -> Optional[AllocatorState]:
        # Initialize dynamic update settings
        initial_update_enabled = False
        initial_update_interval_value = 1
        initial_update_interval_unit = 'days'
        if existing_state:
            initial_update_enabled = bool(existing_state.get('update_enabled', False))
            try:
                initial_update_interval_value = int(existing_state.get('update_interval_value', 1))
            except (ValueError, TypeError):
                initial_update_interval_value = 1
            initial_update_interval_unit = str(existing_state.get('update_interval_unit', 'days'))

        initial_name = f"Max Sharpe MPT {str(uuid.uuid4())[:4]}"
        initial_instruments_list: List[str] = []
        initial_allow_shorting = False
        initial_use_adj_close = True

        if existing_state:
            initial_name = str(existing_state.get('name', initial_name))
            instruments_data = existing_state.get('instruments')
            if isinstance(instruments_data, (set, list, tuple)):
                initial_instruments_list = sorted(list(set(map(str, instruments_data))))
            initial_allow_shorting = bool(existing_state.get('allow_shorting', False))
            initial_use_adj_close = bool(existing_state.get('use_adj_close', True))
        initial_name = f"Max Sharpe MPT {str(uuid.uuid4())[:4]}"
        initial_instruments_list: List[str] = []
        initial_allow_shorting = False
        initial_use_adj_close = True
        initial_update_enabled = False
        initial_update_interval_value = 1
        initial_update_interval_unit = 'days'

        if existing_state:
            initial_name = str(existing_state.get('name', initial_name))
            instruments_data = existing_state.get('instruments')
            if isinstance(instruments_data, (set, list, tuple)):
                initial_instruments_list = sorted(list(set(map(str, instruments_data))))
            initial_allow_shorting = bool(existing_state.get('allow_shorting', False))
            initial_use_adj_close = bool(existing_state.get('use_adj_close', True))
            initial_update_enabled = bool(existing_state.get('update_enabled', False))
            try:
                initial_update_interval_value = int(existing_state.get('update_interval_value', 1))
            except (ValueError, TypeError):
                initial_update_interval_value = 1
            initial_update_interval_unit = str(existing_state.get('update_interval_unit', 'days'))
        
        dialog = MaxSharpeConfigDialog(
            parent_window,
            title=f"Configure: {initial_name}" if existing_state else "Create Max Sharpe Allocator",
            initial_name=initial_name,
            initial_instruments_list=initial_instruments_list,
            initial_allow_shorting=initial_allow_shorting,
            initial_use_adj_close=initial_use_adj_close,
            initial_update_enabled=initial_update_enabled,
            initial_update_interval_value=initial_update_interval_value,
            initial_update_interval_unit=initial_update_interval_unit
        )
        
        if dialog.result_is_ok:
            assert not dialog.update_enabled_var.get(), "Dynamic update is not yet supported."
            new_state: AllocatorState = {
                "name": str(dialog.result_name),
                "instruments": set(dialog.result_instruments_set),
                "allow_shorting": bool(dialog.result_allow_shorting),
                "use_adj_close": bool(dialog.result_use_adj_close),
                "update_enabled": False,
                "update_interval_value": int(dialog.update_interval_value_var.get()),
                "update_interval_unit": dialog.update_interval_unit_var.get(),
            }
            try:
                _ = cls(**new_state) 
            except ValueError as e:
                messagebox.showerror("Config Error", f"Failed to create allocator state: {e}", parent=parent_window)
                return None
            logger.info(f"MaxSharpeAllocator '{new_state['name']}' config result: {new_state}")
            return new_state
        logger.info(f"MaxSharpeAllocator config cancelled for '{initial_name}'.")
        return None

class MaxSharpeConfigDialog(simpledialog.Dialog):
    def __init__(self, parent: tk.Misc, title: str, 
                 initial_name: str,
                 initial_instruments_list: List[str],
                 initial_allow_shorting: bool,
                 initial_use_adj_close: bool,
                 initial_update_enabled: bool,
                 initial_update_interval_value: int,
                 initial_update_interval_unit: str):
        
        self.initial_name = initial_name
        self.initial_instruments_list = initial_instruments_list
        self.initial_allow_shorting = initial_allow_shorting
        self.initial_use_adj_close = initial_use_adj_close
        self.initial_update_enabled = initial_update_enabled
        self.initial_update_interval_value = initial_update_interval_value
        self.initial_update_interval_unit = initial_update_interval_unit

        self.name_var = tk.StringVar(value=self.initial_name)
        self.allow_shorting_var = tk.BooleanVar(value=self.initial_allow_shorting)
        self.use_adj_close_var = tk.BooleanVar(value=self.initial_use_adj_close)
        self.update_enabled_var = tk.BooleanVar(value=self.initial_update_enabled)
        self.update_interval_value_var = tk.StringVar(value=str(self.initial_update_interval_value))
        self.update_interval_unit_var = tk.StringVar(value=self.initial_update_interval_unit)
        
        self.instrument_manager_widget: Optional[InstrumentListManagerWidget] = None
        self.result_is_ok: bool = False
        self.result_name: Optional[str] = None
        self.result_instruments_set: Optional[Set[str]] = None
        self.result_allow_shorting: bool = False
        self.result_use_adj_close: bool = True
        super().__init__(parent, title)

    def body(self, master_frame: tk.Frame) -> tk.Entry | None:
        master_frame.pack_configure(padx=10, pady=10, fill="both", expand=True)

        top_options_frame = ttk.Frame(master_frame)
        top_options_frame.pack(side="top", fill="x", pady=(0, 10))

        name_frame = ttk.Frame(top_options_frame)
        name_frame.pack(side="top", fill="x", pady=2)
        ttk.Label(name_frame, text="Allocator Name:").pack(side="left", padx=(0,5))
        self.name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=40)
        self.name_entry.pack(side="left", fill="x", expand=True)

        options_checks_frame = ttk.Frame(top_options_frame)
        options_checks_frame.pack(side="top", fill="x", pady=2)
        self.shorting_check = ttk.Checkbutton(options_checks_frame, text="Allow Short Selling", variable=self.allow_shorting_var)
        self.shorting_check.pack(side="top", anchor="w", fill="x")
        self.adj_close_check = ttk.Checkbutton(options_checks_frame, text="Use Adjusted Close Prices", variable=self.use_adj_close_var)
        self.adj_close_check.pack(side="top", anchor="w", fill="x")

        instruments_group_frame = ttk.LabelFrame(master_frame, text="Instruments")
        instruments_group_frame.pack(side="top", fill="both", expand=True, pady=5)
        self.instrument_manager_widget = InstrumentListManagerWidget(
            instruments_group_frame, 
            initial_instruments_list=self.initial_instruments_list
        )
        self.instrument_manager_widget.pack(fill="both", expand=True, padx=5, pady=5)

        # Dynamic update configuration
        # Layout: <checkbox> <label 'Update each:'> <entry> <dropdown>
        update_frame = ttk.Frame(master_frame)
        update_frame.pack(side="top", fill="x", pady=(5, 0))
        self.update_check = ttk.Checkbutton(update_frame, text="Enable Dynamic Update", variable=self.update_enabled_var)
        self.update_check.pack(side="left", padx=(0,5))
        ttk.Label(update_frame, text="Update each:").pack(side="left", padx=(5,2))
        self.update_interval_entry = ttk.Entry(update_frame, textvariable=self.update_interval_value_var, width=5)
        self.update_interval_entry.pack(side="left")
        self.update_interval_unit_combo = ttk.Combobox(update_frame, textvariable=self.update_interval_unit_var, state="readonly", values=["days", "weeks", "months"], width=10)
        self.update_interval_unit_combo.pack(side="left", padx=(2,0))
        self.update_interval_unit_combo.current(["days", "weeks", "months"].index(self.initial_update_interval_unit))
        
        return self.name_entry

    def validate(self) -> bool:
        self.result_name = self.name_var.get().strip()
        if not self.result_name:
            messagebox.showerror("Validation Error", "Allocator Name cannot be empty.", parent=self)
            self.name_entry.focus_set()
            return False
        
        if not self.instrument_manager_widget:
            messagebox.showerror("Internal Error", "Instrument manager missing.", parent=self)
            return False
        self.result_instruments_set = self.instrument_manager_widget.get_instruments()

        if not self.result_instruments_set:
            if not messagebox.askyesno("No Instruments", "No instruments. Continue?", parent=self):
                if self.instrument_manager_widget.instrument_rows_data: # Check if rows exist
                    self.instrument_manager_widget.focus_on_last_instrument_entry()
                else: # if no rows (e.g. all deleted)
                    self.instrument_manager_widget.focus_on_add_button()
                return False
        
        self.result_allow_shorting = self.allow_shorting_var.get()
        self.result_use_adj_close = self.use_adj_close_var.get()
        self.result_is_ok = True
        return True

    def apply(self) -> None: # Results set in validate()
        pass