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
import platform
import logging # Added logging
from typing import Optional, Set, Dict, Type, Any, List, Tuple

# Import the new AllocatorState along with PortfolioAllocator
from allocator.allocator import PortfolioAllocator, AllocatorState
from allocator.manual import ManualAllocator
# from allocator.markovits import MarkovitsAllocator # REMOVED
from allocator.mpt.max_sharpe import MaxSharpeAllocator # New import
from allocator.mpt.min_volatility import MinVolatilityAllocator # New import
from portfolio import Portfolio # Added import

from data_getter import av_fetcher # Changed to import av_fetcher directly

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

# Dialog for duplicating allocator with type drop-down and name entry
class DuplicateAllocatorDialog(simpledialog.Dialog):
    def __init__(self, parent, title, type_names, current_type, initial_name):
        self.type_names = type_names
        self.current_type = current_type
        self.initial_name = initial_name
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Allocator Type:").grid(row=0, column=0, sticky='w')
        self.type_var = tk.StringVar(value=self.current_type)
        self.type_combo = ttk.Combobox(master, textvariable=self.type_var, values=self.type_names, state='readonly')
        self.type_combo.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(master, text="Name:").grid(row=1, column=0, sticky='w')
        self.name_var = tk.StringVar(value=self.initial_name)
        self.name_entry = ttk.Entry(master, textvariable=self.name_var)
        self.name_entry.grid(row=1, column=1, padx=5, pady=5)
        return self.name_entry

    def apply(self):
        self.result = (self.type_var.get(), self.name_var.get())


