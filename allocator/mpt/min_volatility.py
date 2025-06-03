# portfolio_optimizer/allocator/mpt/min_volatility.py
import logging
from typing import Set, Dict, Optional, Type, Any, List
from datetime import date
import pandas as pd
from pypfopt import EfficientFrontier, risk_models, expected_returns
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import uuid

from ..allocator import PortfolioAllocator, AllocatorState, PAL
from ..util import InstrumentListManagerWidget
from ...portfolio import Portfolio # Relative import from portfolio_optimizer directory
from ...data_getter import av_fetcher # Relative import data_getter

logger = logging.getLogger(__name__)

class MinVolatilityAllocator(PortfolioAllocator):
    OPTIMIZATION_TARGET_INTERNAL = "min_volatility" # Fixed for this allocator

    def __init__(self, **state: AllocatorState):
        super().__init__(**state)
        
        self._allow_shorting: bool = bool(self._state.get('allow_shorting', False))
        self._use_adj_close: bool = bool(self._state.get('use_adj_close', True))

        self._state['allow_shorting'] = self._allow_shorting
        self._state['use_adj_close'] = self._use_adj_close

    def get_state(self) -> AllocatorState:
        current_state = self._state.copy()
        current_state['allow_shorting'] = self._allow_shorting
        current_state['use_adj_close'] = self._use_adj_close
        return current_state

    def compute_allocations(self, fitting_start_date: date, fitting_end_date: date) -> Portfolio:
        portfolio = Portfolio(start_date=fitting_start_date)
        current_instruments = self.get_instruments()

        if not current_instruments:
            logger.warning(f"({self.get_name()} - MinVol): No instruments. Returning empty portfolio.")
            return portfolio

        logger.info(f"({self.get_name()} - MinVol): Computing for {current_instruments} from {fitting_start_date} to {fitting_end_date}. AdjClose: {self._use_adj_close}")
        
        requested_instruments_upper = {t.upper() for t in current_instruments}
        upper_to_original_ticker_map = {t.upper(): t for t in current_instruments}

        try:
            raw_data_df, flawed_tickers_from_fetcher_upper = av_fetcher(
                requested_instruments_upper,
                pd.to_datetime(fitting_start_date),
                pd.to_datetime(fitting_end_date)
            )
        except Exception as e:
            logger.error(f"({self.get_name()} - MinVol): Data fetch failed: {e}", exc_info=True)
            return portfolio

        if raw_data_df.empty:
            logger.warning(f"({self.get_name()} - MinVol): No data from fetcher. Flawed: {flawed_tickers_from_fetcher_upper}")
            return portfolio

        valid_instruments_upper = requested_instruments_upper - set(flawed_tickers_from_fetcher_upper)
        if not valid_instruments_upper:
            logger.warning(f"({self.get_name()} - MinVol): No valid instruments after fetch. Flawed: {flawed_tickers_from_fetcher_upper}")
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
                logger.info(f"({self.get_name()} - MinVol): Using fallback '{fallback_field}' for {original_ticker} ({ticker_upper}).")
            else:
                logger.warning(f"({self.get_name()} - MinVol): No price data for {original_ticker} ({ticker_upper}). Skipping.")
                continue
            if price_series is not None and not price_series.dropna().empty:
                prices_df_list.append(price_series.dropna().rename(original_ticker))
            else:
                logger.warning(f"({self.get_name()} - MinVol): All data for {original_ticker} ({ticker_upper}) was NaN. Skipping.")
        
        if not prices_df_list:
            logger.warning(f"({self.get_name()} - MinVol): No valid price series after extraction.")
            return portfolio
            
        prices = pd.concat(prices_df_list, axis=1).sort_index()
        if prices.shape[0] > 1 and prices.shape[1] > 0: #Align dates
            common_start = prices.apply(lambda col: col.first_valid_index()).max()
            common_end = prices.apply(lambda col: col.last_valid_index()).min()
            if pd.notna(common_start) and pd.notna(common_end) and common_start < common_end:
                prices = prices.loc[common_start:common_end]
        prices = prices.ffill().bfill().dropna(axis=1, how='all')

        if prices.empty or prices.shape[0] < 2 or prices.shape[1] == 0:
            logger.warning(f"({self.get_name()} - MinVol): Not enough data points ({prices.shape[0]}) or instruments ({prices.shape[1]}) after processing.")
            return portfolio

        try:
            # For min_volatility, mu can be omitted from EfficientFrontier, 
            # or simply not used if ef.min_volatility() is called.
            # However, PyPortfolioOpt expects mu, so we calculate it.
            mu = expected_returns.mean_historical_return(prices, compounding=True, frequency=252)
            S = risk_models.CovarianceShrinkage(prices, frequency=252).ledoit_wolf()
        except Exception as e:
            logger.error(f"({self.get_name()} - MinVol): Could not calc mu/S: {e}. Prices Cols: {prices.columns}", exc_info=True)
            return portfolio

        weight_bounds = (-1.0 if self._allow_shorting else 0.0, 1.0)
        ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)

        try:
            ef.min_volatility() # Key difference
            computed_allocations = ef.clean_weights()

            final_allocs_for_segment = {inst: 0.0 for inst in current_instruments}
            for ticker, weight in computed_allocations.items():
                if ticker in final_allocs_for_segment:
                     final_allocs_for_segment[ticker] = weight
                else: 
                    logger.warning(f"({self.get_name()} - MinVol): Optimized ticker {ticker} not in current_instruments. Check mapping.")

            logger.info(f"({self.get_name()} - MinVol): Computed allocations for segment: {final_allocs_for_segment}")
            if fitting_end_date > fitting_start_date:
                portfolio.append(end_date=fitting_end_date, allocations=final_allocs_for_segment)
            else:
                logger.warning(f"({self.get_name()} - MinVol): fitting_end_date not after fitting_start_date. Segment not added.")
            return portfolio
        except Exception as e:
            logger.error(f"({self.get_name()} - MinVol): Optimization failed: {e}", exc_info=True)
            return portfolio

    @classmethod
    def configure(cls: Type['MinVolatilityAllocator'],
                  parent_window: tk.Misc,
                  existing_state: Optional[AllocatorState] = None
                 ) -> Optional[AllocatorState]:
        initial_name = f"Min Volatility MPT {str(uuid.uuid4())[:4]}"
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
        
        dialog = MinVolatilityConfigDialog(
            parent_window,
            title=f"Configure: {initial_name}" if existing_state else "Create Min Volatility Allocator",
            initial_name=initial_name,
            initial_instruments_list=initial_instruments_list,
            initial_allow_shorting=initial_allow_shorting,
            initial_use_adj_close=initial_use_adj_close
        )
        
        if dialog.result_is_ok:
            new_state: AllocatorState = {
                "name": str(dialog.result_name),
                "instruments": set(dialog.result_instruments_set),
                "allow_shorting": bool(dialog.result_allow_shorting),
                "use_adj_close": bool(dialog.result_use_adj_close),
            }
            try:
                _ = cls(**new_state) 
            except ValueError as e:
                messagebox.showerror("Config Error", f"Failed to create allocator state: {e}", parent=parent_window)
                return None
            logger.info(f"MinVolatilityAllocator '{new_state['name']}' config result: {new_state}")
            return new_state
        logger.info(f"MinVolatilityAllocator config cancelled for '{initial_name}'.")
        return None

class MinVolatilityConfigDialog(simpledialog.Dialog):
    def __init__(self, parent: tk.Misc, title: str, 
                 initial_name: str,
                 initial_instruments_list: List[str],
                 initial_allow_shorting: bool,
                 initial_use_adj_close: bool):
        
        self.initial_name = initial_name
        self.initial_instruments_list = initial_instruments_list
        self.initial_allow_shorting = initial_allow_shorting
        self.initial_use_adj_close = initial_use_adj_close

        self.name_var = tk.StringVar(value=self.initial_name)
        self.allow_shorting_var = tk.BooleanVar(value=self.initial_allow_shorting)
        self.use_adj_close_var = tk.BooleanVar(value=self.initial_use_adj_close)
        
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
                if self.instrument_manager_widget.instrument_rows_data:
                    self.instrument_manager_widget.focus_on_last_instrument_entry()
                else: 
                    self.instrument_manager_widget.focus_on_add_button()
                return False
        
        self.result_allow_shorting = self.allow_shorting_var.get()
        self.result_use_adj_close = self.use_adj_close_var.get()
        self.result_is_ok = True
        return True

    def apply(self) -> None: 
        pass
