# c:\Users\Eduar\projects\portfolio_optimizer\allocator\manual.py

from datetime import date
from typing import Set, Dict, Optional, Type, Any, List # Added List for type hint
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import uuid
import logging

from .allocator import PortfolioAllocator, AllocatorState, PAL
from portfolio import Portfolio # Changed from relative to direct

logger = logging.getLogger(__name__)

class ManualAllocator(PortfolioAllocator):
    """
    An allocator where the user manually specifies the allocation percentages
    for each instrument.
    """
    def __init__(self, **state: AllocatorState):
        super().__init__(**state)
        raw_allocations = self._state.get('allocations', {})
        self._allocations: Dict[str, float] = {
            str(k): float(v) for k, v in raw_allocations.items() if isinstance(v, (int,float))
        }
        current_instruments = self.get_instruments()
        for inst in current_instruments:
            if inst not in self._allocations:
                self._allocations[inst] = 0.0
        self._allocations = {
            inst: self._allocations.get(inst, 0.0) for inst in current_instruments
        }
        self._state['allocations'] = self._allocations.copy()


    def get_state(self) -> AllocatorState:
        self._state['allocations'] = self._allocations.copy()
        return self._state.copy()

    @classmethod
    def configure(cls: Type['ManualAllocator'],
                  parent_window: tk.Misc,
                  existing_state: Optional[AllocatorState] = None
                 ) -> Optional[AllocatorState]:
        
        initial_name = f"Manual Allocator {str(uuid.uuid4())[:4]}"
        initial_instruments_set: Set[str] = set()
        initial_allocs_percent: Dict[str, float] = {} 

        if existing_state:
            initial_name = str(existing_state.get('name', initial_name))
            instruments_data = existing_state.get('instruments')
            if isinstance(instruments_data, (set, list, tuple)):
                initial_instruments_set = set(map(str, instruments_data))
            
            existing_allocs_decimal = existing_state.get('allocations', {})
            if isinstance(existing_allocs_decimal, dict):
                for instrument in initial_instruments_set:
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
                "instruments": set(dialog.result_instruments), 
                "allocations": final_allocations_decimal
            }
            
            try:
                _ = cls(**new_state) 
            except ValueError as e:
                messagebox.showerror("Configuration Error", f"Failed to create allocator state: {e}", parent=parent_window)
                return None

            logger.info(f"ManualAllocator '{new_state['name']}' configuration resulted in state: {new_state}")
            return new_state
        
        logger.info(f"ManualAllocator configuration/creation cancelled for '{initial_name}'.")
        return None

    def compute_allocations(self, fitting_start_date: date, fitting_end_date: date, test_end_date: date) -> Portfolio:
        """
        Computes allocations and returns them within a Portfolio object.
        For ManualAllocator, this involves creating a single segment in the portfolio
        that spans the fitting_start_date to fitting_end_date with the stored manual allocations.
        """
        current_instruments = self.get_instruments()
        # Use the internally stored allocations
        manual_allocs: Dict[str, float] = {
            inst: self._allocations.get(inst, 0.0) for inst in current_instruments
        }
        
        # Create a Portfolio object starting from fitting_start_date
        # The Portfolio object itself uses fitting_start_date as its inception.
        # The segment then defines the period for these specific allocations.
        portfolio = Portfolio(start_date=fitting_start_date)
        
        # Add a single segment with these allocations spanning the full period
        # The segment's start date within the portfolio is implicitly fitting_start_date (handled by Portfolio.append)
        # The segment's end date is fitting_end_date
        if fitting_end_date > fitting_start_date:
            portfolio.append(end_date=fitting_end_date, allocations=manual_allocs)
            logger.info(f"({self.get_name()}): Created Portfolio segment from {fitting_start_date} to {fitting_end_date} with allocations: {manual_allocs}")
        else:
            # If dates are not valid for a segment, return an empty portfolio (no segments)
            logger.warning(f"({self.get_name()}): fitting_end_date ({fitting_end_date}) is not after fitting_start_date ({fitting_start_date}). Returning empty portfolio.")
            # The portfolio object is already initialized but will contain no segments.

        current_sum = sum(manual_allocs.values())
        if manual_allocs and abs(current_sum - 1.0) > 1e-7:
             logger.warning(f"({self.get_name()}): Allocations for the segment sum to {current_sum:.2f}%, not 100%. This might be as configured.")
        
        return portfolio


