# app.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, date, timedelta
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
import uuid
from typing import Optional, Set

# Assuming allocator.py is in the same directory or accessible
from allocator.allocator import PortfolioAllocator
from allocator.manual import ManualAllocator # PAL TypeVar not needed here
GEAR_ICON = "\u2699"  # Gear emoji ⚙
DELETE_ICON = "\u2716" # Heavy Multiplication X ✖ (or use \u274C for red X ❌)

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Portfolio Allocation Tool")
        self.root.geometry("1200x800") # Adjusted size for new layout

        # --- Data Stores ---
        self.current_instruments_set: Set[str] = set()
        # Stores allocator instances. Key: unique_id, Value: {'instance': PortfolioAllocator, 'is_enabled_var': tk.BooleanVar}
        self.allocators_store: Dict[str, Dict[str, any]] = {}
        # Available allocator types for creation
        self.available_allocator_types: Dict[str, Type[PortfolioAllocator]] = {
            "Manual Allocator": ManualAllocator,
            # Add other allocator types here, e.g., "Equal Weight": EqualWeightAllocator
        }

        # --- UI Setup ---
        self._create_widgets() # This will now correctly order widget creation and dependent calls
        self._update_allocator_selector_dropdown() # Initial population
        self._refresh_allocations_display_area() # Show initial state

        # Add a default instrument row to start
        self._add_instrument_row_ui()


    def _create_widgets(self):
        # --- Main Paned Window (Top/Bottom) ---
        main_v_pane = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_v_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Top Frame (Plot and Allocations/Update) ---
        top_frame_outer = ttk.Frame(main_v_pane)
        main_v_pane.add(top_frame_outer, weight=3)

        top_h_pane = ttk.PanedWindow(top_frame_outer, orient=tk.HORIZONTAL)
        top_h_pane.pack(fill=tk.BOTH, expand=True)

        # Top-Left: Plot Area (Define canvas and ax first)
        self.plot_frame_tl = ttk.LabelFrame(top_h_pane, text="Portfolio Performance", padding=5)
        top_h_pane.add(self.plot_frame_tl, weight=2)

        self.fig = Figure(figsize=(7, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame_tl)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)
        # Plot setup calls (like _setup_plot_axes_appearance, _set_initial_plot_view_limits)
        # will be moved to after all dependent widgets (like date entries) are created.

        # Top-Right: Update Button, Allocator Selector, Allocation Details
        self.top_right_controls_frame = ttk.Frame(top_h_pane, padding=5)
        top_h_pane.add(self.top_right_controls_frame, weight=1)

        self.global_update_button = ttk.Button(self.top_right_controls_frame, text="UPDATE & PLOT ALL", command=self._on_global_update_button_click, style="Accent.TButton")
        self.global_update_button.pack(pady=(0,10), fill="x", ipady=5)
        
        # Date Configuration
        date_config_frame = ttk.Frame(self.top_right_controls_frame)
        date_config_frame.pack(fill="x", pady=(0,10))
        ttk.Label(date_config_frame, text="Hist. Start:").grid(row=0, column=0, sticky="w", padx=(0,2))
        self.hist_start_date_entry = ttk.Entry(date_config_frame, width=12) # Defined HERE
        self.hist_start_date_entry.grid(row=0, column=1, sticky="ew", padx=(0,5))
        self.hist_start_date_entry.insert(0, (date.today() - timedelta(days=365)).strftime("%Y-%m-%d"))
        
        ttk.Label(date_config_frame, text="Plot Start:").grid(row=0, column=2, sticky="w", padx=(5,2))
        self.plot_start_date_entry = ttk.Entry(date_config_frame, width=12) # Defined HERE
        self.plot_start_date_entry.grid(row=0, column=3, sticky="ew")
        self.plot_start_date_entry.insert(0, date.today().strftime("%Y-%m-%d"))
        date_config_frame.grid_columnconfigure(1, weight=1)
        date_config_frame.grid_columnconfigure(3, weight=1)

        alloc_display_outer_frame = ttk.LabelFrame(self.top_right_controls_frame, text="Selected Allocator Details", padding=5)
        alloc_display_outer_frame.pack(fill="both", expand=True)

        ttk.Label(alloc_display_outer_frame, text="View Allocator:").pack(side="top", anchor="w", padx=2, pady=(0,2))
        self.allocator_selector_var = tk.StringVar()
        self.allocator_selector_combo = ttk.Combobox(alloc_display_outer_frame, textvariable=self.allocator_selector_var, state="readonly", width=30)
        self.allocator_selector_combo.pack(side="top", fill="x", pady=(0,5), padx=2)
        self.allocator_selector_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_allocations_display_area())

        self.allocations_text_widget = tk.Text(alloc_display_outer_frame, height=8, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1)
        self.allocations_text_scrollbar = ttk.Scrollbar(alloc_display_outer_frame, command=self.allocations_text_widget.yview)
        self.allocations_text_widget.configure(yscrollcommand=self.allocations_text_scrollbar.set)
        self.allocations_text_scrollbar.pack(side="right", fill="y")
        self.allocations_text_widget.pack(side="left", fill="both", expand=True)
        self.allocations_text_widget.insert(tk.END, "Select an allocator to view its details.")
        self.allocations_text_widget.config(state=tk.DISABLED, background=self.root.cget('bg'))

        # --- Bottom Frame (Instruments and Allocators) ---
        bottom_frame_outer = ttk.Frame(main_v_pane)
        main_v_pane.add(bottom_frame_outer, weight=2)

        bottom_h_pane = ttk.PanedWindow(bottom_frame_outer, orient=tk.HORIZONTAL)
        bottom_h_pane.pack(fill=tk.BOTH, expand=True)

        # Bottom-Left: Instrument Management
        self.instrument_mgmt_frame = ttk.LabelFrame(bottom_h_pane, text="Instrument Setup", padding=5)
        bottom_h_pane.add(self.instrument_mgmt_frame, weight=1)
        self._create_instrument_management_ui()

        # Bottom-Right: Allocator Management
        self.allocator_mgmt_frame = ttk.LabelFrame(bottom_h_pane, text="Allocator Setup", padding=5)
        bottom_h_pane.add(self.allocator_mgmt_frame, weight=1)
        self._create_allocator_management_ui()

        # --- Final Plot Setup (after all relevant widgets like date entries are created) ---
        self._setup_plot_axes_appearance() # Configure plot style
        self._set_initial_plot_view_limits() # Now self.hist_start_date_entry exists
        self.fig.tight_layout()
        self.canvas.draw()

        # Status Bar (at the very bottom of the root window)
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=0, pady=0)

    # --- Instrument Management UI & Logic ---
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
        self.instrument_gui_rows = [] # Stores dicts of {'frame': frame, 'entry': entry_widget}

    def _add_instrument_row_ui(self):
        row_frame = ttk.Frame(self.instruments_list_scrollframe)
        row_frame.pack(fill="x", pady=1)
        
        entry = ttk.Entry(row_frame, width=20)
        entry.pack(side="left", padx=(0,5), fill="x", expand=True)
        entry.bind("<FocusOut>", lambda e, current_entry=entry: self._validate_single_instrument_entry_for_duplicates(current_entry))
        
        del_btn = ttk.Button(row_frame, text=DELETE_ICON, width=3, style="Danger.TButton",
                             command=lambda rf=row_frame: self._delete_instrument_row_ui(rf))
        del_btn.pack(side="left", padx=(0,2))
        self.instrument_gui_rows.append({'frame': row_frame, 'entry': entry})
        self.instruments_list_scrollframe.update_idletasks() # Ensure scrollregion updates
        self.instruments_canvas.configure(scrollregion=self.instruments_canvas.bbox("all"))
        entry.focus_set()

    def _delete_instrument_row_ui(self, row_frame_to_delete: ttk.Frame):
        for i, row_data in enumerate(self.instrument_gui_rows):
            if row_data['frame'] == row_frame_to_delete:
                row_data['frame'].destroy()
                del self.instrument_gui_rows[i]
                self.set_status("Instrument row removed. Click 'UPDATE' to apply changes to allocators.")
                # Re-validate all remaining entries for duplicates
                for r_data in self.instrument_gui_rows:
                    self._validate_single_instrument_entry_for_duplicates(r_data['entry'])
                self.instruments_list_scrollframe.update_idletasks()
                self.instruments_canvas.configure(scrollregion=self.instruments_canvas.bbox("all"))
                return

    def _validate_single_instrument_entry_for_duplicates(self, current_entry: ttk.Entry):
        if not current_entry.winfo_exists(): return True # Consider it valid if destroyed
        current_value = current_entry.get().strip()
        is_duplicate = False
        if current_value: # Only check non-empty entries for duplicates
            for row_data in self.instrument_gui_rows:
                entry_widget = row_data['entry']
                if entry_widget.winfo_exists() and entry_widget != current_entry and entry_widget.get().strip() == current_value:
                    is_duplicate = True
                    break
        current_entry.configure(style="Error.TEntry" if is_duplicate else "TEntry")
        return not is_duplicate # True if valid (not duplicate or empty)

    def _collect_and_validate_instruments(self) -> Optional[Set[str]]:
        instruments = set()
        all_entries_valid_individually = True # Tracks if any entry itself is marked as duplicate
        
        for row_data in self.instrument_gui_rows:
            entry = row_data['entry']
            if not entry.winfo_exists(): continue
            
            # Validate and style this specific entry based on current GUI state
            if not self._validate_single_instrument_entry_for_duplicates(entry):
                if entry.get().strip(): # If it's non-empty and a duplicate
                    all_entries_valid_individually = False
            
            val = entry.get().strip()
            if val: # Only add non-empty values to the set to be returned
                instruments.add(val)

        if not all_entries_valid_individually:
            messagebox.showerror("Input Error", "Duplicate instrument names found (marked red). Please correct them.", parent=self.root)
            return None # Indicates an error due to duplicates shown in UI
        
        self.current_instruments_set = instruments # Update the app's central store
        return instruments


    # --- Allocator Management UI & Logic ---
    def _create_allocator_management_ui(self):
        top_bar = ttk.Frame(self.allocator_mgmt_frame)
        top_bar.pack(fill="x", pady=(0,5))
        ttk.Label(top_bar, text="Allocator Type:").pack(side="left", padx=(0,5))
        self.new_allocator_type_var = tk.StringVar()
        self.new_allocator_type_combo = ttk.Combobox(top_bar, textvariable=self.new_allocator_type_var,
                                                     values=list(self.available_allocator_types.keys()), state="readonly", width=20)
        if self.available_allocator_types:
            self.new_allocator_type_combo.current(0)
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

    def _redraw_allocator_list_ui(self):
        for widget in self.allocators_list_scrollframe.winfo_children():
            widget.destroy()

        sorted_allocator_items = sorted(self.allocators_store.items(), key=lambda item: item[1]['instance'].name.lower())

        for allocator_id, data in sorted_allocator_items: # Iterate sorted by name
            allocator_instance = data['instance']
            is_enabled_var = data['is_enabled_var']

            row_frame = ttk.Frame(self.allocators_list_scrollframe)
            row_frame.pack(fill="x", pady=2, padx=2)

            chk = ttk.Checkbutton(row_frame, variable=is_enabled_var, text="")
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
            parent_window=self.root,
            current_instruments=current_instruments, # Pass empty set if no instruments
            existing_allocator=None
        )

        if new_allocator_instance:
            new_name_lower = new_allocator_instance.name.lower()
            for data in self.allocators_store.values():
                if data['instance'].name.lower() == new_name_lower:
                    messagebox.showerror("Create Allocator", f"An allocator with the name '{new_allocator_instance.name}' already exists. Please choose a unique name.", parent=self.root)
                    return

            allocator_id = str(uuid.uuid4())
            self.allocators_store[allocator_id] = {
                'instance': new_allocator_instance,
                'is_enabled_var': tk.BooleanVar(value=True)
            }
            self.set_status(f"Allocator '{new_allocator_instance.name}' created successfully.", success=True)
            self._redraw_allocator_list_ui()
        else:
            self.set_status(f"Allocator creation cancelled for type '{allocator_type_name}'.")


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
            current_instruments=current_instruments, # Pass empty set if no instruments
            existing_allocator=existing_instance
        )

        if reconfigured_instance:
            new_name_lower = reconfigured_instance.name.lower()
            for aid, data in self.allocators_store.items():
                if aid != allocator_id_to_configure and data['instance'].name.lower() == new_name_lower:
                    messagebox.showerror("Configure Allocator", f"An allocator with the name '{reconfigured_instance.name}' already exists. Please choose a unique name.", parent=self.root)
                    return
            
            self.allocators_store[allocator_id_to_configure]['instance'] = reconfigured_instance
            self.set_status(f"Allocator '{reconfigured_instance.name}' reconfigured successfully.", success=True)
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
                self._refresh_allocations_display_area()
        else:
            messagebox.showerror("Error", "Allocator not found for deletion.", parent=self.root)


    # --- Global Update & Plotting ---
    def _on_global_update_button_click(self):
        self.set_status("Processing global update...")

        current_instruments = self._collect_and_validate_instruments()
        if current_instruments is None:
            self.set_status("Update failed: Please fix instrument errors.", error=True)
            return
        # self.current_instruments_set is updated by _collect_and_validate_instruments

        for aid, data in self.allocators_store.items():
            try:
                data['instance'].on_instruments_changed(self.current_instruments_set)
            except Exception as e:
                print(f"Error in on_instruments_changed for {data['instance'].name}: {e}")
                self.set_status(f"Error updating {data['instance'].name} with instruments: {e}", error=True)

        hist_start_date_for_view = self.parse_date_entry(self.hist_start_date_entry, "Historical Start Date")
        if not hist_start_date_for_view: return
        
        plot_start_date_for_data = self.parse_date_entry(self.plot_start_date_entry, "Plot Start Date")
        if not plot_start_date_for_data: return

        if hist_start_date_for_view > plot_start_date_for_data:
            messagebox.showerror("Date Error", "Historical Start Date (for view) cannot be after Plot Start Date (for data).", parent=self.root)
            return
        
        plot_actual_end_date = date.today()

        self.ax.clear()
        self._setup_plot_axes_appearance()
        self.ax.set_xlim(hist_start_date_for_view, plot_actual_end_date)

        plots_drawn_count = 0
        enabled_allocators_for_plot = []
        for aid, data in self.allocators_store.items():
            if data['is_enabled_var'].get():
                allocator = data['instance']
                try:
                    allocator.prepare_plot_data(plot_start_date_for_data, plot_actual_end_date)
                    allocator.draw_plot(self.ax)
                    # A more robust check for whether draw_plot actually added lines/patches
                    # could be to check len(self.ax.lines) before and after, but this is simpler for now.
                    if any(line.get_label() and allocator.name in line.get_label() for line in self.ax.lines):
                         plots_drawn_count +=1 # Count if a line with its name was added
                    enabled_allocators_for_plot.append(allocator)
                except Exception as e:
                    print(f"Error processing/plotting for {allocator.name}: {e}")
                    self.set_status(f"Error with {allocator.name}: {e}", error=True)
        
        if plots_drawn_count == 0 and not (self.ax.lines or self.ax.collections or self.ax.patches): # Check if axes are truly empty
             self.ax.text(0.5, 0.5, "No data plotted. Check enabled allocators and date ranges.",
                          ha='center', va='center', transform=self.ax.transAxes, fontsize='small')
        
        # Add legend only if there are lines with labels
        handles, labels = self.ax.get_legend_handles_labels()
        if handles and labels:
             self.ax.legend(handles, labels, fontsize='x-small', loc='best')


        self.fig.autofmt_xdate(rotation=25, ha='right')
        self.fig.tight_layout()
        self.canvas.draw()

        self._refresh_allocations_display_area()
        self.set_status("Global update complete.", success=True)


    # --- Helper methods for UI updates ---
    def _update_allocator_selector_dropdown(self):
        allocator_names = sorted([data['instance'].name for data in self.allocators_store.values()])
        current_selection = self.allocator_selector_var.get()
        
        self.allocator_selector_combo['values'] = allocator_names
        
        if allocator_names:
            if current_selection in allocator_names and current_selection: # Ensure current_selection is not empty
                self.allocator_selector_var.set(current_selection)
            elif allocator_names: # Default to first if current is invalid or no selection
                self.allocator_selector_var.set(allocator_names[0])
            else: # No allocators left
                self.allocator_selector_var.set("")
        else:
            self.allocator_selector_var.set("")
        # self._refresh_allocations_display_area() # Often called by the method that calls this

    def _refresh_allocations_display_area(self):
        self.allocations_text_widget.config(state=tk.NORMAL, background='white')
        self.allocations_text_widget.delete("1.0", tk.END)

        selected_allocator_name = self.allocator_selector_var.get()
        display_text = "No allocator selected or allocator not found."
        
        found_data = None
        if selected_allocator_name: # Only proceed if a name is selected
            for data in self.allocators_store.values():
                if data['instance'].name == selected_allocator_name:
                    found_data = data
                    break
        
        if found_data:
            allocator = found_data['instance']
            is_enabled = found_data['is_enabled_var'].get()
            
            allocs = allocator.allocations
            status_text = "ENABLED" if is_enabled else "DISABLED"
            display_text = f"Allocator: '{allocator.name}' ({status_text})\n"
            
            if allocs:
                alloc_sum = sum(allocs.values())
                display_text += "\nAllocations:\n"
                display_text += "\n".join([f"  {inst}: {percent:.2%}" for inst, percent in sorted(allocs.items())])
                
                if not (abs(alloc_sum - 1.0) < 1e-7 or (not allocs and abs(alloc_sum) < 1e-9)): # Allow empty allocs to sum to 0
                    display_text += f"\n\nWARNING: Allocations sum to {alloc_sum*100:.2f}%. Reconfiguration may be needed."
            else:
                display_text += "\nNo allocations currently set for this allocator."
                if self.current_instruments_set:
                    display_text += "\nConsider configuring it for the current instruments."
        elif not self.allocators_store:
             display_text = "No allocators created yet. Please create one."


        self.allocations_text_widget.insert(tk.END, display_text)
        self.allocations_text_widget.config(state=tk.DISABLED, background=self.root.cget('bg'))


    def _setup_plot_axes_appearance(self):
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("Performance Metric (e.g., Return %)")
        self.ax.set_title("Allocator Performance Comparison")
        self.ax.grid(True, linestyle=':', alpha=0.6)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=10, interval_multiples=True)) # interval_multiples=True for date locators

    def _set_initial_plot_view_limits(self):
        try:
            start_dt = datetime.strptime(self.hist_start_date_entry.get(), "%Y-%m-%d").date()
            end_dt = date.today()
            if start_dt <= end_dt:
                self.ax.set_xlim(start_dt, end_dt)
            else:
                self.ax.set_xlim(end_dt - timedelta(days=365), end_dt)
        except ValueError:
            self.ax.set_xlim(date.today() - timedelta(days=365), date.today())

    def parse_date_entry(self, entry_widget: ttk.Entry, date_name: str) -> Optional[date]:
        date_str = entry_widget.get().strip()
        if not date_str:
            messagebox.showerror("Input Error", f"{date_name} cannot be empty.", parent=self.root)
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("Input Error", f"Invalid {date_name} format (YYYY-MM-DD).", parent=self.root)
            return None

    def set_status(self, message: str, error: bool = False, success: bool = False):
        self.status_bar.config(text=message)
        if error: self.status_bar.config(foreground="red", background="#FFDDDD")
        elif success: self.status_bar.config(foreground="darkgreen", background="#DDFFDD")
        else: self.status_bar.config(foreground="black", background=ttk.Style().lookup('TLabel', 'background'))


