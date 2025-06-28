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
import uuid
import json
import os
import platform
import logging # Added logging
from typing import Optional, Set, Dict, Type, Any, List, Tuple

# Import the new AllocatorState along with PortfolioAllocator
from allocator.allocator import PortfolioAllocator, AllocatorState
from portfolio import Portfolio # Added import

from data_getter import av_fetcher # Changed to import av_fetcher directly
from allocator_manager import AllocatorManager
from portfolio_info import PortfolioInfo

# Setup logger for this module
logger = logging.getLogger(__name__)

GEAR_ICON = "\u2699"
DELETE_ICON = "\u2716"
SAVE_STATE_FILENAME = "portfolio_app_state.json"

def _is_windows() -> bool:
    """Check if running on Windows"""
    return platform.system() == "Windows"

def _is_dark_mode() -> bool:
    """Detect if Windows is using dark mode"""
    if not _is_windows():
        return False
    
    try:
        import winreg
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0  # 0 = dark mode, 1 = light mode
    except Exception as e:
        logger.info(f"Could not detect Windows theme: {e}")
        return False  # Default to light mode if detection fails

def _setup_windows_theme(root: tk.Tk) -> bool:
    """Setup Windows 11-style theme if on Windows"""
    if not _is_windows():
        return False
    
    try:
        import sv_ttk
        
        # Detect system theme
        is_dark = _is_dark_mode()
        
        # Apply the theme
        if is_dark:
            sv_ttk.set_theme("dark")
            logger.info("Applied dark Windows 11 theme")
        else:
            sv_ttk.set_theme("light") 
            logger.info("Applied light Windows 11 theme")
        
        return True
        
    except ImportError:
        logger.warning("sv-ttk not available, falling back to default theme")
        return False
    except Exception as e:
        logger.error(f"Error setting up Windows theme: {e}")
        return False

def _setup_matplotlib_theme_colors(is_dark_theme: bool = False):
    """Configure matplotlib colors to match the theme"""
    try:
        import matplotlib.pyplot as plt
        
        if is_dark_theme:
            # Dark theme colors
            plt.style.use('dark_background')
            return {
                'bg_color': '#2b2b2b',
                'text_color': '#ffffff',
                'grid_color': '#404040'
            }
        else:
            # Light theme colors (default)
            plt.rcParams.update(plt.rcParamsDefault)  # Reset to defaults
            return {
                'bg_color': '#ffffff',
                'text_color': '#000000', 
                'grid_color': '#cccccc'
            }
    except Exception as e:
        logger.error(f"Error configuring matplotlib theme: {e}")
        return None

# DuplicateAllocatorDialog and DatePickerDialog moved to their respective component files


