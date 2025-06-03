\
# portfolio_optimizer/allocator/manual.py

from datetime import date
from typing import Set, Dict, Optional, Type, Any
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import uuid

from .allocator import PortfolioAllocator, AllocatorState, PAL

class ManualAllocator(PortfolioAllocator):
    """
    An allocator where the user manually specifies the allocation percentages
    for each instrument.
    """
    def __init__(self, **state: AllocatorState):
        super().__init__(**state)
        # Ensure allocations are present and values are float, defaulting to empty if not.
        raw_allocations = self._state.get('allocations', {})
        self._allocations: Dict[str, float] = {
            str(k): float(v) for k, v in raw_allocations.items() if isinstance(v, (int,float))
        }
        # Ensure all declared instruments have an allocation entry, defaulting to 0.0
        current_instruments = self.get_instruments()
        for inst in current_instruments:
            if inst not in self._allocations:
                self._allocations[inst] = 0.0
        # Prune allocations for instruments not in the declared set (e.g. if state was from old config)
        self._allocations = {
            inst: self._allocations.get(inst, 0.0) for inst in current_instruments
        }
        # Update state with cleaned/reconciled allocations
        self._state['allocations'] = self._allocations.copy()


    def get_state(self) -> AllocatorState:
        """Returns the current state of the allocator."""
        # Ensure the internal _allocations are in sync with the state dictionary
        # This can be redundant if __init__ and configure are correctly managing state,
        # but serves as a safeguard.
        self._state['allocations'] = self._allocations.copy()
        return self._state.copy()

    @classmethod
    def configure(cls: Type['ManualAllocator'],
                  parent_window: tk.Misc,
                  existing_state: Optional[AllocatorState] = None
                 ) -> Optional[AllocatorState]:
        
        initial_name = f"Manual Allocator {str(uuid.uuid4())[:4]}"
        initial_instruments_set: Set[str] = set()
        initial_allocs_percent: Dict[str, float] = {} # For dialog (0-100 scale)

        if existing_state:
            initial_name = str(existing_state.get('name', initial_name))
            # Instruments should be a set of strings
            instruments_data = existing_state.get('instruments')
            if isinstance(instruments_data, (set, list, tuple)):
                initial_instruments_set = set(map(str, instruments_data))
            
            # Allocations are decimal (0-1.0 scale) in state
            existing_allocs_decimal = existing_state.get('allocations', {})
            if isinstance(existing_allocs_decimal, dict):
                for instrument in initial_instruments_set: # Use current instruments for dialog
                    alloc_val = existing_allocs_decimal.get(instrument, 0.0)
                    initial_allocs_percent[instrument] = float(alloc_val) * 100.0
        
        dialog_title = f"Configure: {initial_name}" if existing_state else "Create New Manual Allocator"
        
        dialog = ManualAllocationDialog(parent_window,
                                        title=dialog_title,
                                        initial_instruments=initial_instruments_set,
                                        initial_allocations_percent=initial_allocs_percent,
                                        initial_name=initial_name)

        if dialog.result_name is not None and \
           dialog.result_allocations_percent is not None and \
           dialog.result_instruments is not None:
            
            final_allocations_decimal = {
                str(inst): perc / 100.0 for inst, perc in dialog.result_allocations_percent.items()
            }
            
            new_state: AllocatorState = {
                "name": str(dialog.result_name),
                "instruments": set(dialog.result_instruments), # Ensure it's a set
                "allocations": final_allocations_decimal
            }
            
            # Validate the new state before returning
            try:
                # Test instantiation with the new state (catches basic issues like missing name)
                # We don't actually keep this instance, just test creation.
                _ = cls(**new_state) 
            except ValueError as e:
                messagebox.showerror("Configuration Error", f"Failed to create allocator state: {e}", parent=parent_window)
                return None

            print(f"INFO: ManualAllocator '{new_state['name']}' configuration resulted in state: {new_state}")
            return new_state
        
        print(f"INFO: ManualAllocator configuration/creation cancelled for '{initial_name}'.")
        return None

    def compute_allocations(self, fitting_start_date: date, fitting_end_date: date) -> Dict[str, float]:
        # Allocations are already stored based on __init__ or re-configuration.
        # They should be aligned with the current instrument set defined in self._state['instruments'].
        
        current_instruments = self.get_instruments() # From self._state['instruments']
        
        # Retrieve allocations from state, which should be the source of truth
        # self._allocations is kept in sync with self._state['allocations'] by __init__ and configure
        
        # Ensure all instruments in the current set have an entry, defaulting to 0.0.
        # And prune any allocations for instruments no longer in the set.
        # This reconciliation is crucial.
        computed_allocs: Dict[str, float] = {
            inst: self._allocations.get(inst, 0.0) for inst in current_instruments
        }

        current_sum = sum(computed_allocs.values())
        if computed_allocs and abs(current_sum - 1.0) > 1e-7:
             print(f"WARNING ({self.get_name()}): Allocations provided by compute_allocations sum to {current_sum:.2f}%, not 100%. This might be as configured.")
        
        print(f"INFO ({self.get_name()}): 'Computing' allocations (returning configured): {computed_allocs}. Dates [{fitting_start_date} to {fitting_end_date}] ignored.")
        return computed_allocs.copy() # Return a copy