if __name__ == "__main__":
    root = tk.Tk()
    
    style = ttk.Style()
    # Attempt to use a theme that might offer better default styling
    # available_themes = style.theme_names()
    # if 'clam' in available_themes: style.theme_use('clam')
    # elif 'vista' in available_themes: style.theme_use('vista') # Good on Windows

    style.configure("Error.TEntry", foreground="red")
    # For fieldbackground, it's highly theme dependent. This is an attempt.
    style.map("Error.TEntry", fieldbackground=[('!disabled', '#FFEEEE')]) # Lighter pink

    style.configure("Accent.TButton", font=('Helvetica', 10, 'bold'), padding=5)
    style.configure("Success.TButton", foreground="white", background="green", font=('Helvetica', 9))
    style.map("Success.TButton", background=[('active', 'darkgreen')])
    style.configure("Danger.TButton", foreground="white", background="red", font=('Helvetica', 9))
    style.map("Danger.TButton", background=[('active', 'darkred')])
    
    style.configure("Toolbutton.TButton", padding=2, relief="flat")
    style.map("Toolbutton.TButton", relief=[('pressed', 'sunken'), ('!pressed', 'flat')])
    style.configure("Danger.Toolbutton.TButton", foreground="red", padding=2, relief="flat")
    style.map("Danger.Toolbutton.TButton", relief=[('pressed', 'sunken'), ('!pressed', 'flat')], foreground=[('pressed', 'darkred'), ('!pressed', 'red')])


    app_instance = App(root)
    root.mainloop()