# PortfolioInfo class moved to portfolio_info.py

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Portfolio Allocation Tool")
        self.root.geometry("1200x800")
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_closing)

        # Theme setup
        self.is_windows_theme = _setup_windows_theme(root)
        self.is_dark_mode = _is_dark_mode() if _is_windows() else False
        self.matplotlib_colors = _setup_matplotlib_theme_colors(self.is_dark_mode)

        # Allocator management now handled by AllocatorManager component
        self.allocator_manager = None
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
        # Main horizontal paned window (left/right)
        self.main_h_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_h_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Create Panes --- 
        self.left_v_pane = ttk.PanedWindow(self.main_h_pane, orient=tk.VERTICAL)
        self.main_h_pane.add(self.left_v_pane, weight=3) # 60% of total width (approx 3/5)
        self.right_v_pane = ttk.PanedWindow(self.main_h_pane, orient=tk.VERTICAL)
        self.main_h_pane.add(self.right_v_pane, weight=2) # 40% of total width (approx 2/5)

        # --- Populate Right Pane First (to ensure dependant widgets exist) ---
        # Top-right: Controls
        self.top_right_controls_frame = ttk.LabelFrame(self.right_v_pane, padding=5)
        self.right_v_pane.add(self.top_right_controls_frame, weight=1) # 10% of right pane height a pprox

        action_button_bar = ttk.Frame(self.top_right_controls_frame)
        action_button_bar.pack(pady=(0,10), fill="x")
        self.global_update_button = ttk.Button(action_button_bar, text="FIT & PLOT", command=self._on_global_update_button_click, style="Accent.TButton")
        self.global_update_button.pack(side="left", fill="x", expand=True, ipady=5, padx=(0,2))
        
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
        
        ttk.Label(date_config_frame, text="Test End:").grid(row=2, column=0, sticky="w", padx=(0,2))
        self.test_end_date_entry = ttk.Entry(date_config_frame, width=12)
        self.test_end_date_entry.grid(row=2, column=1, sticky="ew")
        self.test_end_date_entry.insert(0, date.today().strftime("%Y-%m-%d"))

        date_config_frame.grid_columnconfigure(1, weight=1)

        # Bottom-right: Allocator Details
        self.allocator_details_frame = ttk.Frame(self.right_v_pane)
        self.right_v_pane.add(self.allocator_details_frame, weight=9) # 90% of right pane height approx

        selector_frame = ttk.Frame(self.allocator_details_frame)
        selector_frame.pack(fill="x", pady=(0,5), side=tk.TOP)
        ttk.Label(selector_frame, text="View Allocator:").pack(side="left", padx=(0,5))
        self.allocator_selector_var = tk.StringVar()
        self.allocator_selector_combo = ttk.Combobox(selector_frame, textvariable=self.allocator_selector_var, state="readonly", width=30)
        self.allocator_selector_combo.pack(side="left", fill="x", expand=True)
        self.allocator_selector_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_allocations_display_area())
        
        # Placeholder for the PortfolioInfo widget
        self.portfolio_info_widget = PortfolioInfo(self.allocator_details_frame)
        self.portfolio_info_widget.pack(fill="both", expand=True, side=tk.TOP, pady=(5,0))

        # --- Populate Left Pane ---
        # Top-left: Plot area
        self.plot_frame_tl = ttk.LabelFrame(self.left_v_pane, padding=5)
        self.left_v_pane.add(self.plot_frame_tl, weight=3) # 60% of left pane height
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame_tl)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

        # Bottom-left: Allocator Management
        self.allocator_mgmt_frame = ttk.LabelFrame(self.left_v_pane, padding=5)
        self.left_v_pane.add(self.allocator_mgmt_frame, weight=2) # 40% of left pane height
        self._create_allocator_management_ui()

        # Final setup
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
        # Create the AllocatorManager component
        self.allocator_manager = AllocatorManager(self.allocator_mgmt_frame)
        self.allocator_manager.pack(fill="both", expand=True)
        self.allocator_manager.set_status_callback(self.set_status)

    # Old allocator UI methods removed - now handled by AllocatorManager

    # Old allocator management methods removed - functionality now in AllocatorManager

    def _on_global_update_button_click(self, is_auto_load_call=False):
        if not is_auto_load_call:
            self.set_status("Processing Fit & Plot...")

        fitting_start_dt = self.parse_date_entry(self.fit_start_date_entry, "Fit Start Date")
        fitting_end_dt = self.parse_date_entry(self.fit_end_date_entry, "Fit End Date")
        plot_actual_end_dt = self.parse_date_entry(self.test_end_date_entry, "Test End")
        if not fitting_start_dt or not fitting_end_dt or not plot_actual_end_dt: return

        if fitting_start_dt >= fitting_end_dt:
            messagebox.showerror("Date Error", "Fit Start Date must be before Fit End Date.", parent=self.root)
            return
        
        plot_start_dt = fitting_end_dt 

        if plot_start_dt >= plot_actual_end_dt:
            messagebox.showerror("Date Error", 
                                 f"Fit End Date ({plot_start_dt.strftime('%Y-%m-%d')}) must be before Test End Date ({plot_actual_end_dt.strftime('%Y-%m-%d')}) to plot performance.", 
                                 parent=self.root)
            self.ax.clear()
            self._setup_plot_axes_appearance()
            self.ax.text(0.5, 0.5, "Plotting period is invalid.\nFit End Date must be before today.",
                          ha='center', va='center', transform=self.ax.transAxes, fontsize='small')
            self.fig.tight_layout()
            self.canvas.draw()
            self._update_allocator_selector_dropdown()
            self._refresh_allocations_display_area()
            return
        
        enabled_allocators_data = []
        any_allocator_failed_computation = False
        enabled_allocators = self.allocator_manager.get_enabled_allocators_data()
        for alloc_data in enabled_allocators:
            allocator = alloc_data['instance']
            allocator._last_computed_portfolio = None # Clear previous
            try:
                # compute_allocations now returns a Portfolio object
                computed_portfolio = allocator.compute_allocations(fitting_start_dt, fitting_end_dt, plot_actual_end_dt)
                
                if not isinstance(computed_portfolio, Portfolio):
                    logger.error(f"Allocator {allocator.get_name()} did not return a Portfolio object. Type: {type(computed_portfolio)}")
                    any_allocator_failed_computation = True; continue
                allocator._last_computed_portfolio = computed_portfolio # Store for display

                # Determine the allocations to use for the out-of-sample plot period.
                # These are the allocations active at fitting_end_dt (which is plot_start_dt)
                segments_at_fitting_end = computed_portfolio.get(fitting_end_dt)
                allocations_for_plot = None
                if segments_at_fitting_end:
                    # Use allocations from the last segment active at or before fitting_end_dt
                    allocations_for_plot = segments_at_fitting_end[-1]['allocations']
                else:
                    # No segments by fitting_end_dt means no defined strategy for the plot period
                    logger.info(f"Allocator {allocator.get_name()} has no allocation segments defined by fitting_end_dt ({fitting_end_dt}).")
                    allocations_for_plot = {} # Empty dict if no strategy

                enabled_allocators_data.append({
                    'instance': allocator, 
                    'allocations_for_plot': allocations_for_plot # This is a Dict[str, float]
                    # 'computed_portfolio': computed_portfolio # Could also store this if needed later here
                })
            except Exception as e:
                msg = f"Error computing allocations for {allocator.get_name()}: {e}";
                logger.error(msg, exc_info=True)
                # Check for no efficient target message
                if "no efficient target" in str(e).lower() or "no feasible" in str(e).lower():
                    messagebox.showerror("Optimization Error", f"Allocator '{allocator.get_name()}' has no efficient target for the given requirements.", parent=self.root)
                else:
                    self.set_status(msg, error=True)
                any_allocator_failed_computation = True
        
        if not enabled_allocators_data and not any_allocator_failed_computation:
             self.set_status("No allocators enabled or no allocations computed. Nothing to plot.", error=not is_auto_load_call)
             self.ax.clear(); self._setup_plot_axes_appearance()
             self.ax.text(0.5, 0.5, "No data to plot. Enable allocators and ensure they compute.", ha='center', va='center', transform=self.ax.transAxes, fontsize='small')
             self.fig.tight_layout(); self.canvas.draw(); self._update_allocator_selector_dropdown(); self._refresh_allocations_display_area()
             return

        all_instruments_for_plot_data = set()
        for alloc_data in enabled_allocators_data:
            # 'allocations_for_plot' is the Dict[str, float] to be used
            for ticker, weight in alloc_data['allocations_for_plot'].items():
                if abs(weight) > 1e-9: # Only consider instruments with non-negligible weight
                    all_instruments_for_plot_data.add(ticker)
        
        historical_prices_for_plot, problematic_tickers_fetch = self._fetch_plot_data(
            all_instruments_for_plot_data, 
            plot_start_dt, 
            plot_actual_end_dt,
            self.plot_dividends_var.get()
        )

        if problematic_tickers_fetch:
             messagebox.showwarning("Plot Data Issues", f"Could not fetch/validate plot data for ticker(s):\n{', '.join(sorted(list(problematic_tickers_fetch)))}.", parent=self.root)

        # Delegate plotting to each portfolio
        self.ax.clear()
        self._setup_plot_axes_appearance()
        self.ax.set_xlim(plot_start_dt, plot_actual_end_dt)
        for alloc_data in enabled_allocators_data:
            allocator = alloc_data['instance']
            portfolio_obj = allocator._last_computed_portfolio
            label = f"{allocator.get_name()} (Performance)"
            # portfolio.plot handles empty data internally
            portfolio_obj.plot(self.ax, plot_actual_end_dt, include_dividends=self.plot_dividends_var.get(), label=label)
        # Draw legend and finalize
        self.ax.legend(fontsize='x-small', loc='best')
        self.fig.autofmt_xdate(rotation=25, ha='right'); self.fig.tight_layout(pad=1.5); self.canvas.draw()
        self._update_allocator_selector_dropdown()
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
        # Use a dictionary to store sash positions for clarity
        pane_positions = {
            'main_h_pane': self.main_h_pane.sashpos(0),
            'left_v_pane': self.left_v_pane.sashpos(0),
            'right_v_pane': self.right_v_pane.sashpos(0)
        }
        state = {
            "fit_start_date": self.fit_start_date_entry.get(),
            "fit_end_date": self.fit_end_date_entry.get(),
            "test_end_date": self.test_end_date_entry.get(),
            "plot_dividends": self.plot_dividends_var.get(),
            "window_geometry": self.root.geometry(),
            "pane_positions": pane_positions
        }

        # Get component states and store under specific keys
        if self.allocator_manager:
            state["allocator_manager_state"] = self.allocator_manager.get_state()
        
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
            self.test_end_date_entry.delete(0, tk.END)
            self.test_end_date_entry.insert(0, state.get("test_end_date", date.today().strftime("%Y-%m-%d")))

            if state.get("plot_dividends", False):
                self.plot_dividends_var.set(True); self.plot_dividends_checkbox.state(['selected'])
            else:
                self.plot_dividends_var.set(False); self.plot_dividends_checkbox.state(['!selected'])
                
            if "window_geometry" in state: self.root.geometry(state["window_geometry"])

            # Restore pane positions
            pane_positions = state.get("pane_positions")
            if pane_positions and isinstance(pane_positions, dict):
                # Use a small delay to ensure the main window is ready for sash updates
                self.root.after(100, lambda: self.main_h_pane.sashpos(0, pane_positions.get('main_h_pane')))
                self.root.after(100, lambda: self.left_v_pane.sashpos(0, pane_positions.get('left_v_pane')))
                self.root.after(100, lambda: self.right_v_pane.sashpos(0, pane_positions.get('right_v_pane')))

            # Extract component states and pass to components
            # Handle both new format (allocator_manager_state) and old format (allocators) for backward compatibility
            allocator_manager_state = state.get("allocator_manager_state", None)
            if allocator_manager_state is None and "allocators" in state:
                # Backward compatibility: convert old format to new format
                allocator_manager_state = {"allocators": state.get("allocators", [])}
            
            # Destroy existing AllocatorManager if it exists (from _create_allocator_management_ui)
            if hasattr(self, 'allocator_manager') and self.allocator_manager:
                self.allocator_manager.destroy()
            
            self.allocator_manager = AllocatorManager(self.allocator_mgmt_frame, json_state=allocator_manager_state)
            self.allocator_manager.pack(fill="both", expand=True)
            self.allocator_manager.set_status_callback(self.set_status)
            
            self._update_allocator_selector_dropdown()
            self._refresh_allocations_display_area()
            self._set_initial_plot_view_limits()
            self.canvas.draw()
            if self.allocator_manager.get_enabled_allocators_data():
                self._on_global_update_button_click(is_auto_load_call=True)
            else:
                self.set_status("State loaded. No allocators defined to plot.")
            return True
            
        except Exception as e:
            self.set_status(f"Critical error processing loaded state: {e}", error=True);
            logger.exception("Critical error processing loaded state. Resetting application.")
            messagebox.showerror("Load Error", f"Critical error processing state: {e}\nStarting fresh.", parent=self.root)
            # Recreate clean allocator manager
            if hasattr(self, 'allocator_manager') and self.allocator_manager:
                self.allocator_manager.destroy()
            self.allocator_manager = AllocatorManager(self.allocator_mgmt_frame)
            self.allocator_manager.pack(fill="both", expand=True)
            self.allocator_manager.set_status_callback(self.set_status)
            self._update_allocator_selector_dropdown()
            self._refresh_allocations_display_area()
            return False

    def _update_allocator_selector_dropdown(self):
        # Get only allocators that have computed portfolios
        allocator_names = self.allocator_manager.get_allocator_names_with_portfolios()
        current_selection = self.allocator_selector_var.get()
        self.allocator_selector_combo['values'] = allocator_names
        if allocator_names: 
            if current_selection in allocator_names: self.allocator_selector_var.set(current_selection)
            else: self.allocator_selector_var.set(allocator_names[0])
        else: self.allocator_selector_var.set("") 

    def _refresh_allocations_display_area(self):
        # Destroy the old PortfolioInfo widget
        if hasattr(self, 'portfolio_info_widget') and self.portfolio_info_widget.winfo_exists():
            self.portfolio_info_widget.destroy()

        selected_allocator_name = self.allocator_selector_var.get()
        found_allocator_data = None
        
        if selected_allocator_name:
            found_allocator_data = self.allocator_manager.get_allocator_by_name(selected_allocator_name)
        
        portfolio_to_display = None
        if found_allocator_data:
            allocator = found_allocator_data['instance']
            portfolio_to_display = getattr(allocator, '_last_computed_portfolio', None)

        # Get all portfolios from enabled allocators
        all_portfolios = self.allocator_manager.get_portfolios()

        # Create a new PortfolioInfo widget with access to all portfolios
        self.portfolio_info_widget = PortfolioInfo(
            self.allocator_details_frame, 
            portfolio=portfolio_to_display,
            all_portfolios=all_portfolios,
            app_instance=self
        )
        self.portfolio_info_widget.pack(fill="both", expand=True, side=tk.TOP, pady=(5,0))

    def _setup_plot_axes_appearance(self):
        self.ax.clear() 
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("Cumulative Performance (%)")
        self.ax.set_title("Portfolio Performance (Out-of-Sample)")
        
        # Apply theme-appropriate colors if available
        if self.matplotlib_colors:
            if self.is_dark_mode:
                # Dark theme styling
                self.ax.set_facecolor('#2b2b2b')
                self.ax.tick_params(colors='#ffffff')
                self.ax.xaxis.label.set_color('#ffffff')
                self.ax.yaxis.label.set_color('#ffffff')
                self.ax.title.set_color('#ffffff')
                self.ax.grid(True, linestyle=':', alpha=0.3, color='#606060')
                # Set figure background
                self.fig.patch.set_facecolor('#1e1e1e')
            else:
                # Light theme styling (reset to defaults)
                self.ax.set_facecolor('#ffffff')
                self.ax.tick_params(colors='#000000')
                self.ax.xaxis.label.set_color('#000000')
                self.ax.yaxis.label.set_color('#000000')
                self.ax.title.set_color('#000000')
                self.ax.grid(True, linestyle=':', alpha=0.7, color='#cccccc')
                # Set figure background
                self.fig.patch.set_facecolor('#ffffff')
        else:
            # Fallback to default styling
            self.ax.grid(True, linestyle=':', alpha=0.7)
        
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=12, interval_multiples=True))
        self.ax.yaxis.set_major_formatter(mtick.PercentFormatter())

    def _set_initial_plot_view_limits(self):
        try:
            start_dt_str = self.fit_end_date_entry.get() 
            start_dt = datetime.strptime(start_dt_str, "%Y-%m-%d").date()
            end_dt_str = self.test_end_date_entry.get()
            end_dt = datetime.strptime(end_dt_str, "%Y-%m-%d").date()
            if start_dt < end_dt: 
                self.ax.set_xlim(start_dt, end_dt)
            else: 
                self.ax.set_xlim(end_dt - timedelta(days=30), end_dt)
        except ValueError: 
            self.ax.set_xlim(date.today() - timedelta(days=30), date.today())

    def parse_date_entry(self, entry_widget: ttk.Entry, date_name: str, silent: bool = False) -> Optional[date]:
        date_str = entry_widget.get().strip()
        if not date_str:
            if not silent: messagebox.showerror("Input Error", f"{date_name} cannot be empty.", parent=self.root)
            return None
        try: 
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError: 
            if not silent: messagebox.showerror("Input Error", f"Invalid {date_name} (YYYY-MM-DD).", parent=self.root)
            return None

    def set_status(self, message: str, error: bool = False, success: bool = False):
        self.status_bar.config(text=message)
        if error: self.status_bar.config(foreground="white", background="#A62F03")
        elif success: self.status_bar.config(foreground="white", background="#027A48")
        else: self.status_bar.config(foreground="black", background=ttk.Style().lookup('TLabel', 'background'))

    def _on_window_closing(self):
        """
        Prompt the user on exit whether to save or discard current state.
        """
        choice = messagebox.askyesnocancel(
            "Exit",
            "Do you want to save changes to your portfolio before exiting?\n\nYes = Save and exit\nNo = Discard and exit\nCancel = Stay in app.",
            parent=self.root
        )
        if choice is None:
            # Cancel, do nothing
            return
        elif choice is True:
            # Save state then exit
            self._save_application_state()
            self.root.destroy()
        else:
            # Discard changes and exit (just exit, do NOT save)
            self.root.destroy()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Basic logging config
    multiprocessing.freeze_support() 
    root = tk.Tk()
    
    # Create app instance (which handles theme setup)
    app_instance = App(root)
    
    # Apply custom button styles after theme is set
    style = ttk.Style()
    
    # Check if we're using Windows theme or fallback
    if not app_instance.is_windows_theme:
        # Fallback to clam theme if Windows theme not available
        if 'clam' in style.theme_names(): 
            style.theme_use('clam')
    
    # Configure custom button styles (these work with both themes)
    try:
        # Error entry style
        style.configure("Error.TEntry", foreground="red", fieldbackground="#FFEEEE")
        
        # Button styles that adapt to the current theme
        style.configure("Accent.TButton", font=('Helvetica', 9, 'bold'), padding=4)
        style.configure("Info.TButton", font=('Helvetica', 9), padding=4)
        
        # Success button (green)
        style.configure("Success.TButton", 
                       foreground="white", 
                       background="#28a745", 
                       font=('Helvetica', 9, 'normal'), 
                       borderwidth=1, 
                       relief="raised")
        style.map("Success.TButton", 
                 background=[('active', '#218838'), ('pressed', '#1e7e34')], 
                 relief=[('pressed', 'sunken')])
        
        # Danger button (red)
        style.configure("Danger.TButton", 
                       foreground="white", 
                       background="#dc3545", 
                       font=('Helvetica', 9, 'normal'), 
                       borderwidth=1, 
                       relief="raised")
        style.map("Danger.TButton", 
                 background=[('active', '#c82333'), ('pressed', '#b21f2d')], 
                 relief=[('pressed', 'sunken')])
        
        # Tool buttons
        style.configure("Toolbutton.TButton", padding=2, relief="flat", font=('Arial', 10))
        style.map("Toolbutton.TButton", 
                 relief=[('pressed', 'sunken'), ('hover', 'groove'), ('!pressed', 'flat')], 
                 background=[('active', '#e0e0e0')])
        
        # Danger tool button
        style.configure("Danger.Toolbutton.TButton", 
                       foreground="#c00000", 
                       padding=2, 
                       relief="flat", 
                       font=('Arial', 10))
        style.map("Danger.Toolbutton.TButton", 
                 relief=[('pressed', 'sunken'), ('hover', 'groove'), ('!pressed', 'flat')], 
                 foreground=[('pressed', 'darkred'), ('hover', 'red'), ('!pressed', '#c00000')], 
                 background=[('active', '#fde0e0')])
                 
    except Exception as e:
        logger.warning(f"Could not apply custom button styles: {e}")

    root.mainloop()