class PortfolioInfo(ttk.Frame):
    def __init__(self, parent, portfolio: Optional[Portfolio] = None, app_instance=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.portfolio = portfolio
        self.current_segment_index = 0
        self.app_instance = app_instance  # Reference to app for status updates

        if not portfolio:
            self._create_empty_view()
        else:
            self._create_portfolio_view()

    def _create_empty_view(self):
        empty_label = ttk.Label(self, text="Select Allocator", font=("Helvetica", 12, 'italic'))
        empty_label.pack(expand=True)

    def _create_portfolio_view(self):
        # Main container with vertical layout
        main_container = ttk.Frame(self)
        main_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Header frame with date info and checkbox
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill="x", pady=(0, 10))
        
        # Configure header frame columns
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)
        
        # Centered date label
        self.header_label = ttk.Label(header_frame, font=("Helvetica", 10, "bold"), anchor="center")
        self.header_label.grid(row=0, column=0, sticky="ew")
        
        # Show graph checkbox (right side)
        self.show_graph_var = tk.BooleanVar(value=False)
        self.show_graph_checkbox = ttk.Checkbutton(header_frame, 
                                                  text="Show graph", 
                                                  variable=self.show_graph_var,
                                                  command=self._on_show_graph_changed)
        self.show_graph_checkbox.grid(row=0, column=1, sticky="e", padx=(10, 0))
        
        # Content frame that will hold either table or graph
        self.content_frame = ttk.Frame(main_container)
        self.content_frame.pack(fill="both", expand=True)
        
        # Initialize sorting state
        self.sort_column = "Allocation"  # Default sort by allocation
        self.sort_reverse = True  # Default to highest first
        
        # Create table view components (initially visible)
        self._create_table_view()
        
        # Create graph view components (initially hidden)
        self._create_graph_view()
        
        # Show table view by default
        self.table_frame.pack(fill="both", expand=True)
        
        # Initialize display
        self._update_display()
    
    def _create_table_view(self):
        """Create the table view components with navigation"""
        # Table frame with scrollable content and navigation
        self.table_frame = ttk.Frame(self.content_frame)
        
        # Table area (top part of table frame)
        table_area = ttk.Frame(self.table_frame)
        table_area.pack(fill="both", expand=True, pady=(0, 10))
        
        # Create Treeview for the table
        columns = ("Instrument", "Allocation")
        self.tree = ttk.Treeview(table_area, columns=columns, show="headings", height=8)
        
        # Configure columns with sorting
        self.tree.heading("Instrument", text="Instrument", 
                         command=lambda: self._sort_column("Instrument"))
        self.tree.heading("Allocation", text="Allocation (%) ↓", 
                         command=lambda: self._sort_column("Allocation"))
        self.tree.column("Instrument", width=120, anchor="w")
        self.tree.column("Allocation", width=100, anchor="e")
        
        # Configure grid lines and alternating row colors
        style = ttk.Style()
        
        # Configure the treeview to show grid lines
        style.configure("Treeview", 
                       borderwidth=1,
                       relief="solid")
        style.configure("Treeview.Heading",
                       borderwidth=1,
                       relief="solid")
        
        # Configure alternating row colors based on theme
        self._configure_table_row_colors()
        
        # Add scrollbar to table
        self.table_scrollbar = ttk.Scrollbar(table_area, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.table_scrollbar.set)
        
        # Pack table and scrollbar
        self.tree.pack(side="left", fill="both", expand=True)
        self.table_scrollbar.pack(side="right", fill="y")
    
    def _configure_table_row_colors(self):
        """Configure table row colors based on current theme"""
        if self.app_instance and hasattr(self.app_instance, 'is_dark_mode'):
            is_dark = self.app_instance.is_dark_mode
            
            if is_dark:
                # Dark theme row colors
                self.tree.tag_configure('evenrow', 
                                      background='#3c3c3c', 
                                      foreground='#ffffff')
                self.tree.tag_configure('oddrow', 
                                      background='#2d2d2d', 
                                      foreground='#ffffff')
            else:
                # Light theme row colors
                self.tree.tag_configure('evenrow', 
                                      background='#f0f0f0', 
                                      foreground='#000000')
                self.tree.tag_configure('oddrow', 
                                      background='#ffffff', 
                                      foreground='#000000')
        else:
            # Fallback colors (light theme)
            self.tree.tag_configure('evenrow', background='#f0f0f0')
            self.tree.tag_configure('oddrow', background='white')
        
        # Navigation controls (bottom part of table frame)
        nav_frame = ttk.Frame(self.table_frame)
        nav_frame.pack(fill="x")
        
        # Center the navigation controls
        nav_center_frame = ttk.Frame(nav_frame)
        nav_center_frame.pack(anchor="center")
        
        # Left arrow button
        self.prev_button = ttk.Button(nav_center_frame, text="◀", width=3, 
                                     command=self._prev_segment, state="normal")
        self.prev_button.pack(side="left", padx=2)
        
        # Copy button
        self.copy_button = ttk.Button(nav_center_frame, text="📋", width=3,
                                     command=self._copy_to_clipboard)
        self.copy_button.pack(side="left", padx=2)
        
        # Right arrow button  
        self.next_button = ttk.Button(nav_center_frame, text="▶", width=3,
                                     command=self._next_segment, state="normal")
        self.next_button.pack(side="left", padx=2)
    
    def _create_graph_view(self):
        """Create the graph view components"""
        self.graph_frame = ttk.Frame(self.content_frame)
        
        # Create matplotlib figure and canvas for the distribution plot
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        
        self.dist_fig = Figure(figsize=(6, 4), dpi=80)
        self.dist_ax = self.dist_fig.add_subplot(111)
        self.dist_canvas = FigureCanvasTkAgg(self.dist_fig, master=self.graph_frame)
        self.dist_canvas_widget = self.dist_canvas.get_tk_widget()
        self.dist_canvas_widget.pack(fill=tk.BOTH, expand=True)
        
        # Style the plot with theme colors
        self._apply_graph_theme_styling()
    
    def _apply_graph_theme_styling(self):
        """Apply theme-appropriate styling to the distribution graph"""
        if self.app_instance and hasattr(self.app_instance, 'is_dark_mode'):
            is_dark = self.app_instance.is_dark_mode
            
            if is_dark:
                # Dark theme styling
                self.dist_fig.patch.set_facecolor('#1e1e1e')
                self.dist_ax.set_facecolor('#2b2b2b')
                self.dist_ax.tick_params(colors='#ffffff')
                self.dist_ax.set_ylabel("Allocation (%)", color='#ffffff')
                self.dist_ax.set_title("Portfolio Distribution", color='#ffffff')
                self.dist_ax.grid(True, linestyle=':', alpha=0.3, color='#606060')
            else:
                # Light theme styling
                self.dist_fig.patch.set_facecolor('#ffffff')
                self.dist_ax.set_facecolor('#ffffff')
                self.dist_ax.tick_params(colors='#000000')
                self.dist_ax.set_ylabel("Allocation (%)", color='#000000')
                self.dist_ax.set_title("Portfolio Distribution", color='#000000')
                self.dist_ax.grid(True, linestyle=':', alpha=0.7, color='#cccccc')
        else:
            # Fallback styling
            self.dist_ax.set_ylabel("Allocation (%)")
            self.dist_ax.set_title("Portfolio Distribution")
            self.dist_ax.grid(True, linestyle=':', alpha=0.7)
    
    def _on_show_graph_changed(self):
        """Handle the show graph checkbox change"""
        if self.show_graph_var.get():
            # Show graph view (navigation buttons are automatically hidden with table)
            self.table_frame.pack_forget()
            self.graph_frame.pack(fill="both", expand=True)
            self._update_graph_display()
        else:
            # Show table view (navigation buttons are automatically shown with table)
            self.graph_frame.pack_forget()
            self.table_frame.pack(fill="both", expand=True)
            self._update_table_display()

    def _update_display(self):
        """Update the display with current segment data"""
        if not self.portfolio or not self.portfolio.segments:
            self.header_label.config(text="No portfolio segments available")
            # Clear both views
            self._clear_table_data()
            self._clear_graph_data()
            self._update_button_states()
            return
        
        # Update the appropriate view based on checkbox state
        if self.show_graph_var.get():
            self._update_graph_display()
        else:
            # Get current segment for table view
            current_segment = self.portfolio.segments[self.current_segment_index]
            
            # Update header with date range for table view
            start_date = current_segment.get('start_date', 'Unknown')
            end_date = current_segment.get('end_date', 'Unknown')
            
            if hasattr(start_date, 'strftime'):
                start_str = start_date.strftime('%Y-%m-%d')
            else:
                start_str = str(start_date)
                
            if hasattr(end_date, 'strftime'):
                end_str = end_date.strftime('%Y-%m-%d')
            else:
                end_str = str(end_date)
            
            self.header_label.config(text=f"From {start_str} to {end_str}")
            self._update_table_display()
        
        # Update button states
        self._update_button_states()
    
    def _update_table_display(self):
        """Update the table view with current segment data"""
        if not self.portfolio or not self.portfolio.segments:
            return
        
        # Clear existing table data
        self._clear_table_data()
        
        # Get current segment
        current_segment = self.portfolio.segments[self.current_segment_index]
        
        # Get allocations and populate table
        allocations = current_segment.get('allocations', {})
        
        # Filter out zero allocations
        significant_allocations = [(k, v) for k, v in allocations.items() if abs(v) > 1e-9]
        
        # Sort according to current sort settings
        self._sort_data(significant_allocations)
        
        # If no significant allocations, show a message
        if not significant_allocations:
            self.tree.insert("", "end", values=("No significant allocations", ""))
    
    def _update_graph_display(self):
        """Update the graph view with portfolio distribution progression"""
        if not self.portfolio or not self.portfolio.segments:
            self._clear_graph_data()
            return
        
        try:
            # Get test end date from app instance
            test_end_date = None
            if self.app_instance:
                test_end_date = self.app_instance.parse_date_entry(
                    self.app_instance.test_end_date_entry, "Test End", silent=True
                )
            
            if not test_end_date:
                # Fallback to last segment end date
                test_end_date = self.portfolio.segments[-1].get('end_date')
            
            # Clear the previous plot
            self.dist_ax.clear()
            
            # Plot the distribution progression up to test_end_date
            self.portfolio.plot_distribution(self.dist_ax, test_end_date)
            
            # Apply theme styling after plotting
            self._apply_graph_theme_styling()
            
            # Update header for graph view
            portfolio_start_date = self.portfolio.segments[0].get('start_date')
            if hasattr(portfolio_start_date, 'strftime') and hasattr(test_end_date, 'strftime'):
                start_str = portfolio_start_date.strftime('%Y-%m-%d')
                end_str = test_end_date.strftime('%Y-%m-%d')
                self.header_label.config(text=f"Portfolio Distribution: {start_str} to {end_str}")
            else:
                self.header_label.config(text="Portfolio Distribution")
            
            # Update the plot title with theme-appropriate color
            self.dist_ax.set_title("Portfolio Allocation Progression", fontsize=10)
            self.dist_fig.tight_layout()
            self.dist_canvas.draw()
            
        except Exception as e:
            # Handle any errors in graph generation
            self.dist_ax.clear()
            self._apply_graph_theme_styling()
            
            # Apply theme colors to error text
            text_color = '#ffffff' if (self.app_instance and hasattr(self.app_instance, 'is_dark_mode') and self.app_instance.is_dark_mode) else '#000000'
            self.dist_ax.text(0.5, 0.5, f"Error generating graph:\n{str(e)}", 
                             ha='center', va='center', transform=self.dist_ax.transAxes, 
                             fontsize=10, wrap=True, color=text_color)
            self.dist_canvas.draw()
            
            # Update header to show error state
            self.header_label.config(text="Error displaying portfolio distribution")
    
    def _clear_table_data(self):
        """Clear all data from the table"""
        for item in self.tree.get_children():
            self.tree.delete(item)
    
    def _clear_graph_data(self):
        """Clear the graph display"""
        self.dist_ax.clear()
        self._apply_graph_theme_styling()
        self.dist_ax.text(0.5, 0.5, "No data to display", 
                         ha='center', va='center', transform=self.dist_ax.transAxes, 
                         fontsize=12, style='italic')
        self.dist_canvas.draw()

    def _update_button_states(self):
        """Update navigation button states based on current position"""
        if not self.portfolio or not self.portfolio.segments:
            self.prev_button.config(state="disabled")
            self.next_button.config(state="disabled")
            self.copy_button.config(state="disabled")
            return
        
        total_segments = len(self.portfolio.segments)
        
        # Previous button
        if self.current_segment_index <= 0:
            self.prev_button.config(state="disabled")
        else:
            self.prev_button.config(state="normal")
        
        # Next button
        if self.current_segment_index >= total_segments - 1:
            self.next_button.config(state="disabled")
        else:
            self.next_button.config(state="normal")
        
        # Copy button (always enabled if we have segments)
        self.copy_button.config(state="normal")

    def _prev_segment(self):
        """Navigate to previous segment"""
        if self.portfolio and self.portfolio.segments and self.current_segment_index > 0:
            self.current_segment_index -= 1
            self._update_display()

    def _next_segment(self):
        """Navigate to next segment"""
        if (self.portfolio and self.portfolio.segments and 
            self.current_segment_index < len(self.portfolio.segments) - 1):
            self.current_segment_index += 1
            self._update_display()

    def _copy_to_clipboard(self):
        """Copy the current table data to clipboard as DataFrame"""
        if not self.portfolio or not self.portfolio.segments:
            return
        
        try:
            # Get current segment data
            current_segment = self.portfolio.segments[self.current_segment_index]
            allocations = current_segment.get('allocations', {})
            
            # Get all instruments with non-zero allocations
            instruments = []
            allocation_values = []
            
            for instrument, allocation in allocations.items():
                if abs(allocation) > 1e-9:  # Only include non-zero allocations
                    instruments.append(instrument)
                    allocation_values.append(allocation)
            
            # Create DataFrame
            df = pd.DataFrame({
                'Instrument': instruments,
                'Allocation': allocation_values
            })
            
            # Sort by allocation (descending)
            df = df.sort_values('Allocation', ascending=False, key=abs)
            
            # Copy to clipboard
            df.to_clipboard(index=False)
            
            # Update status using app instance if available
            if self.app_instance:
                self.app_instance.set_status("Table copied to clipboard", success=True)
            else:
                print("Table copied to clipboard")
                
        except Exception as e:
            error_msg = f"Error copying to clipboard: {e}"
            if self.app_instance:
                self.app_instance.set_status(error_msg, error=True)
            else:
                print(error_msg)

    def _sort_column(self, column):
        """Handle column header clicks for sorting (only works in table view)"""
        # Only sort if we're in table view
        if self.show_graph_var.get():
            return
            
        if self.sort_column == column:
            # Same column clicked, toggle sort order
            self.sort_reverse = not self.sort_reverse
        else:
            # New column clicked
            self.sort_column = column
            if column == "Instrument":
                self.sort_reverse = False  # Default to A-Z for instruments
            else:  # Allocation
                self.sort_reverse = True   # Default to highest first for allocations
        
        # Update column headers with sort indicators
        self._update_column_headers()
        
        # Re-display the current data with new sort (table only)
        self._update_table_display()
    
    def _update_column_headers(self):
        """Update column headers with sort indicators"""
        instrument_text = "Instrument"
        allocation_text = "Allocation (%)"
        
        if self.sort_column == "Instrument":
            if self.sort_reverse:
                instrument_text += " ↑"  # Z-A (reverse alphabetical)
            else:
                instrument_text += " ↓"  # A-Z (normal alphabetical)
            # allocation_text stays as "Allocation (%)" with no arrows
        else:  # Allocation
            if self.sort_reverse:
                allocation_text += " ↓"  # Highest first
            else:
                allocation_text += " ↑"  # Lowest first
            # instrument_text stays as "Instrument" with no arrows
        
        self.tree.heading("Instrument", text=instrument_text)
        self.tree.heading("Allocation", text=allocation_text)
    
    def _sort_data(self, allocations_list):
        """Sort and populate the table with data"""
        if not allocations_list:
            return
        
        if self.sort_column == "Instrument":
            # Sort by instrument name (alphabetical)
            sorted_data = sorted(allocations_list, key=lambda x: x[0].lower(), reverse=self.sort_reverse)
        else:  # Sort by allocation
            # Sort by allocation value (by absolute value for proper comparison)
            sorted_data = sorted(allocations_list, key=lambda x: abs(x[1]), reverse=self.sort_reverse)
        
        # Add rows to table with alternating colors
        for idx, (instrument, allocation) in enumerate(sorted_data):
            percentage = allocation * 100  # Convert to percentage
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            self.tree.insert("", "end", values=(instrument, f"{percentage:.2f}%"), tags=(tag,))

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

        # self.current_instruments_set: Set[str] = set() # REMOVED - managed per allocator

        # Stores allocator instances and their UI elements (like is_enabled_var)
        # Key: allocator_id (str), Value: Dict {'instance': PortfolioAllocator, 'is_enabled_var': tk.BooleanVar}
        self.allocators_store: Dict[str, Dict[str, Any]] = {}
        
        self.available_allocator_types: Dict[str, Type[PortfolioAllocator]] = {
            "Manual Allocator": ManualAllocator,
            "Max Sharpe": MaxSharpeAllocator,
            "Min Volatility": MinVolatilityAllocator,
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

            # New duplicate button
            duplicate_btn = ttk.Button(row_frame, text="⧉", width=3, style="Toolbutton.TButton",
                                       command=lambda aid=allocator_id: self._on_duplicate_allocator_prompt(aid))
            duplicate_btn.pack(side="left", padx=2)

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

    def _on_duplicate_allocator_prompt(self, allocator_id_to_duplicate: str):
        """
        Prompt with a drop-down to select allocator type and an entry to specify the new name.
        """
        data = self.allocators_store.get(allocator_id_to_duplicate)
        if not data:
            messagebox.showerror("Duplicate Error", "Allocator not found for duplication.", parent=self.root)
            return

        original_instance = data['instance']
        original_state = original_instance.get_state()

        # Determine current allocator type name
        current_type = None
        for type_name, cls in self.available_allocator_types.items():
            if isinstance(original_instance, cls):
                current_type = type_name
                break
        type_names = list(self.available_allocator_types.keys())
        initial_name = original_state.get('name', '') + " (copy)"

        # Show dialog
        dialog = DuplicateAllocatorDialog(
            self.root,
            "Duplicate Allocator",
            type_names,
            current_type,
            initial_name
        )
        if not dialog.result:
            self.set_status("Allocator duplication cancelled.")
            return
        chosen_type, new_name = dialog.result

        new_state = dict(original_state)
        new_state['name'] = new_name
        try:
            AllocatorClass = self.available_allocator_types[chosen_type]
            new_instance = AllocatorClass(**new_state)
        except Exception as e:
            messagebox.showerror("Duplicate Error", f"Failed to duplicate allocator: {e}", parent=self.root)
            return

        new_alloc_id = str(uuid.uuid4())
        self.allocators_store[new_alloc_id] = {
            'instance': new_instance,
            'is_enabled_var': tk.BooleanVar(value=True)
        }
        self.set_status(f"Allocator '{new_name}' duplicated as {chosen_type}.", success=True)
        self._redraw_allocator_list_ui()
        self._refresh_allocations_display_area()

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
            self._refresh_allocations_display_area()
            return
        
        enabled_allocators_data = []
        any_allocator_failed_computation = False
        for aid, data in self.allocators_store.items():
            if data['is_enabled_var'].get():
                allocator = data['instance']
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
             self.fig.tight_layout(); self.canvas.draw(); self._refresh_allocations_display_area()
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
            "allocators": [],
            "plot_dividends": self.plot_dividends_var.get(),
            "window_geometry": self.root.geometry(),
            "pane_positions": pane_positions
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
        # Destroy the old PortfolioInfo widget
        if hasattr(self, 'portfolio_info_widget') and self.portfolio_info_widget.winfo_exists():
            self.portfolio_info_widget.destroy()

        selected_allocator_name = self.allocator_selector_var.get()
        found_allocator_data = None
        
        if selected_allocator_name:
            for data_dict in self.allocators_store.values():
                if data_dict['instance'].get_name() == selected_allocator_name:
                    found_allocator_data = data_dict
                    break
        
        portfolio_to_display = None
        if found_allocator_data:
            allocator = found_allocator_data['instance']
            portfolio_to_display = getattr(allocator, '_last_computed_portfolio', None)

        # Create a new PortfolioInfo widget
        self.portfolio_info_widget = PortfolioInfo(
            self.allocator_details_frame, 
            portfolio=portfolio_to_display,
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