class ManualAllocationDialog(simpledialog.Dialog):
    def __init__(self, parent, title: str, 
                 initial_instruments: Set[str],
                 initial_allocations_percent: Dict[str, float], # Expects 0-100 scale
                 initial_name: str):
        
        self.initial_instruments_set = set(initial_instruments) # Work with a copy
        self.initial_allocations_percent = initial_allocations_percent # 0-100 scale
        self.initial_name = initial_name

        self.name_var = tk.StringVar(value=self.initial_name)
        
        # For dynamically managing instrument rows
        self.instrument_widgets: Dict[str, Dict[str, Any]] = {} # instrument_id -> {'frame': ttk.Frame, 'entry': ttk.Entry, 'ticker_var': tk.StringVar}
        self.instrument_id_counter = 0 # To generate unique IDs for frame keys

        self.sum_label_var = tk.StringVar()
        self.sum_label_widget: Optional[ttk.Label] = None
        
        self.scrollable_frame_for_instruments: Optional[ttk.Frame] = None


        self.result_name: Optional[str] = None
        self.result_allocations_percent: Optional[Dict[str, float]] = None # 0-100 scale
        self.result_instruments: Optional[Set[str]] = None
        super().__init__(parent, title)

    def body(self, master_frame: tk.Frame) -> tk.Entry | None:
        master_frame.pack_configure(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # --- Name Entry ---
        name_frame = ttk.Frame(master_frame)
        name_frame.pack(side="top", fill="x", pady=(0, 10))
        ttk.Label(name_frame, text="Allocator Name:").pack(side="left", padx=(0,5))
        self.name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=30)
        self.name_entry.pack(side="left", fill="x", expand=True)

        ttk.Separator(master_frame, orient='horizontal').pack(side="top", fill='x', pady=5)

        # --- Instrument Management Area ---
        instrument_area_label_frame = ttk.LabelFrame(master_frame, text="Instruments & Allocations")
        instrument_area_label_frame.pack(side="top", fill="both", expand=True, pady=5)
        
        add_instrument_button = ttk.Button(instrument_area_label_frame, text="Add Instrument", command=self._add_instrument_row_ui)
        add_instrument_button.pack(pady=5, anchor="nw")

        # Canvas for scrollable instrument list
        controls_canvas = tk.Canvas(instrument_area_label_frame, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(instrument_area_label_frame, orient="vertical", command=controls_canvas.yview)
        self.scrollable_frame_for_instruments = ttk.Frame(controls_canvas)
        
        self.scrollable_frame_for_instruments.bind(
            "<Configure>",
            lambda e: controls_canvas.configure(scrollregion=controls_canvas.bbox("all"))
        )
        controls_canvas.create_window((0, 0), window=self.scrollable_frame_for_instruments, anchor="nw")
        controls_canvas.configure(yscrollcommand=scrollbar.set)

        # Add header
        header_frame = ttk.Frame(self.scrollable_frame_for_instruments)
        header_frame.pack(fill="x")
        ttk.Label(header_frame, text="Instrument Ticker", font=('Helvetica', 9, 'bold')).pack(side="left", padx=5, pady=2, expand=True, fill="x")
        ttk.Label(header_frame, text="Allocation (%)", font=('Helvetica', 9, 'bold')).pack(side="left", padx=5, pady=2, expand=True, fill="x")
        ttk.Label(header_frame, text="Actions", font=('Helvetica', 9, 'bold')).pack(side="left", padx=5, pady=2, ipadx=10) # For delete button

        controls_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y") # Pack scrollbar conditionally if needed, or always

        # Populate initial instruments
        for ticker in sorted(list(self.initial_instruments_set)):
            alloc_percent = self.initial_allocations_percent.get(ticker, 0.0)
            self._add_instrument_row_ui(instrument_ticker=ticker, allocation_percent=alloc_percent)
        
        if not self.initial_instruments_set: # Add one empty row if no instruments initially
            self._add_instrument_row_ui()


        # --- Sum Label ---
        sum_frame = ttk.Frame(master_frame)
        sum_frame.pack(side="top", fill="x", pady=(10,0), anchor="sw")
        ttk.Label(sum_frame, text="Current Sum (%):").pack(side="left", padx=5)
        self.sum_label_widget = ttk.Label(sum_frame, textvariable=self.sum_label_var)
        self.sum_label_widget.pack(side="left")
        self._update_sum_and_validate_tickers()

        return self.name_entry

    def _add_instrument_row_ui(self, instrument_ticker: str = "", allocation_percent: float = 0.0):
        if self.scrollable_frame_for_instruments is None: return

        instrument_id = f"inst_{self.instrument_id_counter}"
        self.instrument_id_counter += 1

        row_frame = ttk.Frame(self.scrollable_frame_for_instruments)
        row_frame.pack(fill="x", pady=1)

        ticker_var = tk.StringVar(value=instrument_ticker)
        ticker_entry = ttk.Entry(row_frame, textvariable=ticker_var, width=20)
        ticker_entry.pack(side="left", padx=5, fill="x", expand=True)
        ticker_entry.bind("<FocusOut>", lambda e: self._update_sum_and_validate_tickers())
        ticker_entry.bind("<KeyRelease>", lambda e: self._update_sum_and_validate_tickers(quick_validate_ticker_for_duplicates=False))


        alloc_var = tk.StringVar(value=f"{allocation_percent:.2f}") # Store as string for Entry
        alloc_entry = ttk.Entry(row_frame, textvariable=alloc_var, width=10, validate="key")
        vcmd = (alloc_entry.register(self._validate_percentage_input_for_entry), '%P', alloc_entry) # Pass entry for context
        alloc_entry.configure(validatecommand=vcmd)
        alloc_entry.pack(side="left", padx=5, fill="x", expand=True)
        alloc_entry.bind("<KeyRelease>", lambda e: self._update_sum_and_validate_tickers(quick_validate_ticker_for_duplicates=False))
        alloc_entry.bind("<FocusOut>", lambda e, current_entry=alloc_entry: self._format_alloc_entry_on_focus_out(current_entry))


        del_btn = ttk.Button(row_frame, text="Del", width=4, style="Danger.Toolbutton.TButton",
                             command=lambda i_id=instrument_id: self._delete_instrument_row_ui(i_id))
        del_btn.pack(side="left", padx=(0, 2))

        self.instrument_widgets[instrument_id] = {
            'frame': row_frame, 
            'ticker_var': ticker_var, 'ticker_entry': ticker_entry,
            'alloc_var': alloc_var, 'alloc_entry': alloc_entry
        }
        
        # Scroll to bottom if adding made scrollbar appear or extend
        self.scrollable_frame_for_instruments.update_idletasks()
        # self.controls_canvas.yview_moveto(1) # Might be needed if list grows large

        if not instrument_ticker: # If adding a new empty row
            ticker_entry.focus_set()
        self._update_sum_and_validate_tickers() # Crucial to update after adding
        return row_frame


    def _delete_instrument_row_ui(self, instrument_id_to_delete: str):
        if instrument_id_to_delete in self.instrument_widgets:
            widgets = self.instrument_widgets[instrument_id_to_delete]
            widgets['frame'].destroy()
            del self.instrument_widgets[instrument_id_to_delete]
            self._update_sum_and_validate_tickers()
            # If last row deleted, add a new empty one? Optional.
            if not self.instrument_widgets:
                self._add_instrument_row_ui()
    
    def _format_alloc_entry_on_focus_out(self, entry_widget: ttk.Entry):
        try:
            val_str = entry_widget.get()
            if val_str:
                val = float(val_str)
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, f"{val:.2f}") # Format to 2 decimal places
        except ValueError:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, "0.00") # Default if invalid
        self._update_sum_and_validate_tickers()


    def _validate_percentage_input_for_entry(self, P: str, entry_widget: ttk.Entry) -> bool:
        # Standard validation allowing floats for entry
        if P == "" or P == ".": return True
        try:
            val = float(P)
            # Allow temporarily out of 0-100 range during typing
            # Final validation happens in `validate()`
            return True 
        except ValueError:
            # Allow partial valid inputs like "12."
            if P.count('.') <= 1 and all(c.isdigit() or c == '.' for c in P if c):
                 return True
            return False

    def _update_sum_and_validate_tickers(self, quick_validate_ticker_for_duplicates=True):
        current_sum = 0.0
        all_alloc_entries_valid_format = True
        
        current_tickers_in_dialog: Dict[str, List[ttk.Entry]] = {} # ticker_str -> list of entry widgets with this ticker
        
        for row_widgets in self.instrument_widgets.values():
            ticker_entry = row_widgets['ticker_entry']
            alloc_entry = row_widgets['alloc_entry']
            
            # Validate and collect tickers
            ticker_val = ticker_entry.get().strip().upper()
            if ticker_val : # only consider non-empty tickers for duplication checks
                if ticker_val not in current_tickers_in_dialog:
                    current_tickers_in_dialog[ticker_val] = []
                current_tickers_in_dialog[ticker_val].append(ticker_entry)

            # Sum allocations
            try:
                val_str = alloc_entry.get()
                if val_str: # Only sum if there's a value
                    current_sum += float(val_str)
            except ValueError:
                all_alloc_entries_valid_format = False # Mark sum as potentially unreliable
                alloc_entry.config(style="Error.TEntry")


        # Highlight duplicate tickers if not doing a quick validation pass
        if not quick_validate_ticker_for_duplicates:
            for ticker_list in current_tickers_in_dialog.values():
                is_duplicate = len(ticker_list) > 1
                for entry_widget in ticker_list:
                    entry_widget.config(style="Error.TEntry" if is_duplicate else "TEntry")
        
        self.sum_label_var.set(f"{current_sum:.2f}" if all_alloc_entries_valid_format else "Error in formats")
        
        if self.sum_label_widget:
            if not all_alloc_entries_valid_format:
                self.sum_label_widget.configure(foreground="magenta") # Special color for format errors
            elif abs(current_sum - 100.0) < 1e-7 and current_tickers_in_dialog: # Sum is 100
                self.sum_label_widget.configure(foreground="darkgreen")
            elif not current_tickers_in_dialog and abs(current_sum) < 1e-7: # No tickers, sum is 0
                 self.sum_label_widget.configure(foreground="black") # Neutral for zero instruments
            else: # Sum is not 100 or tickers exist with 0 sum
                self.sum_label_widget.configure(foreground="red")


    def validate(self) -> bool:
        # Validate Allocator Name
        allocator_name = self.name_var.get().strip()
        if not allocator_name:
            messagebox.showerror("Validation Error", "Allocator Name cannot be empty.", parent=self)
            if self.name_entry: self.name_entry.focus_set()
            return False
        
        # Collect and Validate Instruments and Allocations
        temp_allocations_percent: Dict[str, float] = {}
        temp_instruments_set: Set[str] = set()
        current_tickers_in_dialog: Dict[str, int] = {} # ticker_str -> count

        if not self.instrument_widgets and messagebox.askyesno(
            "No Instruments", 
            "No instruments are defined. Do you want to create an allocator with an empty instrument set?", 
            parent=self):
            self.result_name = allocator_name
            self.result_allocations_percent = {}
            self.result_instruments = set()
            print("INFO: User confirmed creating Manual Allocator with no instruments.")
            return True
        elif not self.instrument_widgets:
            return False # User chose not to proceed with no instruments

        focused_error_widget = False

        for row_widgets in self.instrument_widgets.values():
            ticker_entry = row_widgets['ticker_entry']
            alloc_entry = row_widgets['alloc_entry']
            
            ticker_val = ticker_entry.get().strip().upper() # Standardize to uppercase
            
            if not ticker_val: # Skip rows with no ticker
                # Optionally, treat as error or just ignore the row
                if alloc_entry.get().strip() and float(alloc_entry.get().strip()) != 0.0: # Allocation without ticker
                    messagebox.showerror("Validation Error", "An allocation is specified without an instrument ticker.", parent=self)
                    if not focused_error_widget: ticker_entry.focus_set(); focused_error_widget = True
                    return False
                continue # Ignore empty ticker rows if alloc is zero or empty


            # Check for duplicate tickers
            current_tickers_in_dialog[ticker_val] = current_tickers_in_dialog.get(ticker_val, 0) + 1
            if current_tickers_in_dialog[ticker_val] > 1:
                messagebox.showerror("Validation Error", f"Duplicate instrument ticker found: '{ticker_val}'.", parent=self)
                # Highlight all entries with this ticker (visual feedback already done by _update_sum_and_validate_tickers in some cases)
                for rw in self.instrument_widgets.values():
                    if rw['ticker_entry'].get().strip().upper() == ticker_val:
                        rw['ticker_entry'].config(style="Error.TEntry")
                        if not focused_error_widget: rw['ticker_entry'].focus_set(); focused_error_widget=True
                return False
            else:
                ticker_entry.config(style="TEntry") # Reset style if previously error

            temp_instruments_set.add(ticker_val) # Add valid, unique ticker

            # Validate Allocation Percentage
            try:
                val_str = alloc_entry.get()
                percentage = float(val_str) if val_str.strip() else 0.0 # Default to 0 if empty
                if not (0.0 <= percentage <= 100.0): 
                    messagebox.showerror("Validation Error", f"Allocation for '{ticker_val}' must be between 0.00 and 100.00.", parent=self)
                    if not focused_error_widget : alloc_entry.focus_set(); focused_error_widget=True
                    alloc_entry.config(style="Error.TEntry")
                    return False
                temp_allocations_percent[ticker_val] = percentage
                alloc_entry.config(style="TEntry") # Reset style
            except ValueError: 
                messagebox.showerror("Validation Error", f"Invalid number format for '{ticker_val}' allocation: '{alloc_entry.get()}'.", parent=self)
                if not focused_error_widget: alloc_entry.focus_set(); focused_error_widget=True
                alloc_entry.config(style="Error.TEntry")
                return False
        
        if focused_error_widget: return False # An error was found and focus set

        # If we reach here, all individual entries are valid. Now check the sum.
        current_sum = sum(temp_allocations_percent.values())
        
        if temp_instruments_set and abs(current_sum - 100.0) > 1e-7: # Only warn if instruments exist
            proceed = messagebox.askokcancel("Allocation Sum Warning",
                                             f"The total allocation is {current_sum:.2f}%, not 100%.\n"
                                             "If you save, these allocations will be used as is.\n\n"
                                             "Do you want to save these allocations anyway?",
                                             icon=messagebox.WARNING, parent=self)
            if not proceed:
                # Try to focus the first allocation entry as a general place to start corrections
                if self.instrument_widgets:
                    first_row_id = next(iter(self.instrument_widgets))
                    self.instrument_widgets[first_row_id]['alloc_entry'].focus_set()
                return False
        
        # All validations passed
        self.result_name = allocator_name
        self.result_allocations_percent = temp_allocations_percent
        self.result_instrumentdelete_instrument_row_uidelete_instrument_row_uidelete_instrument_row_uis = temp_instruments_set
        return True

    def apply(self) -> None:
        # Results are set in validate() if successful
        pass

    def buttonbox(self) -> None:
        box = ttk.Frame(self)
        self.ok_button = ttk.Button(box, text="Save Allocator", width=15, command=self.ok, default=tk.ACTIVE)
        self.ok_button.pack(side=tk.LEFT, padx=5, pady=5)
        cancel_button = ttk.Button(box, text="Cancel", width=10, command=self.cancel)
        cancel_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack(side=tk.BOTTOM, pady=5)

