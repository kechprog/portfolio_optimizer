import tkinter as tk
from tkinter import ttk, simpledialog
from datetime import date
import platform
import logging
import pandas as pd
from typing import Optional
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from portfolio import Portfolio

logger = logging.getLogger(__name__)


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


class DatePickerDialog(simpledialog.Dialog):
    def __init__(self, parent, title, initial_date=None):
        self.initial_date = initial_date or date.today()
        self.selected_date = self.initial_date
        self.result = None
        # Detect theme colors
        self._detect_theme_colors()
        super().__init__(parent, title)

    def _detect_theme_colors(self):
        """Detect current theme colors for the calendar"""
        # Check if we're in dark mode by looking at Windows theme
        is_dark = _is_dark_mode() if _is_windows() else False
        
        if is_dark:
            # Dark theme colors
            self.theme_colors = {
                'normal_bg': '#404040',
                'normal_fg': '#ffffff',
                'selected_bg': '#0078d4',
                'selected_fg': '#ffffff',
                'hover_bg': '#505050',
                'disabled_bg': '#2d2d2d',
                'disabled_fg': '#808080'
            }
        else:
            # Light theme colors
            self.theme_colors = {
                'normal_bg': '#f0f0f0',
                'normal_fg': '#000000',
                'selected_bg': '#0078d4',
                'selected_fg': '#ffffff',
                'hover_bg': '#e5e5e5',
                'disabled_bg': '#f5f5f5',
                'disabled_fg': '#a0a0a0'
            }

    def body(self, master):
        # Configure grid weights
        master.grid_columnconfigure(0, weight=1)
        
        # Calendar Frame
        calendar_frame = ttk.LabelFrame(master, text="Select Date", padding=15)
        calendar_frame.grid(row=0, column=0, sticky='nsew', pady=(0, 10))
        
        # Year and Month controls
        controls_frame = ttk.Frame(calendar_frame)
        controls_frame.grid(row=0, column=0, columnspan=7, sticky='ew', pady=(0, 10))
        
        self.year_var = tk.StringVar(value=str(self.initial_date.year))
        self.month_var = tk.StringVar(value=str(self.initial_date.month))
        
        ttk.Label(controls_frame, text="Year:").grid(row=0, column=0, sticky='w', padx=(0, 5))
        year_combo = ttk.Combobox(controls_frame, textvariable=self.year_var, 
                                 values=[str(y) for y in range(2000, 2030)], width=8, state='readonly')
        year_combo.grid(row=0, column=1, padx=(0, 20))
        year_combo.bind('<<ComboboxSelected>>', lambda e: self._update_calendar())
        
        ttk.Label(controls_frame, text="Month:").grid(row=0, column=2, sticky='w', padx=(0, 5))
        month_combo = ttk.Combobox(controls_frame, textvariable=self.month_var,
                                  values=[str(m) for m in range(1, 13)], width=8, state='readonly')
        month_combo.grid(row=0, column=3)
        month_combo.bind('<<ComboboxSelected>>', lambda e: self._update_calendar())
        
        # Days of week header
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for i, day in enumerate(days):
            label = ttk.Label(calendar_frame, text=day, font=("Helvetica", 9, "bold"), anchor='center')
            label.grid(row=1, column=i, sticky='ew', padx=2, pady=2)
        
        # Create day buttons storage
        self.day_buttons = {}
        
        # Create grid of day buttons (6 rows x 7 cols for full month coverage)
        for row in range(2, 8):
            for col in range(7):
                btn = tk.Button(calendar_frame, text="", width=4, height=2, font=("Helvetica", 9),
                               command=lambda r=row, c=col: self._on_day_click(r, c),
                               bg=self.theme_colors['disabled_bg'],
                               fg=self.theme_colors['disabled_fg'],
                               relief='flat',
                               borderwidth=1)
                btn.grid(row=row, column=col, padx=1, pady=1, sticky='ew')
                
                # Add hover effects
                btn.bind("<Enter>", lambda e, button=btn: self._on_button_hover(button, True))
                btn.bind("<Leave>", lambda e, button=btn: self._on_button_hover(button, False))
                
                self.day_buttons[f'{row},{col}'] = btn
        
        # Configure column weights for even distribution
        for i in range(7):
            calendar_frame.grid_columnconfigure(i, weight=1)
        
        # Initialize calendar
        self._update_calendar()
        
        return year_combo  # Return focus widget

    def _on_button_hover(self, button, is_entering):
        """Handle button hover effects"""
        if button.cget('state') == 'disabled':
            return
        
        # Don't change hover for selected button
        if button.cget('bg') == self.theme_colors['selected_bg']:
            return
            
        if is_entering:
            button.config(bg=self.theme_colors['hover_bg'])
        else:
            button.config(bg=self.theme_colors['normal_bg'])

    def _update_calendar(self):
        """Update calendar display for the current month/year"""
        import calendar
        
        year = int(self.year_var.get())
        month = int(self.month_var.get())
        
        # Clear all buttons first
        for btn in self.day_buttons.values():
            btn.config(text="", 
                      state='disabled', 
                      bg=self.theme_colors['disabled_bg'], 
                      fg=self.theme_colors['disabled_fg'],
                      relief='flat')
        
        # Get calendar data
        cal = calendar.monthcalendar(year, month)
        
        # Update buttons with days
        for week_num, week in enumerate(cal):
            row = week_num + 2  # Start from row 2 (after header)
            for day_num, day in enumerate(week):
                if day == 0:
                    continue
                
                btn = self.day_buttons[f'{row},{day_num}']
                btn.config(text=str(day), 
                          state='normal',
                          fg=self.theme_colors['normal_fg'])
                
                # Highlight selected date
                current_date = date(year, month, day)
                if current_date == self.selected_date:
                    btn.config(bg=self.theme_colors['selected_bg'], 
                              fg=self.theme_colors['selected_fg'],
                              relief='solid')
                else:
                    btn.config(bg=self.theme_colors['normal_bg'],
                              relief='raised')

    def _on_day_click(self, row, col):
        """Handle day button click"""
        btn = self.day_buttons[f'{row},{col}']
        day_text = btn.cget('text')
        
        if not day_text or day_text == "":
            return
        
        day = int(day_text)
        year = int(self.year_var.get())
        month = int(self.month_var.get())
        
        self.selected_date = date(year, month, day)
        self._update_calendar()

    def validate(self):
        """Validate the selected date"""
        return True  # Simple validation - any valid date is acceptable

    def apply(self):
        """Apply the selected date"""
        self.result = self.selected_date


