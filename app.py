# c:\Users\Eduar\projects\portfolio_optimizer\app.py
import multiprocessing # Added for freeze_support
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, date, timedelta
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
import matplotlib.ticker as mtick # For PercentFormatter
import pandas as pd
# import numpy as np # Not explicitly used after refactoring, could be removed if not needed by other parts
import uuid
import json
import os
import logging # Added logging
from typing import Optional, Set, Dict, Type, Any, List, Tuple

# Import the new AllocatorState along with PortfolioAllocator
from allocator.allocator import PortfolioAllocator, AllocatorState
from allocator.manual import ManualAllocator
from allocator.markovits import MarkovitsAllocator

from data_getter import av_fetcher # Changed to import av_fetcher directly

# Setup logger for this module
logger = logging.getLogger(__name__)

GEAR_ICON = "\u2699"
DELETE_ICON = "\u2716"
SAVE_STATE_FILENAME = "portfolio_app_state.json"

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Portfolio Allocation Tool")
        self.root.geometry("1200x800")
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_closing)

        # self.current_instruments_set: Set[str] = set() # REMOVED - managed per allocator

        # Stores allocator instances and their UI elements (like is_enabled_var)
        # Key: allocator_id (str), Value: Dict {'instance': PortfolioAllocator, 'is_enabled_var': tk.BooleanVar}
        self.allocators_store: Dict[str, Dict[str, Any]] = {}
        
        self.available_allocator_types: Dict[str, Type[PortfolioAllocator]] = {
            "Manual Allocator": ManualAllocator,
            "Markovits Allocator": MarkovitsAllocator,
        }
        self._plot_data_cache: Optional[pd.DataFrame] = None # Retained for potential future use
        self._plot_data_cache_params: Optional[Dict[str, Any]] = None # Retained

        self._create_widgets()

        if not self._load_application_state():
            # No global instruments to add initially.
            self._update_allocator_selector_dropdown()
            self._refresh_allocations_display_area()
            self.set_status("Welcome! Started fresh.")
        else:
            self.set_status("Application state loaded successfully.", success=True)
            # Plotting on load is handled within _load_application_state if allocators exist

    def _create_widgets(self):
        main_v_pane = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_v_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        top_frame_outer = ttk.Frame(main_v_pane)
        main_v_pane.add(top_frame_outer, weight=3)
        top_h_pane = ttk.PanedWindow(top_frame_outer, orient=tk.HORIZONTAL)
        top_h_pane.pack(fill=tk.BOTH, expand=True)

        self.plot_frame_tl = ttk.LabelFrame(top_h_pane, text="Portfolio Performance (Out-of-Sample)", padding=5)
        top_h_pane.add(self.plot_frame_tl, weight=3)
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame_tl)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

        self.top_right_controls_frame = ttk.Frame(top_h_pane, padding=5)
        top_h_pane.add(self.top_right_controls_frame, weight=1)

        action_button_bar = ttk.Frame(self.top_right_controls_frame)
        action_button_bar.pack(pady=(0,10), fill="x")
        self.global_update_button = ttk.Button(action_button_bar, text="FIT & PLOT", command=self._on_global_update_button_click, style="Accent.TButton")
        self.global_update_button.pack(side="left", fill="x", expand=True, ipady=5, padx=(0,2))
        self.save_state_button = ttk.Button(action_button_bar, text="SAVE STATE", command=self._save_application_state, style="Info.TButton")
        self.save_state_button.pack(side="left", fill="x", expand=True, ipady=5, padx=(2,0))
        
        self.plot_dividends_var = tk.BooleanVar(value=False)
        self.plot_dividends_checkbox = ttk.Checkbutton(self.top_right_controls_frame, 
                                                    text="Plot with Dividends", 
                                                    variable=self.plot_dividends_var)
        self.plot_dividends_checkbox.pack(pady=(0, 5), fill='x')
        
        date_config_frame = ttk.Frame(self.top_right_controls_frame)
        date_config_frame.pack(fill="x", pady=(0,10))
        
        ttk.Label(date_config_frame, text="Fit Start Date:").grid(row=0, column=0, sticky="w", padx=(0,2))
        self.fit_start_date_entry = ttk.Entry(date_config_frame, width=12)
        self.fit_start_date_entry.grid(row=0, column=1, sticky="ew", padx=(0,5))
        self.fit_start_date_entry.insert(0, (date.today() - timedelta(days=365*2)).strftime("%Y-%m-%d"))
        
        ttk.Label(date_config_frame, text="Fit End Date:").grid(row=1, column=0, sticky="w", padx=(0,2))
        self.fit_end_date_entry = ttk.Entry(date_config_frame, width=12)
        self.fit_end_date_entry.grid(row=1, column=1, sticky="ew")
        self.fit_end_date_entry.insert(0, (date.today() - timedelta(days=30)).strftime("%Y-%m-%d"))
        date_config_frame.grid_columnconfigure(1, weight=1)

        alloc_display_outer_frame = ttk.LabelFrame(self.top_right_controls_frame, text="Selected Allocator Details", padding=5)
        alloc_display_outer_frame.pack(fill="both", expand=True, pady=(5,0))
        ttk.Label(alloc_display_outer_frame, text="View Allocator:").pack(side="top", anchor="w", padx=2, pady=(0,2))
        self.allocator_selector_var = tk.StringVar()
        self.allocator_selector_combo = ttk.Combobox(alloc_display_outer_frame, textvariable=self.allocator_selector_var, state="readonly", width=30)
        self.allocator_selector_combo.pack(side="top", fill="x", pady=(0,5), padx=2)
        self.allocator_selector_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_allocations_display_area())
        self.allocations_text_widget = tk.Text(alloc_display_outer_frame, height=10, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1)
        self.allocations_text_scrollbar = ttk.Scrollbar(alloc_display_outer_frame, command=self.allocations_text_widget.yview)
        self.allocations_text_widget.configure(yscrollcommand=self.allocations_text_scrollbar.set)
        self.allocations_text_scrollbar.pack(side="right", fill="y")
        self.allocations_text_widget.pack(side="left", fill="both", expand=True)
        self.allocations_text_widget.insert(tk.END, "Select an allocator to view its details.")
        self.allocations_text_widget.config(state=tk.DISABLED, background=self.root.cget('bg'))

        # --- Bottom area: Allocator Management Only ---
        bottom_frame_outer = ttk.Frame(main_v_pane) 
        main_v_pane.add(bottom_frame_outer, weight=1) # Adjusted weight, can be tuned
        
        self.allocator_mgmt_frame = ttk.LabelFrame(bottom_frame_outer, text="Allocator Setup", padding=5)
        self.allocator_mgmt_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0) # Takes full space of bottom_frame_outer
        self._create_allocator_management_ui()

        self._setup_plot_axes_appearance()
        self._set_initial_plot_view_limits()
        self.fig.tight_layout()
        self.canvas.draw()
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=0, pady=0)

    # Global instrument management UI methods (_create_instrument_management_ui, 
    # _add_instrument_row_ui, _delete_instrument_row_ui, 
    # _validate_single_instrument_entry_for_duplicates, 
    # _collect_and_validate_instruments) have been REMOVED.

    def _create_allocator_management_ui(self):
        top_bar = ttk.Frame(self.allocator_mgmt_frame)
        top_bar.pack(fill="x", pady=(0,5))
        ttk.Label(top_bar, text="Allocator Type:").pack(side="left", padx=(0,5))
        self.new_allocator_type_var = tk.StringVar()
        self.new_allocator_type_combo = ttk.Combobox(top_bar, textvariable=self.new_allocator_type_var,
                                                     values=list(self.available_allocator_types.keys()), state="readonly", width=20)
        if self.available_allocator_types: self.new_allocator_type_combo.current(0)
        self.new_allocator_type_combo.pack(side="left", padx=(0,10))
        ttk.Button(top_bar, text="Create Allocator", command=self._on_create_allocator_button_click, style="Success.TButton").pack(side="left")

        list_area = ttk.Frame(self.allocator_mgmt_frame)
        list_area.pack(fill="both", expand=True, pady=5)
        self.allocators_canvas = tk.Canvas(list_area, borderwidth=0, highlightthickness=0)
        self.allocators_list_scrollframe = ttk.Frame(self.allocators_canvas)
        scrollbar = ttk.Scrollbar(list_area, orient="vertical", command=self.allocators_canvas.yview)
        self.allocators_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.allocators_canvas.pack(side="left", fill="both", expand=True)
        self.allocators_canvas.create_window((0,0), window=self.allocators_list_scrollframe, anchor="nw")
        self.allocators_list_scrollframe.bind("<Configure>", lambda e: self.allocators_canvas.configure(scrollregion=self.allocators_canvas.bbox("all")))
        self._redraw_allocator_list_ui()

    def _redraw_allocator_list_ui(self):
        for widget in self.allocators_list_scrollframe.winfo_children(): widget.destroy()
        sorted_allocator_items = sorted(self.allocators_store.items(), key=lambda item: item[1]['instance'].get_name().lower())
        
        for allocator_id, data in sorted_allocator_items:
            allocator_instance = data['instance']
            is_enabled_var = data['is_enabled_var']
            row_frame = ttk.Frame(self.allocators_list_scrollframe)
            row_frame.pack(fill="x", pady=2, padx=2)
            chk = ttk.Checkbutton(row_frame, variable=is_enabled_var, text="", command=self._on_allocator_enable_changed)
            chk.pack(side="left", padx=(0,2))
            name_label = ttk.Label(row_frame, text=allocator_instance.get_name(), width=20, anchor="w", relief="groove", padding=2)
            name_label.pack(side="left", padx=2, fill="x", expand=True)
            config_btn = ttk.Button(row_frame, text=GEAR_ICON, width=3, style="Toolbutton.TButton",
                                    command=lambda aid=allocator_id: self._on_configure_existing_allocator(aid))
            config_btn.pack(side="left", padx=2)
            del_btn = ttk.Button(row_frame, text=DELETE_ICON, width=3, style="Danger.Toolbutton.TButton",
                                 command=lambda aid=allocator_id: self._on_delete_allocator(aid))
            del_btn.pack(side="left", padx=2)
        self.allocators_list_scrollframe.update_idletasks()
        self.allocators_canvas.configure(scrollregion=self.allocators_canvas.bbox("all"))
        self._update_allocator_selector_dropdown()

    def _on_allocator_enable_changed(self):
        self._refresh_allocations_display_area() 
        self.set_status("Allocator enabled/disabled. Click 'FIT & PLOT' to see changes.")

    def _on_create_allocator_button_click(self):
        allocator_type_name = self.new_allocator_type_var.get()
        if not allocator_type_name:
            messagebox.showwarning("Create Allocator", "Please select an allocator type.", parent=self.root)
            return
        AllocatorClass = self.available_allocator_types.get(allocator_type_name)
        if not AllocatorClass:
            messagebox.showerror("Error", f"Unknown allocator type: {allocator_type_name}", parent=self.root)
            return

        new_allocator_state = AllocatorClass.configure(parent_window=self.root, existing_state=None)

        if new_allocator_state:
            try:
                new_allocator_name = str(new_allocator_state.get('name', ''))
                if not new_allocator_name:
                    messagebox.showerror("Create Allocator", "Allocator configuration did not return a valid name.", parent=self.root)
                    return

                new_name_lower = new_allocator_name.lower()
                for data in self.allocators_store.values():
                    if data['instance'].get_name().lower() == new_name_lower:
                        messagebox.showerror("Create Allocator", f"An allocator with the name '{new_allocator_name}' already exists.", parent=self.root)
                        return
                
                new_allocator_instance = AllocatorClass(**new_allocator_state)
            except Exception as e:
                messagebox.showerror("Create Allocator", f"Failed to create allocator instance: {e}", parent=self.root)
                self.set_status(f"Error creating {allocator_type_name}: {e}", error=True)
                return

            allocator_id = str(uuid.uuid4())
            self.allocators_store[allocator_id] = {
                'instance': new_allocator_instance, 
                'is_enabled_var': tk.BooleanVar(value=True)
            }
            self.set_status(f"Allocator '{new_allocator_instance.get_name()}' created.", success=True)
            self._redraw_allocator_list_ui()
            self._refresh_allocations_display_area()
        else: 
            self.set_status(f"Allocator creation cancelled for '{allocator_type_name}'.")

    def _on_configure_existing_allocator(self, allocator_id_to_configure: str):
        data_to_configure = self.allocators_store.get(allocator_id_to_configure)
        if not data_to_configure:
            messagebox.showerror("Error", "Allocator not found for configuration.", parent=self.root)
            return
        
        existing_instance = data_to_configure['instance']
        AllocatorClass = type(existing_instance)
        existing_state = existing_instance.get_state()

        new_state_from_config = AllocatorClass.configure(
            parent_window=self.root, 
            existing_state=existing_state
        )

        if new_state_from_config:
            try:
                new_allocator_name = str(new_state_from_config.get('name', ''))
                if not new_allocator_name:
                    messagebox.showerror("Configure Allocator", "Allocator configuration did not return a valid name.", parent=self.root)
                    return

                new_name_lower = new_allocator_name.lower()
                for aid, data in self.allocators_store.items():
                    if aid != allocator_id_to_configure and data['instance'].get_name().lower() == new_name_lower:
                        messagebox.showerror("Configure Allocator", f"An allocator with the name '{new_allocator_name}' already exists (used by another allocator).", parent=self.root)
                        return
                
                reconfigured_instance = AllocatorClass(**new_state_from_config)
            except Exception as e:
                messagebox.showerror("Configure Allocator", f"Failed to reconfigure allocator instance: {e}", parent=self.root)
                self.set_status(f"Error reconfiguring {existing_instance.get_name()}: {e}", error=True)
                return

            self.allocators_store[allocator_id_to_configure]['instance'] = reconfigured_instance
            self.set_status(f"Allocator '{reconfigured_instance.get_name()}' reconfigured.", success=True)
            self._redraw_allocator_list_ui()
            self._refresh_allocations_display_area() 
        else:
            self.set_status(f"Reconfiguration of '{existing_instance.get_name()}' cancelled.")

    def _on_delete_allocator(self, allocator_id_to_delete: str):
        if allocator_id_to_delete in self.allocators_store:
            allocator_name = self.allocators_store[allocator_id_to_delete]['instance'].get_name()
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete allocator '{allocator_name}'?", parent=self.root):
                del self.allocators_store[allocator_id_to_delete]
                self.set_status(f"Allocator '{allocator_name}' deleted.", success=True)
                self._redraw_allocator_list_ui()
                if self.allocator_selector_var.get() == allocator_name:
                    self.allocator_selector_var.set("") 
                    if self.allocator_selector_combo['values']: 
                        self.allocator_selector_combo.current(0) 
                self._refresh_allocations_display_area() 
        else:
            messagebox.showerror("Error", "Allocator not found for deletion.", parent=self.root)

    def _on_global_update_button_click(self, is_auto_load_call=False):
        if not is_auto_load_call:
            self.set_status("Processing Fit & Plot...")

        fitting_start_dt = self.parse_date_entry(self.fit_start_date_entry, "Fit Start Date")
        fitting_end_dt = self.parse_date_entry(self.fit_end_date_entry, "Fit End Date")
        if not fitting_start_dt or not fitting_end_dt: return

        if fitting_start_dt >= fitting_end_dt:
            messagebox.showerror("Date Error", "Fit Start Date must be before Fit End Date.", parent=self.root)
            return
        
        plot_start_dt = fitting_end_dt 
        plot_actual_end_dt = date.today()

        if plot_start_dt >= plot_actual_end_dt:
            messagebox.showerror("Date Error", 
                                 f"Fit End Date ({plot_start_dt.strftime('%Y-%m-%d')}) must be before today ({plot_actual_end_dt.strftime('%Y-%m-%d')}) to plot performance.", 
                                 parent=self.root)
            self.ax.clear()
            self._setup_plot_axes_appearance()
            self.ax.text(0.5, 0.5, "Plotting period is invalid.\nFit End Date must be before today.",
                          ha='center', va='center', transform=self.ax.transAxes, fontsize='small')
            self.fig.tight_layout()
            self.canvas.draw()
            self._refresh_allocations_display_area()
            return
        
        enabled_allocators_data = []
        any_allocator_failed_computation = False
        for aid, data in self.allocators_store.items():
            if data['is_enabled_var'].get():
                allocator = data['instance']
                try:
                    computed_allocs = allocator.compute_allocations(fitting_start_dt, fitting_end_dt)
                    if computed_allocs is None: 
                        logger.warning(f"Allocator {allocator.get_name()} returned None from compute_allocations.")
                        any_allocator_failed_computation = True; continue
                    enabled_allocators_data.append({'instance': allocator, 'computed_allocations': computed_allocs})
                except Exception as e:
                    msg = f"Error computing allocations for {allocator.get_name()}: {e}"; logger.error(msg)
                    self.set_status(msg, error=True);
                    any_allocator_failed_computation = True
        
        if not enabled_allocators_data and not any_allocator_failed_computation:
             self.set_status("No allocators enabled or no allocations computed. Nothing to plot.", error=not is_auto_load_call)
             self.ax.clear(); self._setup_plot_axes_appearance()
             self.ax.text(0.5, 0.5, "No data to plot. Enable allocators and ensure they compute.", ha='center', va='center', transform=self.ax.transAxes, fontsize='small')
             self.fig.tight_layout(); self.canvas.draw(); self._refresh_allocations_display_area()
             return

        all_instruments_for_plot_data = set()
        for alloc_data in enabled_allocators_data:
            for ticker, weight in alloc_data['computed_allocations'].items():
                if abs(weight) > 1e-9:
                    all_instruments_for_plot_data.add(ticker)
        
        historical_prices_for_plot, problematic_tickers_fetch = self._fetch_plot_data(
            all_instruments_for_plot_data, 
            plot_start_dt, 
            plot_actual_end_dt,
            self.plot_dividends_var.get()
        )

        if problematic_tickers_fetch:
             messagebox.showwarning("Plot Data Issues", f"Could not fetch/validate plot data for ticker(s):\n{', '.join(sorted(list(problematic_tickers_fetch)))}.", parent=self.root)

        self.ax.clear()
        self._setup_plot_axes_appearance()
        self.ax.set_xlim(plot_start_dt, plot_actual_end_dt)
        
        num_series_plotted = 0
        for alloc_data in enabled_allocators_data:
            allocator = alloc_data['instance']
            current_allocs = alloc_data['computed_allocations']
            
            instruments_to_plot_for_this_alloc = {
                inst for inst, weight in current_allocs.items() 
                if abs(weight) > 1e-9 and inst in historical_prices_for_plot.columns and not historical_prices_for_plot[inst].isnull().all()
            }

            if not instruments_to_plot_for_this_alloc:
                self.ax.plot([], [], label=f"{allocator.get_name()} (No plottable data)"); num_series_plotted+=1; continue

            alloc_prices_for_plot_period = historical_prices_for_plot[list(instruments_to_plot_for_this_alloc)]
            alloc_prices_for_plot_period = alloc_prices_for_plot_period[alloc_prices_for_plot_period.index.date <= plot_actual_end_dt]

            if alloc_prices_for_plot_period.empty or alloc_prices_for_plot_period.shape[0] < 2:
                self.ax.plot([], [], label=f"{allocator.get_name()} (Insufficient data for plot period)"); num_series_plotted+=1; continue
            
            daily_returns = alloc_prices_for_plot_period.pct_change()
            relevant_daily_returns = daily_returns[daily_returns.index.date >= plot_start_dt].copy()
            relevant_daily_returns.dropna(how='all', inplace=True)

            if relevant_daily_returns.empty:
                logger.info(f"({allocator.get_name()}): No daily returns available in the plotting period starting {plot_start_dt}.")
                self.ax.plot([], [], label=f"{allocator.get_name()} (No returns in plot period)"); num_series_plotted+=1; continue

            alloc_series_data = {
                inst: current_allocs.get(inst, 0.0) 
                for inst in relevant_daily_returns.columns 
                if inst in current_allocs
            }
            alloc_series = pd.Series(alloc_series_data)
            
            common_cols_for_dot_product = [col for col in alloc_series.index if col in relevant_daily_returns.columns]
            
            if not common_cols_for_dot_product:
                 self.ax.plot([], [], label=f"{allocator.get_name()} (No common data for returns)"); num_series_plotted+=1; continue

            portfolio_daily_returns = relevant_daily_returns[common_cols_for_dot_product].mul(alloc_series[common_cols_for_dot_product], axis=1).sum(axis=1)
            
            plot_dates_series = [plot_start_dt]
            cumulative_performance_series = [0.0]

            if not portfolio_daily_returns.empty:
                cumulative_calc = (1 + portfolio_daily_returns).cumprod() - 1
                for idx_date, cum_ret_val in cumulative_calc.items():
                    current_dt = idx_date.date() if isinstance(idx_date, pd.Timestamp) else idx_date
                    if current_dt > plot_dates_series[-1]:
                        plot_dates_series.append(current_dt)
                        cumulative_performance_series.append(cum_ret_val * 100.0)
                    elif current_dt == plot_dates_series[-1] and current_dt == plot_start_dt:
                        cumulative_performance_series[-1] = cum_ret_val * 100.0
            
            label_suffix = " (Performance)"
            self.ax.plot(plot_dates_series, cumulative_performance_series, linestyle='-', label=f"{allocator.get_name()}{label_suffix}")
            num_series_plotted +=1
        
        if num_series_plotted > 0 : self.ax.legend(fontsize='x-small', loc='best')
        else: self.ax.text(0.5, 0.5, "No performance data to plot.", ha='center', va='center', transform=self.ax.transAxes, fontsize='small')

        self.fig.autofmt_xdate(rotation=25, ha='right'); self.fig.tight_layout(pad=1.5); self.canvas.draw()
        self._refresh_allocations_display_area()
        if not is_auto_load_call:
            status_msg = "Fit & Plot complete."
            if problematic_tickers_fetch: status_msg += " Some tickers had data issues for plotting."
            if any_allocator_failed_computation: status_msg += " Some allocators failed computation."
            self.set_status(status_msg, success=not (problematic_tickers_fetch or any_allocator_failed_computation), 
                            error=any_allocator_failed_computation)

    def _fetch_plot_data(self, instruments: Set[str], plot_start_dt: date, plot_end_dt: date, include_dividends: bool) -> Tuple[pd.DataFrame, Set[str]]:
        if not instruments:
            return pd.DataFrame(), set()


        fetch_start_dt = plot_start_dt - timedelta(days=7)
        # Alpha Vantage expects uppercase tickers. `instruments` here are original case from user input or state.
        instruments_upper_for_fetch = {ticker.upper() for ticker in instruments}
        
        fetched_df, initially_problematic_tickers_upper = av_fetcher(
            instruments_upper_for_fetch, 
            pd.to_datetime(fetch_start_dt), 
            pd.to_datetime(plot_end_dt)
            # include_dividends and interval are not part of av_fetcher signature
            # av_fetcher returns daily adjusted data by default.
        )
        # Map problematic uppercase tickers back to original case if possible, though `instruments` set is the source of truth.
        # For simplicity, we'll rely on the fact that subsequent processing uses original case from `instruments`.
        current_problematic_tickers = {ticker for ticker in instruments 
                                       if ticker.upper() in initially_problematic_tickers_upper}
        current_problematic_tickers.update({ticker_upper for ticker_upper in initially_problematic_tickers_upper 
                                            if ticker_upper not in [t.upper() for t in instruments]}) # Add any truly unknown/problematic uppercase tickers

        if fetched_df.empty:
            return pd.DataFrame(), current_problematic_tickers

        field_name = 'AdjClose' if include_dividends else 'Close'
        
        if not (isinstance(fetched_df.columns, pd.MultiIndex) and 'Field' in fetched_df.columns.names):
            logger.warning(f"Fetched DataFrame for {instruments} does not have expected MultiIndex ('Field', 'Ticker').")
            current_problematic_tickers.update(instruments)
            return pd.DataFrame(), current_problematic_tickers
            
        available_fields = fetched_df.columns.get_level_values('Field').unique().tolist()
        if field_name not in available_fields:
            logger.warning(f"Required field '{field_name}' not in {available_fields} for {instruments}.")
            current_problematic_tickers.update(instruments)
            return pd.DataFrame(), current_problematic_tickers
            
        try:
            valid_tickers_in_df = set(fetched_df.columns.get_level_values('Ticker').unique())
            tickers_to_extract = list(instruments - current_problematic_tickers & valid_tickers_in_df)

            if not tickers_to_extract:
                current_problematic_tickers.update(instruments)
                return pd.DataFrame(), current_problematic_tickers

            cols_for_xs = pd.MultiIndex.from_product([[field_name], tickers_to_extract], names=['Field', 'Ticker'])
            actual_cols_to_select = fetched_df.columns.intersection(cols_for_xs)

            if actual_cols_to_select.empty:
                current_problematic_tickers.update(instruments)
                return pd.DataFrame(), current_problematic_tickers
            
            processed_df = fetched_df[actual_cols_to_select].xs(key=field_name, level='Field', axis=1, drop_level=True)
        
        except KeyError as e:
            logger.error(f"KeyError during .xs for '{field_name}': {e}.")
            current_problematic_tickers.update(instruments)
            return pd.DataFrame(), current_problematic_tickers
        except Exception as e:
            logger.error(f"Unexpected error extracting field '{field_name}': {e}.")
            current_problematic_tickers.update(instruments)
            return pd.DataFrame(), current_problematic_tickers

        missing_after_extraction = instruments - set(processed_df.columns)
        current_problematic_tickers.update(missing_after_extraction)
        
        if processed_df.empty:
             return pd.DataFrame(), current_problematic_tickers

        filled_df = processed_df.ffill().bfill()
        final_df = filled_df.dropna(axis=1, how='all')
        
        dropped_all_nans = set(filled_df.columns) - set(final_df.columns)
        current_problematic_tickers.update(dropped_all_nans)
        
        surviving_requested_tickers = list(instruments - current_problematic_tickers)
        final_df = final_df[[col for col in surviving_requested_tickers if col in final_df.columns]]
        
        return final_df, current_problematic_tickers

    def _save_application_state(self):
        self.set_status("Saving application state...")
        state = {
            "fit_start_date": self.fit_start_date_entry.get(),
            "fit_end_date": self.fit_end_date_entry.get(),
            "allocators": [],
            "plot_dividends": self.plot_dividends_var.get(),
            "window_geometry": self.root.geometry()
        }

        for aid, data in self.allocators_store.items():
            instance = data['instance']
            allocator_type_name = None
            for type_name_key, AllocatorClassInMap in self.available_allocator_types.items():
                if isinstance(instance, AllocatorClassInMap):
                    allocator_type_name = type_name_key; break
            
            if not allocator_type_name:
                logger.warning(f"Type for allocator '{instance.get_name()}' not found. Skipping save of this allocator."); continue

            allocator_state_to_save = instance.get_state()
            state["allocators"].append({
                "id": aid, 
                "type_name": allocator_type_name, 
                "is_enabled": data['is_enabled_var'].get(),
                "allocator_state": allocator_state_to_save 
            })
        
        try:
            with open(SAVE_STATE_FILENAME, 'w') as f: 
                json.dump(state, f, indent=4, default=lambda o: list(o) if isinstance(o, set) else o)
            self.set_status("Application state saved successfully.", success=True)
        except IOError as e:
            self.set_status(f"Error saving state: {e}", error=True)
            messagebox.showerror("Save Error", f"Could not save state: {e}", parent=self.root)
        except TypeError as e:
            self.set_status(f"Error serializing state for save: {e}", error=True)
            messagebox.showerror("Save Error", f"Could not serialize state for saving: {e}. Ensure all state data is JSON-compatible.", parent=self.root)

    def _load_application_state(self) -> bool:
        if not os.path.exists(SAVE_STATE_FILENAME): 
            self.set_status("No saved state file found.")
            return False
        try:
            with open(SAVE_STATE_FILENAME, 'r') as f: state = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            self.set_status(f"Error loading state file: {e}", error=True)
            messagebox.showwarning("Load Warning", f"Could not load state: {e}\nStarting fresh.", parent=self.root)
            return False

        try:
            self.fit_start_date_entry.delete(0, tk.END)
            self.fit_start_date_entry.insert(0, state.get("fit_start_date", (date.today() - timedelta(days=365*2)).strftime("%Y-%m-%d")))
            self.fit_end_date_entry.delete(0, tk.END)
            self.fit_end_date_entry.insert(0, state.get("fit_end_date", (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")))

            if state.get("plot_dividends", False):
                self.plot_dividends_var.set(True); self.plot_dividends_checkbox.state(['selected'])
            else:
                self.plot_dividends_var.set(False); self.plot_dividends_checkbox.state(['!selected'])
                
            if "window_geometry" in state: self.root.geometry(state["window_geometry"])

            self.allocators_store.clear()
            for saved_alloc_data in state.get("allocators", []):
                allocator_type_name = saved_alloc_data.get("type_name")
                AllocatorClass = self.available_allocator_types.get(allocator_type_name)
                if not AllocatorClass: 
                    logger.warning(f"Unknown allocator type '{allocator_type_name}' in saved state. Skipping."); continue
                
                allocator_state_from_save = saved_alloc_data.get("allocator_state")
                if not allocator_state_from_save or not isinstance(allocator_state_from_save, dict):
                    logger.warning(f"Missing/invalid 'allocator_state' for type '{allocator_type_name}' in saved state. Skipping.")
                    continue
                
                if 'name' not in allocator_state_from_save: # Should be guaranteed by save, but good check
                    allocator_state_from_save['name'] = f"Unnamed {allocator_type_name} {str(uuid.uuid4())[:4]}"
                
                if 'instruments' in allocator_state_from_save and isinstance(allocator_state_from_save['instruments'], list):
                    allocator_state_from_save['instruments'] = set(allocator_state_from_save['instruments'])

                allocator_id = saved_alloc_data.get("id", str(uuid.uuid4())); 
                new_instance: Optional[PortfolioAllocator] = None
                try:
                    new_instance = AllocatorClass(**allocator_state_from_save)
                except Exception as e: 
                    loaded_name = allocator_state_from_save.get('name', 'unknown allocator')
                    logger.error(f"Failed to initialize allocator '{loaded_name}' from saved state: {e}", exc_info=True); 
                    self.set_status(f"Error loading {loaded_name}: {e}", error=True)
                    continue
                
                if new_instance: 
                    self.allocators_store[allocator_id] = {
                        'instance': new_instance, 
                        'is_enabled_var': tk.BooleanVar(value=saved_alloc_data.get("is_enabled", True))
                    }
            
            self._redraw_allocator_list_ui(); 
            self._refresh_allocations_display_area()
            self._set_initial_plot_view_limits()
            self.canvas.draw()
            if self.allocators_store:
                self._on_global_update_button_click(is_auto_load_call=True)
            else:
                self.set_status("State loaded. No allocators defined to plot.")
            return True
            
        except Exception as e:
            self.set_status(f"Critical error processing loaded state: {e}", error=True);
            logger.exception("Critical error processing loaded state. Resetting application.")
            messagebox.showerror("Load Error", f"Critical error processing state: {e}\nStarting fresh.", parent=self.root)
            self.allocators_store.clear()
            self._redraw_allocator_list_ui()
            self._refresh_allocations_display_area()
            return False

    def _update_allocator_selector_dropdown(self):
        allocator_names = sorted([data['instance'].get_name() for data in self.allocators_store.values()])
        current_selection = self.allocator_selector_var.get()
        self.allocator_selector_combo['values'] = allocator_names
        if allocator_names: 
            if current_selection in allocator_names: self.allocator_selector_var.set(current_selection)
            else: self.allocator_selector_var.set(allocator_names[0])
        else: self.allocator_selector_var.set("") 

    def _refresh_allocations_display_area(self):
        self.allocations_text_widget.config(state=tk.NORMAL, background='white'); self.allocations_text_widget.delete("1.0", tk.END)
        selected_allocator_name = self.allocator_selector_var.get(); 
        display_text = "No allocator selected or not found."
        found_allocator_data = None
        
        if selected_allocator_name:
            for data_dict in self.allocators_store.values(): 
                if data_dict['instance'].get_name() == selected_allocator_name: 
                    found_allocator_data = data_dict; break
        
        if found_allocator_data:
            allocator = found_allocator_data['instance']
            is_enabled = found_allocator_data['is_enabled_var'].get()
            
            allocs = getattr(allocator, '_allocations', {})

            status_text = "ENABLED" if is_enabled else "DISABLED"
            display_text = f"Allocator: '{allocator.get_name()}' ({status_text})\nType: {type(allocator).__name__}\n"
            display_text += f"Instruments: {', '.join(sorted(list(allocator.get_instruments()))) if allocator.get_instruments() else 'None'}\n"
            
            if isinstance(allocator, MarkovitsAllocator):
                display_text += f"Optimization: {allocator.optimization_target}\n"
                display_text += f"Allows Shorting: {allocator._allow_shorting}\n"
                display_text += f"Use Adjusted Close: {allocator._use_adj_close}\n"
            
            if allocs: 
                alloc_sum = sum(allocs.values())
                display_text += "\nLast Computed Allocations (after Fit & Plot):\n" + "\n".join([f"  {inst}: {percent:.2%}" for inst, percent in sorted(allocs.items()) if abs(percent)>1e-9])
                if not (abs(alloc_sum - 1.0) < 1e-7 or (not any(abs(v)>1e-9 for v in allocs.values()) and abs(alloc_sum) < 1e-9)):
                    display_text += f"\n\nWARNING: Allocations sum to {alloc_sum*100:.2f}%."
                elif not any(abs(v)>1e-9 for v in allocs.values()): 
                    display_text += "\n(All allocations are zero)"
            else: 
                display_text += "\nNo allocations computed yet or available."
                if is_enabled : display_text += "\nRun 'FIT & PLOT' to compute."
        elif not self.allocators_store:
            display_text = "No allocators created yet."
        
        self.allocations_text_widget.insert(tk.END, display_text)
        self.allocations_text_widget.config(state=tk.DISABLED, background=self.root.cget('bg'))

    def _setup_plot_axes_appearance(self):
        self.ax.clear() 
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("Cumulative Performance (%)")
        self.ax.set_title("Portfolio Performance (Out-of-Sample)")
        self.ax.grid(True, linestyle=':', alpha=0.7)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=12, interval_multiples=True))
        self.ax.yaxis.set_major_formatter(mtick.PercentFormatter())

    def _set_initial_plot_view_limits(self):
        try:
            start_dt_str = self.fit_end_date_entry.get() 
            start_dt = datetime.strptime(start_dt_str, "%Y-%m-%d").date()
            end_dt = date.today()
            if start_dt < end_dt: 
                self.ax.set_xlim(start_dt, end_dt)
            else: 
                self.ax.set_xlim(end_dt - timedelta(days=30), end_dt)
        except ValueError: 
            self.ax.set_xlim(date.today() - timedelta(days=30), date.today())

    def parse_date_entry(self, entry_widget: ttk.Entry, date_name: str) -> Optional[date]:
        date_str = entry_widget.get().strip()
        if not date_str: messagebox.showerror("Input Error", f"{date_name} cannot be empty.", parent=self.root); return None
        try: return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError: messagebox.showerror("Input Error", f"Invalid {date_name} (YYYY-MM-DD).", parent=self.root); return None

    def set_status(self, message: str, error: bool = False, success: bool = False):
        self.status_bar.config(text=message)
        if error: self.status_bar.config(foreground="white", background="#A62F03")
        elif success: self.status_bar.config(foreground="white", background="#027A48")
        else: self.status_bar.config(foreground="black", background=ttk.Style().lookup('TLabel', 'background'))

    def _on_window_closing(self):
        try:
            existing_state = {}
            if os.path.exists(SAVE_STATE_FILENAME):
                try:
                    with open(SAVE_STATE_FILENAME, 'r') as f:
                        existing_state = json.load(f)
                except (IOError, json.JSONDecodeError) as e:
                    logger.warning(f"Could not load existing state on close to save geometry: {e}")
            
            existing_state["window_geometry"] = self.root.geometry()
            
            with open(SAVE_STATE_FILENAME, 'w') as f:
                json.dump(existing_state, f, indent=4, default=lambda o: list(o) if isinstance(o, set) else o)
        except Exception as e:
            logger.error(f"Error saving window geometry on close: {e}", exc_info=True)
        finally:
            self.root.destroy()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Basic logging config
    multiprocessing.freeze_support() 
    root = tk.Tk()
    style = ttk.Style()
    if 'clam' in style.theme_names(): 
        style.theme_use('clam')

    style.configure("Error.TEntry", foreground="red", fieldbackground="#FFEEEE")
    style.configure("Accent.TButton", font=('Helvetica', 9, 'bold'), padding=4)
    style.configure("Info.TButton", font=('Helvetica', 9), padding=4)
    style.configure("Success.TButton", foreground="white", background="#28a745", font=('Helvetica', 9, 'normal'), borderwidth=1, relief="raised")
    style.map("Success.TButton", background=[('active', '#218838'), ('pressed', '#1e7e34')], relief=[('pressed', 'sunken')])
    style.configure("Danger.TButton", foreground="white", background="#dc3545", font=('Helvetica', 9, 'normal'), borderwidth=1, relief="raised")
    style.map("Danger.TButton", background=[('active', '#c82333'), ('pressed', '#b21f2d')], relief=[('pressed', 'sunken')])
    style.configure("Toolbutton.TButton", padding=2, relief="flat", font=('Arial', 10))
    style.map("Toolbutton.TButton", relief=[('pressed', 'sunken'), ('hover', 'groove'), ('!pressed', 'flat')], background=[('active', '#e0e0e0')])
    style.configure("Danger.Toolbutton.TButton", foreground="#c00000", padding=2, relief="flat", font=('Arial', 10))
    style.map("Danger.Toolbutton.TButton", relief=[('pressed', 'sunken'), ('hover', 'groove'), ('!pressed', 'flat')], foreground=[('pressed', 'darkred'), ('hover', 'red'), ('!pressed', '#c00000')], background=[('active', '#fde0e0')])

    app_instance = App(root)
    root.mainloop()