# app.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, date, timedelta
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
import matplotlib.ticker as mtick # For PercentFormatter
import pandas as pd
import numpy as np
import uuid
import json
import os
from typing import Optional, Set, Dict, Type, Any, List

from allocator.allocator import PortfolioAllocator
from allocator.manual import ManualAllocator
from allocator.markovits import MarkovitsAllocator

from config import get_fetcher
Fetcher = get_fetcher()


GEAR_ICON = "\u2699"
DELETE_ICON = "\u2716"
SAVE_STATE_FILENAME = "portfolio_app_state.json"

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Portfolio Allocation Tool")
        self.root.geometry("1200x800")

        self.current_instruments_set: Set[str] = set()
        self.allocators_store: Dict[str, Dict[str, Any]] = {}
        self.available_allocator_types: Dict[str, Type[PortfolioAllocator]] = {
            "Manual Allocator": ManualAllocator,
            "Markovits Allocator": MarkovitsAllocator,
        }
        self._plot_data_cache: Optional[pd.DataFrame] = None
        self._plot_data_cache_params: Optional[Dict[str, Any]] = None

        self._create_widgets()

        if not self._load_application_state():
            self._add_instrument_row_ui()
            self._update_allocator_selector_dropdown()
            self._refresh_allocations_display_area()
            self.set_status("Welcome! Started fresh.")
        else:
            self.set_status("Application state loaded successfully.", success=True)
            # self._on_global_update_button_click(is_auto_load_call=True) # Plot on load

    def _create_widgets(self):
        main_v_pane = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_v_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        top_frame_outer = ttk.Frame(main_v_pane)
        main_v_pane.add(top_frame_outer, weight=3)
        top_h_pane = ttk.PanedWindow(top_frame_outer, orient=tk.HORIZONTAL)
        top_h_pane.pack(fill=tk.BOTH, expand=True)

        self.plot_frame_tl = ttk.LabelFrame(top_h_pane, text="Portfolio Performance (Out-of-Sample)", padding=5) # Updated title
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
        self.global_update_button = ttk.Button(action_button_bar, text="FIT & PLOT", command=self._on_global_update_button_click, style="Accent.TButton") # Renamed button
        self.global_update_button.pack(side="left", fill="x", expand=True, ipady=5, padx=(0,2))
        self.save_state_button = ttk.Button(action_button_bar, text="SAVE STATE", command=self._save_application_state, style="Info.TButton")
        self.save_state_button.pack(side="left", fill="x", expand=True, ipady=5, padx=(2,0))
        
        # Add checkbox for plotting with dividends
        self.plot_dividends_var = tk.BooleanVar(value=False)
        self.plot_dividends_checkbox = ttk.Checkbutton(self.top_right_controls_frame, 
                                                    text="Plot with Dividends", 
                                                    variable=self.plot_dividends_var)
        self.plot_dividends_checkbox.pack(pady=(0, 5), fill='x')
        
        date_config_frame = ttk.Frame(self.top_right_controls_frame)
        date_config_frame.pack(fill="x", pady=(0,10))
        
        # Renamed UI elements for dates
        ttk.Label(date_config_frame, text="Fit Start Date:").grid(row=0, column=0, sticky="w", padx=(0,2))
        self.fit_start_date_entry = ttk.Entry(date_config_frame, width=12) # Was plot_hist_start_date_entry
        self.fit_start_date_entry.grid(row=0, column=1, sticky="ew", padx=(0,5))
        self.fit_start_date_entry.insert(0, (date.today() - timedelta(days=365*2)).strftime("%Y-%m-%d"))
        
        ttk.Label(date_config_frame, text="Fit End Date:").grid(row=1, column=0, sticky="w", padx=(0,2))
        self.fit_end_date_entry = ttk.Entry(date_config_frame, width=12) # Was fitting_start_date_entry
        self.fit_end_date_entry.grid(row=1, column=1, sticky="ew")
        self.fit_end_date_entry.insert(0, (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")) # Default Fit End to 1 month ago
        
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

        bottom_frame_outer = ttk.Frame(main_v_pane)
        main_v_pane.add(bottom_frame_outer, weight=2)
        bottom_h_pane = ttk.PanedWindow(bottom_frame_outer, orient=tk.HORIZONTAL)
        bottom_h_pane.pack(fill=tk.BOTH, expand=True)
        self.instrument_mgmt_frame = ttk.LabelFrame(bottom_h_pane, text="Instrument Setup", padding=5)
        bottom_h_pane.add(self.instrument_mgmt_frame, weight=1)
        self._create_instrument_management_ui()
        self.allocator_mgmt_frame = ttk.LabelFrame(bottom_h_pane, text="Allocator Setup", padding=5)
        bottom_h_pane.add(self.allocator_mgmt_frame, weight=1)
        self._create_allocator_management_ui()

        self._setup_plot_axes_appearance()
        self._set_initial_plot_view_limits() # Uses fit_end_date_entry now for plot start
        self.fig.tight_layout()
        self.canvas.draw()
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=0, pady=0)

    # ... (_create_instrument_management_ui, _add_instrument_row_ui, _delete_instrument_row_ui,
    #      _validate_single_instrument_entry_for_duplicates, _collect_and_validate_instruments,
    #      _create_allocator_management_ui, _redraw_allocator_list_ui, _on_allocator_enable_changed,
    #      _on_create_allocator_button_click, _on_configure_existing_allocator, _on_delete_allocator
    #      remain unchanged from the previous response. Ensure they are present and complete.)
    def _create_instrument_management_ui(self):
        ttk.Button(self.instrument_mgmt_frame, text="Add Instrument Row", command=self._add_instrument_row_ui).pack(pady=5, fill="x")
        list_area = ttk.Frame(self.instrument_mgmt_frame)
        list_area.pack(fill="both", expand=True)
        self.instruments_canvas = tk.Canvas(list_area, borderwidth=0, highlightthickness=0)
        self.instruments_list_scrollframe = ttk.Frame(self.instruments_canvas)
        scrollbar = ttk.Scrollbar(list_area, orient="vertical", command=self.instruments_canvas.yview)
        self.instruments_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.instruments_canvas.pack(side="left", fill="both", expand=True)
        self.instruments_canvas.create_window((0,0), window=self.instruments_list_scrollframe, anchor="nw")
        self.instruments_list_scrollframe.bind("<Configure>", lambda e: self.instruments_canvas.configure(scrollregion=self.instruments_canvas.bbox("all")))
        self.instrument_gui_rows = []

    def _add_instrument_row_ui(self, instrument_name=""):
        row_frame = ttk.Frame(self.instruments_list_scrollframe)
        row_frame.pack(fill="x", pady=1)
        entry = ttk.Entry(row_frame, width=20)
        entry.insert(0, instrument_name) 
        entry.pack(side="left", padx=(0,5), fill="x", expand=True)
        entry.bind("<FocusOut>", lambda e, current_entry=entry: self._validate_single_instrument_entry_for_duplicates(current_entry))
        del_btn = ttk.Button(row_frame, text=DELETE_ICON, width=3, style="Danger.TButton",
                             command=lambda rf=row_frame: self._delete_instrument_row_ui(rf))
        del_btn.pack(side="left", padx=(0,2))
        self.instrument_gui_rows.append({'frame': row_frame, 'entry': entry})
        self.instruments_list_scrollframe.update_idletasks()
        self.instruments_canvas.configure(scrollregion=self.instruments_canvas.bbox("all"))
        if not instrument_name: 
            entry.focus_set()

    def _delete_instrument_row_ui(self, row_frame_to_delete: ttk.Frame):
        for i, row_data in enumerate(self.instrument_gui_rows):
            if row_data['frame'] == row_frame_to_delete:
                row_data['frame'].destroy()
                del self.instrument_gui_rows[i]
                self.set_status("Instrument row removed. Click 'FIT & PLOT' to apply changes.")
                for r_data in self.instrument_gui_rows: 
                    self._validate_single_instrument_entry_for_duplicates(r_data['entry'])
                self.instruments_list_scrollframe.update_idletasks()
                self.instruments_canvas.configure(scrollregion=self.instruments_canvas.bbox("all"))
                return

    def _validate_single_instrument_entry_for_duplicates(self, current_entry: ttk.Entry):
        if not current_entry.winfo_exists(): return True
        current_value = current_entry.get().strip().upper() 
        current_entry.delete(0, tk.END) 
        current_entry.insert(0, current_value)
        is_duplicate = False
        if current_value: 
            for row_data in self.instrument_gui_rows:
                entry_widget = row_data['entry']
                if entry_widget.winfo_exists() and entry_widget != current_entry and entry_widget.get().strip() == current_value:
                    is_duplicate = True
                    break
        current_entry.configure(style="Error.TEntry" if is_duplicate and current_value else "TEntry")
        return not (is_duplicate and current_value)

    def _collect_and_validate_instruments(self) -> Optional[Set[str]]:
        instruments = set()
        all_entries_valid_individually = True
        for row_data in self.instrument_gui_rows:
            entry = row_data['entry']
            if not entry.winfo_exists(): continue
            val_upper = entry.get().strip().upper()
            entry.delete(0, tk.END)
            entry.insert(0, val_upper)
            if not self._validate_single_instrument_entry_for_duplicates(entry):
                if entry.get().strip(): 
                    all_entries_valid_individually = False
            val = entry.get().strip() 
            if val: instruments.add(val)

        if not all_entries_valid_individually:
            messagebox.showerror("Input Error", "Duplicate instrument names found (marked red). Please correct them.", parent=self.root)
            return None
        
        if self.current_instruments_set != instruments: 
            print(f"DEBUG: Instrument set changed from {self.current_instruments_set} to {instruments}")
            self.current_instruments_set = instruments
            for aid, data in self.allocators_store.items():
                try:
                    data['instance'].on_instruments_changed(self.current_instruments_set)
                except Exception as e:
                    msg = f"Error updating {data['instance'].name} with new instruments: {e}"
                    print(msg)
                    self.set_status(msg, error=True)
            self._refresh_allocations_display_area() 
        return instruments

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
        sorted_allocator_items = sorted(self.allocators_store.items(), key=lambda item: item[1]['instance'].name.lower())
        for allocator_id, data in sorted_allocator_items:
            allocator_instance = data['instance']
            is_enabled_var = data['is_enabled_var']
            row_frame = ttk.Frame(self.allocators_list_scrollframe)
            row_frame.pack(fill="x", pady=2, padx=2)
            chk = ttk.Checkbutton(row_frame, variable=is_enabled_var, text="", command=self._on_allocator_enable_changed)
            chk.pack(side="left", padx=(0,2))
            name_label = ttk.Label(row_frame, text=allocator_instance.name, width=20, anchor="w", relief="groove", padding=2)
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
        current_instruments = self._collect_and_validate_instruments()
        if current_instruments is None: return
        new_allocator_instance = AllocatorClass.configure_or_create(
            parent_window=self.root, current_instruments=current_instruments, existing_allocator=None)
        if new_allocator_instance:
            new_name_lower = new_allocator_instance.name.lower()
            for data in self.allocators_store.values():
                if data['instance'].name.lower() == new_name_lower:
                    messagebox.showerror("Create Allocator", f"An allocator with the name '{new_allocator_instance.name}' already exists.", parent=self.root)
                    return
            allocator_id = str(uuid.uuid4())
            self.allocators_store[allocator_id] = {
                'instance': new_allocator_instance, 
                'is_enabled_var': tk.BooleanVar(value=True)
            }
            self.set_status(f"Allocator '{new_allocator_instance.name}' created.", success=True)
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
        current_instruments = self._collect_and_validate_instruments()
        if current_instruments is None: return
        reconfigured_instance = AllocatorClass.configure_or_create(
            parent_window=self.root, 
            current_instruments=current_instruments, 
            existing_allocator=existing_instance
        )
        if reconfigured_instance:
            new_name_lower = reconfigured_instance.name.lower()
            for aid, data in self.allocators_store.items():
                if aid != allocator_id_to_configure and data['instance'].name.lower() == new_name_lower:
                    messagebox.showerror("Configure Allocator", f"An allocator with the name '{reconfigured_instance.name}' already exists (used by another allocator).", parent=self.root)
                    return
            self.allocators_store[allocator_id_to_configure]['instance'] = reconfigured_instance
            self.set_status(f"Allocator '{reconfigured_instance.name}' reconfigured.", success=True)
            self._redraw_allocator_list_ui()
            self._refresh_allocations_display_area() 
        else:
            self.set_status(f"Reconfiguration of '{existing_instance.name}' cancelled.")

    def _on_delete_allocator(self, allocator_id_to_delete: str):
        if allocator_id_to_delete in self.allocators_store:
            allocator_name = self.allocators_store[allocator_id_to_delete]['instance'].name
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

        current_instruments_from_ui = self._collect_and_validate_instruments()
        if current_instruments_from_ui is None:
            self.set_status("Update failed: Please fix instrument errors.", error=True)
            return

        # Date parsing for FITTING period
        fitting_start_dt = self.parse_date_entry(self.fit_start_date_entry, "Fit Start Date")
        fitting_end_dt = self.parse_date_entry(self.fit_end_date_entry, "Fit End Date")
        if not fitting_start_dt or not fitting_end_dt: return

        if fitting_start_dt >= fitting_end_dt:
            messagebox.showerror("Date Error", "Fit Start Date must be before Fit End Date.", parent=self.root)
            return
        
        # PLOTTING period starts from Fit End Date and goes to today
        plot_start_dt = fitting_end_dt # Performance plot starts where fitting ended
        plot_actual_end_dt = date.today()

        if plot_start_dt >= plot_actual_end_dt:
            messagebox.showerror("Date Error", 
                                 f"Fit End Date ({plot_start_dt.strftime('%Y-%m-%d')}) must be before today ({plot_actual_end_dt.strftime('%Y-%m-%d')}) to plot performance.", 
                                 parent=self.root)
            # Clear plot if no valid plot period
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
                    allocator.on_instruments_changed(current_instruments_from_ui) # Ensure allocator has latest instruments
                    # Use fitting_start_dt and fitting_end_dt for computation
                    computed_allocs = allocator.compute_allocations(fitting_start_dt, fitting_end_dt)
                    if computed_allocs is None:
                        any_allocator_failed_computation = True; continue
                    enabled_allocators_data.append({'instance': allocator, 'computed_allocations': computed_allocs})
                except Exception as e:
                    msg = f"Error computing allocations for {allocator.name}: {e}"; print(msg)
                    self.set_status(msg, error=True); any_allocator_failed_computation = True
        
        if not enabled_allocators_data and not any_allocator_failed_computation:
             self.set_status("No allocators enabled or no allocations computed. Nothing to plot.", error=not is_auto_load_call) # ... (same as before)
             self.ax.clear(); self._setup_plot_axes_appearance()
             self.ax.text(0.5, 0.5, "No data to plot. Enable allocators and ensure they compute.", ha='center', va='center', transform=self.ax.transAxes, fontsize='small')
             self.fig.tight_layout(); self.canvas.draw(); self._refresh_allocations_display_area()
             return

        all_instruments_for_plot_data = set()
        for alloc_data in enabled_allocators_data:
            for ticker, weight in alloc_data['computed_allocations'].items():
                if abs(weight) > 1e-9: all_instruments_for_plot_data.add(ticker)
        
        # Extract data fetching to its own method
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
        # Plotting X-axis is from plot_start_dt (Fit End Date) to today
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
                self.ax.plot([], [], label=f"{allocator.name} (No plottable data)"); num_series_plotted+=1; continue

            alloc_prices_for_plot_period = historical_prices_for_plot[list(instruments_to_plot_for_this_alloc)]
            # Ensure prices for plot start at or before plot_start_dt to calculate first return on plot_start_dt
            alloc_prices_for_plot_period = alloc_prices_for_plot_period[alloc_prices_for_plot_period.index.date <= plot_actual_end_dt]


            if alloc_prices_for_plot_period.empty or alloc_prices_for_plot_period.shape[0] < 2:
                self.ax.plot([], [], label=f"{allocator.name} (Insufficient data for plot period)"); num_series_plotted+=1; continue
            
            daily_returns = alloc_prices_for_plot_period.pct_change()#.iloc[1:]
            
            # Filter daily_returns to start from plot_start_dt (Fit End Date)
            # The first return value will be for plot_start_dt, based on price at plot_start_dt and price at T-1.
            relevant_daily_returns = daily_returns[daily_returns.index.date >= plot_start_dt].copy()
            relevant_daily_returns.dropna(how='all', inplace=True) # Drop if first row is all NaN due to pct_change on first day

            if relevant_daily_returns.empty:
                print(f"INFO ({allocator.name}): No daily returns available in the plotting period starting {plot_start_dt}.")
                self.ax.plot([], [], label=f"{allocator.name} (No returns in plot period)"); num_series_plotted+=1; continue

            alloc_series = pd.Series({inst: current_allocs.get(inst, 0.0) for inst in relevant_daily_returns.columns if inst in current_allocs})
            # Ensure columns align for dot product
            cols_to_use = [col for col in alloc_series.index if col in relevant_daily_returns.columns]
            portfolio_daily_returns = relevant_daily_returns[cols_to_use].mul(alloc_series[cols_to_use], axis=1).sum(axis=1)
            
            # Cumulative returns: start plot with 0% on plot_start_dt (Fit End Date)
            plot_dates_series = [plot_start_dt]
            cumulative_performance_series = [0.0] # Start at 0% on Fit End Date

            if not portfolio_daily_returns.empty:
                # Cumprod on (1+r) and subtract 1 for cumulative returns
                cumulative_calc = (1 + portfolio_daily_returns).cumprod() - 1
                
                for idx_date, cum_ret_val in cumulative_calc.items():
                    current_dt = idx_date.date() if isinstance(idx_date, pd.Timestamp) else idx_date
                    # Add if date is after the start of the plot (which is plot_start_dt = fitting_end_dt)
                    # The first point (plot_start_dt, 0.0) is already added.
                    # We only add subsequent points.
                    if current_dt > plot_dates_series[-1]: # Add if new date strictly after last
                        plot_dates_series.append(current_dt)
                        cumulative_performance_series.append(cum_ret_val * 100.0) # As percentage
                    elif current_dt == plot_dates_series[-1] and current_dt == plot_start_dt: # Update the 0% if a return is available on plot_start_dt itself
                        cumulative_performance_series[-1] = cum_ret_val * 100.0


            label_suffix = " (Performance)" # ... (same suffix logic as before)
            self.ax.plot(plot_dates_series, cumulative_performance_series, linestyle='-', label=f"{allocator.name}{label_suffix}")
            num_series_plotted +=1
        
        if num_series_plotted > 0 : self.ax.legend(fontsize='x-small', loc='best')
        else: self.ax.text(0.5, 0.5, "No performance data to plot.", ha='center', va='center', transform=self.ax.transAxes, fontsize='small')

        self.fig.autofmt_xdate(rotation=25, ha='right'); self.fig.tight_layout(pad=1.5); self.canvas.draw()
        self._refresh_allocations_display_area()
        if not is_auto_load_call: # ... (same status message logic as before)
            status_msg = "Fit & Plot complete."
            if problematic_tickers_fetch: status_msg += " Some tickers had data issues for plotting."
            if any_allocator_failed_computation: status_msg += " Some allocators failed computation."
            self.set_status(status_msg, success=not (problematic_tickers_fetch or any_allocator_failed_computation), 
                            error=any_allocator_failed_computation)

    def _fetch_plot_data(self, instruments: Set[str], plot_start_dt: date, plot_end_dt: date, include_dividends: bool) -> (pd.DataFrame, Set[str]):
        """Fetch pricing data for plotting out-of-sample performance"""
        problematic_tickers = set()
        prices = pd.DataFrame()
        
        if not instruments:
            return prices, problematic_tickers
            
        print(f"DEBUG: Fetching PLOT data for: {instruments} from {plot_start_dt} to {plot_end_dt}")
        fetch_start = plot_start_dt - timedelta(days=7)  # Get extra days for returns calculation
        
        raw_hist_data = Fetcher.fetch(
            instruments, fetch_start, plot_end_dt, 
            include_dividends=include_dividends, interval="1d"
        )
        
        if raw_hist_data.empty:
            problematic_tickers = set(instruments)
            return prices, problematic_tickers

        temp_price_frames = []
        # Since tickers are always uppercase, we can simplify column logic
        for ticker in instruments:
            # Determine which column to use based on dividend preference
            field_name = 'AdjClose' if include_dividends else 'Close'
            # Column in MultiIndex format (field, ticker) - ticker is uppercase
            target_col = (field_name, ticker)
            
            if target_col in raw_hist_data.columns:
                price_series = raw_hist_data[target_col]
            # Handle single-instrument case with flat columns (no MultiIndex)
            elif field_name in raw_hist_data.columns and len(instruments) == 1:
                price_series = raw_hist_data[field_name]
            else:
                problematic_tickers.add(ticker)
                continue
                
            # Process the series
            price_series_filled = price_series.ffill().bfill()
            if price_series_filled.isnull().any():
                problematic_tickers.add(ticker)
            else:
                temp_price_frames.append(price_series_filled.rename(ticker))

        if temp_price_frames:
            prices = pd.concat(temp_price_frames, axis=1)
            
        return prices, problematic_tickers

    def _save_application_state(self):
        self.set_status("Saving application state...")
        current_instruments_to_save = [rd['entry'].get().strip().upper() for rd in self.instrument_gui_rows if rd['entry'].get().strip()]
        state = {
            "instruments": current_instruments_to_save,
            "fit_start_date": self.fit_start_date_entry.get(),   # Updated key
            "fit_end_date": self.fit_end_date_entry.get(),     # Updated key
            "allocators": []
        }
        # ... (rest of save logic using instance.save_state() is same as previous response)
        for aid, data in self.allocators_store.items():
            instance = data['instance']
            allocator_type_name = None
            for type_name_key, AllocatorClassInMap in self.available_allocator_types.items():
                if isinstance(instance, AllocatorClassInMap):
                    allocator_type_name = type_name_key; break
            if not allocator_type_name: print(f"Warning: Type for {instance.name} not found. Skipping."); continue
            config_params = instance.save_state()
            state["allocators"].append({
                "id": aid, "type_name": allocator_type_name, "instance_name": instance.name,
                "is_enabled": data['is_enabled_var'].get(), "config_params": config_params
            })
        # Add plot dividends state to saved state
        state["plot_dividends"] = self.plot_dividends_var.get()
        
        try:
            with open(SAVE_STATE_FILENAME, 'w') as f: json.dump(state, f, indent=4)
            self.set_status("Application state saved successfully.", success=True)
        except IOError as e:
            self.set_status(f"Error saving state: {e}", error=True); messagebox.showerror("Save Error", f"Could not save state: {e}", parent=self.root)


    def _load_application_state(self) -> bool:
        if not os.path.exists(SAVE_STATE_FILENAME): return False
        try:
            with open(SAVE_STATE_FILENAME, 'r') as f: state = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            self.set_status(f"Error loading state file: {e}", error=True); messagebox.showwarning("Load Warning", f"Could not load state: {e}\nStarting fresh.", parent=self.root); return False

        try:
            for widget_data in self.instrument_gui_rows: widget_data['frame'].destroy()
            self.instrument_gui_rows.clear(); loaded_instruments_set = set()
            for name in state.get("instruments", []): 
                u_name = name.upper(); self._add_instrument_row_ui(u_name); loaded_instruments_set.add(u_name)
            self.current_instruments_set = loaded_instruments_set

            # Restore dates with new keys
            self.fit_start_date_entry.delete(0, tk.END)
            self.fit_start_date_entry.insert(0, state.get("fit_start_date", (date.today() - timedelta(days=365*2)).strftime("%Y-%m-%d"))) # Updated key
            self.fit_end_date_entry.delete(0, tk.END)
            self.fit_end_date_entry.insert(0, state.get("fit_end_date", (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")))   # Updated key

            # Restore plot dividends state if present
            if state.get("plot_dividends", False):
                self.plot_dividends_var.set(True)
                self.plot_dividends_checkbox.state(['selected'])
            else:
                self.plot_dividends_var.set(False)
                self.plot_dividends_checkbox.state(['!selected'])

            self.allocators_store.clear()
            # ... (rest of load logic using instance.load_state() is same as previous response)
            for saved_alloc_data in state.get("allocators", []):
                allocator_type_name = saved_alloc_data["type_name"]
                AllocatorClass = self.available_allocator_types.get(allocator_type_name)
                if not AllocatorClass: print(f"Warning: Unknown type '{allocator_type_name}'. Skipping."); continue
                instance_name = saved_alloc_data["instance_name"]; config_params = saved_alloc_data["config_params"]
                allocator_id = saved_alloc_data.get("id", str(uuid.uuid4())); new_instance: Optional[PortfolioAllocator] = None
                try:
                    if AllocatorClass == MarkovitsAllocator: new_instance = AllocatorClass(name=instance_name, initial_instruments=self.current_instruments_set.copy())
                    else: new_instance = AllocatorClass(name=instance_name)
                    new_instance.load_state(config_params, self.current_instruments_set.copy())
                except Exception as e: print(f"ERROR: Failed to load '{instance_name}': {e}"); self.set_status(f"Error loading {instance_name}: {e}", error=True); continue
                if new_instance: self.allocators_store[allocator_id] = {'instance': new_instance, 'is_enabled_var': tk.BooleanVar(value=saved_alloc_data.get("is_enabled", True))}
                else: print(f"Warning: Could not recreate '{instance_name}'.")
            
            self._redraw_allocator_list_ui(); self._refresh_allocations_display_area()
            self._set_initial_plot_view_limits() # Uses fit_end_date_entry
            self.canvas.draw()
            self._on_global_update_button_click(is_auto_load_call=True) # Plot after load
            return True
        except Exception as e: # ... (same fallback as before)
            self.set_status(f"Critical error processing loaded state: {e}", error=True); import traceback; traceback.print_exc()
            messagebox.showerror("Load Error", f"Critical error processing state: {e}\nStarting fresh.", parent=self.root)
            self.current_instruments_set = set(); 
            for rd in self.instrument_gui_rows: rd['frame'].destroy()
            self.instrument_gui_rows.clear(); self.allocators_store.clear(); self._add_instrument_row_ui(); self._redraw_allocator_list_ui()
            return False

    def _update_allocator_selector_dropdown(self):
        # ... (Unchanged from previous response)
        allocator_names = sorted([data['instance'].name for data in self.allocators_store.values()])
        current_selection = self.allocator_selector_var.get()
        self.allocator_selector_combo['values'] = allocator_names
        if allocator_names: 
            if current_selection in allocator_names: self.allocator_selector_var.set(current_selection)
            else: self.allocator_selector_var.set(allocator_names[0])
        else: self.allocator_selector_var.set("") 

    def _refresh_allocations_display_area(self):
        # ... (Unchanged from previous response)
        self.allocations_text_widget.config(state=tk.NORMAL, background='white'); self.allocations_text_widget.delete("1.0", tk.END)
        selected_allocator_name = self.allocator_selector_var.get(); display_text = "No allocator selected or not found."
        found_data = None
        if selected_allocator_name:
            for data_dict in self.allocators_store.values(): 
                if data_dict['instance'].name == selected_allocator_name: found_data = data_dict; break
        if found_data:
            allocator = found_data['instance']; is_enabled = found_data['is_enabled_var'].get()
            allocs = allocator.allocations 
            status_text = "ENABLED" if is_enabled else "DISABLED"
            display_text = f"Allocator: '{allocator.name}' ({status_text})\nType: {type(allocator).__name__}\n"
            if isinstance(allocator, MarkovitsAllocator): display_text += f"Optimization: {allocator.optimization_target}\nAllows Shorting: {allocator._allow_shorting}\n"
            if allocs: 
                alloc_sum = sum(allocs.values())
                display_text += "\nLast Computed Allocations:\n" + "\n".join([f"  {inst}: {percent:.2%}" for inst, percent in sorted(allocs.items()) if abs(percent)>1e-9])
                if not (abs(alloc_sum - 1.0) < 1e-7 or (not any(abs(v)>1e-9 for v in allocs.values()) and abs(alloc_sum) < 1e-9)):
                    display_text += f"\n\nWARNING: Allocations sum to {alloc_sum*100:.2f}%."
                elif not any(abs(v)>1e-9 for v in allocs.values()): display_text += "\n(All allocations are zero)"
            else: 
                display_text += "\nNo allocations computed or set."
                if self.current_instruments_set and is_enabled: display_text += "\nConsider running 'FIT & PLOT'."
        elif not self.allocators_store: display_text = "No allocators created yet."
        self.allocations_text_widget.insert(tk.END, display_text)
        self.allocations_text_widget.config(state=tk.DISABLED, background=self.root.cget('bg'))

    def _setup_plot_axes_appearance(self):
        self.ax.clear() 
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("Cumulative Performance (%)")
        self.ax.set_title("Portfolio Performance (Out-of-Sample)") # Updated title
        self.ax.grid(True, linestyle=':', alpha=0.7)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=12, interval_multiples=True))
        self.ax.yaxis.set_major_formatter(mtick.PercentFormatter())

    def _set_initial_plot_view_limits(self):
        # Plot starts from Fit End Date
        try:
            start_dt_str = self.fit_end_date_entry.get() # Use Fit End Date as plot start
            start_dt = datetime.strptime(start_dt_str, "%Y-%m-%d").date()
            end_dt = date.today()
            if start_dt < end_dt: # Ensure plot start is before plot end (today)
                self.ax.set_xlim(start_dt, end_dt)
            else: # Fallback if fit_end_date is today or later
                self.ax.set_xlim(end_dt - timedelta(days=30), end_dt) # Show last 30 days
        except ValueError: 
            self.ax.set_xlim(date.today() - timedelta(days=30), date.today())

    def parse_date_entry(self, entry_widget: ttk.Entry, date_name: str) -> Optional[date]:
        # ... (Unchanged from previous response)
        date_str = entry_widget.get().strip()
        if not date_str: messagebox.showerror("Input Error", f"{date_name} cannot be empty.", parent=self.root); return None
        try: return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError: messagebox.showerror("Input Error", f"Invalid {date_name} (YYYY-MM-DD).", parent=self.root); return None

    def set_status(self, message: str, error: bool = False, success: bool = False):
        # ... (Unchanged from previous response)
        self.status_bar.config(text=message)
        if error: self.status_bar.config(foreground="white", background="#A62F03")
        elif success: self.status_bar.config(foreground="white", background="#027A48")
        else: self.status_bar.config(foreground="black", background=ttk.Style().lookup('TLabel', 'background'))

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style()
    if 'clam' in style.theme_names(): style.theme_use('clam')
    # ... (rest of styling unchanged from previous response)
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