class PortfolioInfo(ttk.Frame):
    def __init__(self, parent, portfolio: Optional[Portfolio] = None, all_portfolios=None, app_instance=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.portfolio = portfolio
        self.all_portfolios = all_portfolios or []  # List of all available portfolios
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
        
        # Centered date label (clickable)
        self.header_label = ttk.Label(header_frame, font=("Helvetica", 10, "bold"), anchor="center", cursor="hand2")
        self.header_label.grid(row=0, column=0, sticky="ew")
        self.header_label.bind("<Button-1>", self._on_date_header_click)
        self.header_label.bind("<Enter>", self._on_header_enter)
        self.header_label.bind("<Leave>", self._on_header_leave)
        
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

    def _on_date_header_click(self, event):
        """Handle click on the date header to open date picker"""
        if not self.portfolio or not self.portfolio.segments:
            return
        
        # Get current segment start date as initial selection
        current_segment = self.portfolio.segments[self.current_segment_index]
        start_date = current_segment.get('start_date')
        
        # Convert to date object if it's datetime object
        if hasattr(start_date, 'date'):
            start_date = start_date.date()
        
        # Show date picker dialog
        dialog = DatePickerDialog(
            self.master,
            "Select Date",
            initial_date=start_date
        )
        
        if dialog.result:
            selected_date = dialog.result
            self._navigate_to_date(selected_date)

    def _on_header_enter(self, event):
        """Handle mouse enter on header to show it's clickable"""
        if self.portfolio and self.portfolio.segments:
            # Change appearance to indicate it's clickable
            self.header_label.configure(foreground="blue")

    def _on_header_leave(self, event):
        """Handle mouse leave on header to restore normal appearance"""
        # Restore normal appearance
        self.header_label.configure(foreground="")

    def _navigate_to_date(self, target_date):
        """Navigate to the segment that contains the specified date"""
        if not self.portfolio or not self.portfolio.segments:
            return
        
        # Find the first segment that contains the target date
        for i, segment in enumerate(self.portfolio.segments):
            seg_start = segment.get('start_date')
            seg_end = segment.get('end_date')
            
            # Convert to date objects if needed
            if hasattr(seg_start, 'date'):
                seg_start = seg_start.date()
            if hasattr(seg_end, 'date'):
                seg_end = seg_end.date()
            
            # Check if target date is within this segment
            if seg_start and seg_end and seg_start <= target_date <= seg_end:
                # Found the segment containing the date
                if i != self.current_segment_index:
                    self.current_segment_index = i
                    self._update_display()
                    
                    # Provide feedback to user about navigation
                    if self.app_instance:
                        start_str = seg_start.strftime('%Y-%m-%d')
                        end_str = seg_end.strftime('%Y-%m-%d')
                        self.app_instance.set_status(
                            f"Navigated to segment containing {target_date.strftime('%Y-%m-%d')}: {start_str} to {end_str}", 
                            success=True
                        )
                else:
                    # Already viewing the segment containing this date
                    if self.app_instance:
                        self.app_instance.set_status(f"Already viewing segment containing {target_date.strftime('%Y-%m-%d')}")
                return
        
        # If no segment contains the date, inform the user
        if self.app_instance:
            self.app_instance.set_status(f"No segment contains the date {target_date.strftime('%Y-%m-%d')}", error=True)