class ManualAllocationDialog(simpledialog.Dialog):
    def __init__(self, parent, title: str, 
                 initial_instruments: Set[str],
                 initial_allocations_percent: Dict[str, float], 
                 initial_name: str):
        
        self.initial_instruments_set = set(initial_instruments) 
        self.initial_allocations_percent = initial_allocations_percent 
        self.initial_name = initial_name
        self.name_var = tk.StringVar(value=self.initial_name)
        self.instrument_widgets: Dict[str, Dict[str, Any]] = {} 
        self.instrument_id_counter = 0 
        self.sum_label_var = tk.StringVar()
        self.sum_label_widget: Optional[ttk.Label] = None
        self.scrollable_frame_for_instruments: Optional[ttk.Frame] = None
        self.result_name: Optional[str] = None
        self.result_allocations_percent: Optional[Dict[str, float]] = None 
        self.result_instruments: Optional[Set[str]] = None
        super().__init__(parent, title)

    def body(self, master_frame: tk.Frame) -> tk.Entry | None:
        master_frame.pack_configure(padx=10, pady=10, fill=tk.BOTH, expand=True)

        name_frame = ttk.Frame(master_frame)
        name_frame.pack(side="top", fill="x", pady=(0, 10))
        ttk.Label(name_frame, text="Allocator Name:").pack(side="left", padx=(0,5))
        self.name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=30)
        self.name_entry.pack(side="left", fill="x", expand=True)

        ttk.Separator(master_frame, orient='horizontal').pack(side="top", fill='x', pady=5)
        
        instrument_area_label_frame = ttk.LabelFrame(master_frame, text="Instruments & Allocations")
        instrument_area_label_frame.pack(side="top", fill="both", expand=True, pady=5)
        
        add_instrument_button = ttk.Button(instrument_area_label_frame, text="Add Instrument", command=self._add_instrument_row_ui)
        add_instrument_button.pack(pady=5, anchor="nw")

        controls_canvas = tk.Canvas(instrument_area_label_frame, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(instrument_area_label_frame, orient="vertical", command=controls_canvas.yview)
        self.scrollable_frame_for_instruments = ttk.Frame(controls_canvas)
        
        self.scrollable_frame_for_instruments.bind(
            "<Configure>", lambda e: controls_canvas.configure(scrollregion=controls_canvas.bbox("all"))
        )
        controls_canvas.create_window((0, 0), window=self.scrollable_frame_for_instruments, anchor="nw")
        controls_canvas.configure(yscrollcommand=scrollbar.set)

        header_frame = ttk.Frame(self.scrollable_frame_for_instruments)
        header_frame.pack(fill="x")
        ttk.Label(header_frame, text="Instrument Ticker", font=('Helvetica', 9, 'bold')).pack(side="left", padx=5, pady=2, expand=True, fill="x")
        ttk.Label(header_frame, text="Allocation (%)", font=('Helvetica', 9, 'bold')).pack(side="left", padx=5, pady=2, expand=True, fill="x")
        ttk.Label(header_frame, text="Actions", font=('Helvetica', 9, 'bold')).pack(side="left", padx=5, pady=2, ipadx=10) 

        controls_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y") 

        for ticker in sorted(list(self.initial_instruments_set)):
            alloc_percent = self.initial_allocations_percent.get(ticker, 0.0)
            self._add_instrument_row_ui(instrument_ticker=ticker, allocation_percent=alloc_percent)
        
        if not self.initial_instruments_set: 
            self._add_instrument_row_ui()

        sum_frame = ttk.Frame(master_frame)
        sum_frame.pack(side="top", fill="x", pady=(10,0), anchor="sw")
        ttk.Label(sum_frame, text="Current Sum (%):").pack(side="left", padx=5)
        self.sum_label_widget = ttk.Label(sum_frame, textvariable=self.sum_label_var)
        self.sum_label_widget.pack(side="left")
        self._update_sum_and_validate_tickers()
        return self.name_entry

    def _add_instrument_row_ui(self, instrument_ticker: str = "", allocation_percent: float = 0.0):
        if self.scrollable_frame_for_instruments is None: return

        instrument_id = f"inst_{self.instrument_id_counter}"; self.instrument_id_counter += 1
        row_frame = ttk.Frame(self.scrollable_frame_for_instruments); row_frame.pack(fill="x", pady=1)

        ticker_var = tk.StringVar(value=instrument_ticker)
        ticker_entry = ttk.Entry(row_frame, textvariable=ticker_var, width=20)
        ticker_entry.pack(side="left", padx=5, fill="x", expand=True)
        ticker_entry.bind("<FocusOut>", lambda e: self._update_sum_and_validate_tickers())
        ticker_entry.bind("<KeyRelease>", lambda e: self._update_sum_and_validate_tickers(quick_validate_ticker_for_duplicates=False))

        alloc_var = tk.StringVar(value=f"{allocation_percent:.2f}")
        alloc_entry = ttk.Entry(row_frame, textvariable=alloc_var, width=10, validate="key")
        vcmd = (alloc_entry.register(self._validate_percentage_input_for_entry), '%P', alloc_entry)
        alloc_entry.configure(validatecommand=vcmd)
        alloc_entry.pack(side="left", padx=5, fill="x", expand=True)
        alloc_entry.bind("<KeyRelease>", lambda e: self._update_sum_and_validate_tickers(quick_validate_ticker_for_duplicates=False))
        alloc_entry.bind("<FocusOut>", lambda e, current_entry=alloc_entry: self._format_alloc_entry_on_focus_out(current_entry))

        del_btn = ttk.Button(row_frame, text="Del", width=4, style="Danger.Toolbutton.TButton",
                             command=lambda i_id=instrument_id: self._delete_instrument_row_ui(i_id))
        del_btn.pack(side="left", padx=(0, 2))

        self.instrument_widgets[instrument_id] = {
            'frame': row_frame, 'ticker_var': ticker_var, 'ticker_entry': ticker_entry,
            'alloc_var': alloc_var, 'alloc_entry': alloc_entry
        }
        self.scrollable_frame_for_instruments.update_idletasks()
        if not instrument_ticker: ticker_entry.focus_set()
        self._update_sum_and_validate_tickers()
        return row_frame

    def _delete_instrument_row_ui(self, instrument_id_to_delete: str):
        if instrument_id_to_delete in self.instrument_widgets:
            self.instrument_widgets[instrument_id_to_delete]['frame'].destroy()
            del self.instrument_widgets[instrument_id_to_delete]
            self._update_sum_and_validate_tickers()
            if not self.instrument_widgets: self._add_instrument_row_ui()
    
    def _format_alloc_entry_on_focus_out(self, entry_widget: ttk.Entry):
        try:
            val_str = entry_widget.get()
            if val_str: entry_widget.insert(0, f"{float(val_str):.2f}"); entry_widget.delete(len(f"{float(val_str):.2f}"), tk.END) # Format and clear rest
            else: entry_widget.insert(0, "0.00")
        except ValueError: entry_widget.delete(0, tk.END); entry_widget.insert(0, "0.00")
        self._update_sum_and_validate_tickers()

    def _validate_percentage_input_for_entry(self, P: str, entry_widget: ttk.Entry) -> bool:
        if P == "" or P == ".": return True
        try: float(P); return True 
        except ValueError:
            if P.count('.') <= 1 and all(c.isdigit() or c == '.' for c in P if c): return True
            return False

    def _update_sum_and_validate_tickers(self, quick_validate_ticker_for_duplicates=True):
        current_sum = 0.0; all_alloc_entries_valid_format = True
        current_tickers_in_dialog: Dict[str, List[ttk.Entry]] = {}
        
        for row_widgets in self.instrument_widgets.values():
            ticker_entry = row_widgets['ticker_entry']; alloc_entry = row_widgets['alloc_entry']
            ticker_val = ticker_entry.get().strip().upper()
            if ticker_val :
                if ticker_val not in current_tickers_in_dialog: current_tickers_in_dialog[ticker_val] = []
                current_tickers_in_dialog[ticker_val].append(ticker_entry)
            try:
                val_str = alloc_entry.get()
                if val_str: current_sum += float(val_str)
            except ValueError: all_alloc_entries_valid_format = False; alloc_entry.config(style="Error.TEntry")

        if not quick_validate_ticker_for_duplicates: # Full validation pass, not just sum update
            for ticker_val, entries in current_tickers_in_dialog.items():
                is_duplicate = len(entries) > 1
                for entry_widget in entries:
                    entry_widget.config(style="Error.TEntry" if is_duplicate and ticker_val else "TEntry")
            # Reset non-duplicate, non-empty tickers that might have been styled as error
            for row_widgets_inner in self.instrument_widgets.values():
                 t_entry = row_widgets_inner['ticker_entry']
                 t_val = t_entry.get().strip().upper()
                 if t_val and len(current_tickers_in_dialog.get(t_val,[])) <=1 :
                      t_entry.config(style="TEntry")


        self.sum_label_var.set(f"{current_sum:.2f}" if all_alloc_entries_valid_format else "Format Error")
        if self.sum_label_widget:
            if not all_alloc_entries_valid_format: self.sum_label_widget.configure(foreground="magenta")
            elif abs(current_sum - 100.0) < 1e-7 and current_tickers_in_dialog: self.sum_label_widget.configure(foreground="darkgreen")
            elif not current_tickers_in_dialog and abs(current_sum) < 1e-7: self.sum_label_widget.configure(foreground="black") 
            else: self.sum_label_widget.configure(foreground="red")

    def validate(self) -> bool:
        allocator_name = self.name_var.get().strip()
        if not allocator_name:
            messagebox.showerror("Validation Error", "Allocator Name cannot be empty.", parent=self)
            if self.name_entry: self.name_entry.focus_set()
            return False
        
        temp_allocations_percent: Dict[str, float] = {}
        temp_instruments_set: Set[str] = set()
        processed_tickers_for_duplicate_check: Dict[str, int] = {} 
        focused_error_widget = False

        if not self.instrument_widgets:
            if messagebox.askyesno("No Instruments", "No instruments defined. Create with an empty set?", parent=self):
                self.result_name = allocator_name; self.result_allocations_percent = {}; self.result_instruments = set()
                # User confirmed creating with no instruments
                return True
            else:
                # User chose not to proceed with no instruments
                return False

        for row_widgets in self.instrument_widgets.values():
            ticker_entry = row_widgets['ticker_entry']; alloc_entry = row_widgets['alloc_entry']
            ticker_val = ticker_entry.get().strip().upper()
            
            if not ticker_val:
                if alloc_entry.get().strip() and float(alloc_entry.get().strip()) != 0.0:
                    messagebox.showerror("Validation Error", "Allocation specified without ticker.", parent=self)
                    if not focused_error_widget: ticker_entry.focus_set(); focused_error_widget = True
                    return False
                continue 

            processed_tickers_for_duplicate_check[ticker_val] = processed_tickers_for_duplicate_check.get(ticker_val, 0) + 1
            if processed_tickers_for_duplicate_check[ticker_val] > 1:
                messagebox.showerror("Validation Error", f"Duplicate ticker: '{ticker_val}'.", parent=self)
                for rw in self.instrument_widgets.values():
                    if rw['ticker_entry'].get().strip().upper() == ticker_val:
                        rw['ticker_entry'].config(style="Error.TEntry")
                        if not focused_error_widget: rw['ticker_entry'].focus_set(); focused_error_widget=True
                return False
            else: ticker_entry.config(style="TEntry")

            temp_instruments_set.add(ticker_val)
            try:
                val_str = alloc_entry.get(); percentage = float(val_str) if val_str.strip() else 0.0
                if not (0.0 <= percentage <= 100.0): 
                    messagebox.showerror("Validation Error", f"Allocation for '{ticker_val}' must be 0-100.", parent=self)
                    if not focused_error_widget : alloc_entry.focus_set(); focused_error_widget=True
                    alloc_entry.config(style="Error.TEntry")
                    return False
                temp_allocations_percent[ticker_val] = percentage; alloc_entry.config(style="TEntry")
            except ValueError: 
                messagebox.showerror("Validation Error", f"Invalid number for '{ticker_val}' allocation: '{alloc_entry.get()}'.", parent=self)
                if not focused_error_widget: alloc_entry.focus_set(); focused_error_widget=True
                alloc_entry.config(style="Error.TEntry")
                return False
        
        if focused_error_widget: 
            return False

        current_sum = sum(temp_allocations_percent.values())
        if temp_instruments_set and abs(current_sum - 100.0) > 1e-7: 
            proceed = messagebox.askokcancel("Sum Warning", f"Allocations sum to {current_sum:.2f}%, not 100%. Save anyway?", icon=messagebox.WARNING, parent=self)
            if not proceed:
                if self.instrument_widgets: next(iter(self.instrument_widgets.values()))['alloc_entry'].focus_set()
                return False
        
        self.result_name = allocator_name
        self.result_allocations_percent = temp_allocations_percent
        self.result_instruments = temp_instruments_set # Corrected spelling
        logger.debug(f"ManualAllocationDialog validation success: name={self.result_name}, allocs={self.result_allocations_percent}, instrs={self.result_instruments}")
        return True

    def apply(self) -> None: pass # Results set in validate()

    def buttonbox(self) -> None:
        box = ttk.Frame(self)
        self.ok_button = ttk.Button(box, text="Save Allocator", width=15, command=self.ok, default=tk.ACTIVE)
        self.ok_button.pack(side=tk.LEFT, padx=5, pady=5)
        cancel_button = ttk.Button(box, text="Cancel", width=10, command=self.cancel)
        cancel_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Return>", self.ok); self.bind("<Escape>", self.cancel)
        box.pack(side=tk.BOTTOM, pady=5)