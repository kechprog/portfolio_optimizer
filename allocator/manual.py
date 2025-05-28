# portfolio_optimizer/allocator/manual.py

from datetime import date
from typing import Set, Dict, Optional, Type, Any # Added Any
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import uuid

from .allocator import PortfolioAllocator, PAL

class ManualAllocator(PortfolioAllocator):
    """
    An allocator where the user manually specifies the allocation percentages
    for each instrument.
    """
    def __init__(self, name: str, initial_allocations: Optional[Dict[str, float]] = None):
        super().__init__(name)
        if initial_allocations is not None:
            self._allocations = {k: v for k, v in initial_allocations.items() if isinstance(v, (int,float))}
        else:
            self._allocations = {}

    def on_instruments_changed(self, new_instrument_set: Set[str]) -> None:
        updated_allocs: Dict[str, float] = {}
        changed = False
        for instrument in new_instrument_set:
            if instrument in self._allocations:
                updated_allocs[instrument] = self._allocations[instrument]
            else:
                updated_allocs[instrument] = 0.0
                changed = True
        
        if len(self._allocations) != len(updated_allocs) or \
           any(old_inst not in new_instrument_set for old_inst in self._allocations):
            changed = True
        
        self._allocations = updated_allocs
        if changed:
            current_sum = sum(self._allocations.values())
            print(f"INFO ({self.name}): Instruments changed. Allocations updated. Current sum: {current_sum:.4f}.")
            if self._allocations and abs(current_sum - 1.0) > 1e-7:
                 print(f"WARNING ({self.name}): Allocations sum to {current_sum:.4f}. Reconfiguration may be needed.")

    @classmethod
    def configure_or_create(cls: Type['ManualAllocator'],
                            parent_window: tk.Misc,
                            current_instruments: Set[str],
                            existing_allocator: Optional[PortfolioAllocator] = None,
                           ) -> Optional['ManualAllocator']:
        initial_name = f"Manual Allocator {str(uuid.uuid4())[:4]}"
        initial_allocs_for_dialog_decimal: Dict[str, float] = {}

        if existing_allocator and isinstance(existing_allocator, ManualAllocator):
            initial_name = existing_allocator.name
            temp_existing_allocs_decimal = existing_allocator.allocations # Uses property
            for instrument in current_instruments:
                initial_allocs_for_dialog_decimal[instrument] = temp_existing_allocs_decimal.get(instrument, 0.0)
        else:
            for instrument in current_instruments:
                initial_allocs_for_dialog_decimal[instrument] = 0.0

        dialog_title = f"Configure: {initial_name}" if existing_allocator else "Create New Manual Allocator"
        initial_allocs_for_dialog_percent = {
            k: v * 100.0 for k, v in initial_allocs_for_dialog_decimal.items()
        }

        dialog = ManualAllocationDialog(parent_window,
                                        title=dialog_title,
                                        instruments=current_instruments,
                                        initial_allocations_percent=initial_allocs_for_dialog_percent,
                                        initial_name=initial_name)

        if dialog.result_name is not None and dialog.result_allocations_percent is not None:
            final_allocations_decimal = {
                inst: perc / 100.0 for inst, perc in dialog.result_allocations_percent.items()
            }
            # Create instance first
            new_instance = cls(name=dialog.result_name)
            # Then set its allocations and reconcile with current_instruments
            new_instance._allocations = final_allocations_decimal
            new_instance.on_instruments_changed(current_instruments) # Important to align/prune based on current_instruments
            
            print(f"INFO: ManualAllocator '{new_instance.name}' configured/created with allocations: {new_instance.allocations}")
            return new_instance
        
        print(f"INFO: ManualAllocator configuration/creation cancelled for '{initial_name}'.")
        return None

    def compute_allocations(self, fitting_start_date: date, fitting_end_date: date) -> Dict[str, float]:
        print(f"INFO ({self.name}): 'Computing' allocations (returning configured): {self._allocations}. Dates [{fitting_start_date} to {fitting_end_date}] ignored.")
        current_sum = sum(self._allocations.values())
        if self._allocations and abs(current_sum - 1.0) > 1e-7 :
             print(f"WARNING ({self.name}): Allocations provided by compute_allocations sum to {current_sum:.2f}%, not 100%.")
        return self.allocations # Returns a copy

    def save_state(self) -> Dict[str, Any]:
        """Serializes the allocator's configuration."""
        return {
            "allocations": self._allocations.copy() # Save a copy
        }

    def load_state(self, config_params: Dict[str, Any], current_instruments: Set[str]) -> None:
        """Restores the allocator's state from configuration parameters."""
        loaded_allocs = config_params.get("allocations", {})
        self._allocations = {k: float(v) for k,v in loaded_allocs.items() if isinstance(v, (int, float))} # Ensure float
        # After loading, reconcile with the current set of instruments in the app
        self.on_instruments_changed(current_instruments)
        print(f"INFO ({self.name}): State loaded. Allocations: {self._allocations}")

# --- ManualAllocationDialog class definition remains the same ---
# (It was provided in the previous response and is correctly placed here)
class ManualAllocationDialog(simpledialog.Dialog):
    def __init__(self, parent, title: str, instruments: Set[str],
                 initial_allocations_percent: Dict[str, float], # Expects 0-100 scale
                 initial_name: str):
        self.instruments = sorted(list(instruments))
        self.initial_allocations_percent = initial_allocations_percent # 0-100 scale
        self.initial_name = initial_name

        self.name_var = tk.StringVar(value=self.initial_name)
        self.entries: Dict[str, tk.Entry] = {}
        self.sum_label_var = tk.StringVar()
        self.sum_label_widget: Optional[ttk.Label] = None

        self.result_name: Optional[str] = None
        self.result_allocations_percent: Optional[Dict[str, float]] = None # 0-100 scale
        super().__init__(parent, title)

    def body(self, master_frame: tk.Frame) -> tk.Entry | None:
        master_frame.pack_configure(padx=10, pady=10)

        name_frame = ttk.Frame(master_frame)
        name_frame.pack(side="top", fill="x", pady=(0, 10))
        ttk.Label(name_frame, text="Allocator Name:").pack(side="left", padx=(0,5))
        name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=30)
        name_entry.pack(side="left", fill="x", expand=True)

        ttk.Separator(master_frame, orient='horizontal').pack(side="top", fill='x', pady=5)
        
        alloc_area_frame = ttk.Frame(master_frame)
        alloc_area_frame.pack(side="top", fill="both", expand=True)

        canvas = tk.Canvas(alloc_area_frame, borderwidth=0, width=380, height=min(250, len(self.instruments)*30 + 40)) # Adjust height
        scrollbar = ttk.Scrollbar(alloc_area_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        if len(self.instruments) * 30 + 40 > 250: # Heuristic for when to show scrollbar
            scrollbar.pack(side="right", fill="y")

        ttk.Label(scrollable_frame, text="Instrument", font=('Helvetica', 10, 'bold')).grid(row=0, column=0, padx=5, pady=3, sticky="w")
        ttk.Label(scrollable_frame, text="Allocation (%)", font=('Helvetica', 10, 'bold')).grid(row=0, column=1, padx=5, pady=3, sticky="w")

        vcmd = (master_frame.register(self._validate_percentage_input), '%P')

        for i, instrument_name in enumerate(self.instruments):
            ttk.Label(scrollable_frame, text=instrument_name + ":").grid(row=i + 1, column=0, padx=5, pady=3, sticky="w")
            entry = ttk.Entry(scrollable_frame, width=10, validate="key", validatecommand=vcmd)
            initial_val_str = f"{self.initial_allocations_percent.get(instrument_name, 0.0):.2f}"
            entry.insert(0, initial_val_str)
            entry.grid(row=i + 1, column=1, padx=5, pady=3, sticky="ew")
            entry.bind("<KeyRelease>", self._update_sum) # Use KeyRelease for more responsive sum update
            entry.bind("<FocusOut>", self._update_sum)   # Keep FocusOut for final validation/update
            self.entries[instrument_name] = entry
        
        scrollable_frame.grid_columnconfigure(1, weight=1) # Allow entry to expand a bit if space

        sum_frame = ttk.Frame(master_frame)
        sum_frame.pack(side="top", fill="x", pady=(10,0), anchor="sw") # anchor south-west
        ttk.Label(sum_frame, text="Current Sum (%):").pack(side="left", padx=5)
        self.sum_label_widget = ttk.Label(sum_frame, textvariable=self.sum_label_var)
        self.sum_label_widget.pack(side="left")
        self._update_sum() # Initial sum calculation

        return name_entry # Return the name_entry for initial focus by the dialog system

    def _validate_percentage_input(self, P: str) -> bool:
        if P == "" or P == ".": return True 
        try:
            val = float(P)
            return 0.0 <= val <= 100.0 or (P.endswith(".") and 0.0 <= float(P[:-1]) <=100.0)
        except ValueError:
            if P.count('.') <= 1 and all(c.isdigit() or c == '.' for c in P):
                 return True 
            return False


    def _update_sum(self, event=None) -> None:
        current_sum = 0.0
        all_entries_empty = True
        for entry_widget in self.entries.values():
            try:
                val_str = entry_widget.get()
                if val_str: 
                    all_entries_empty = False
                    current_sum += float(val_str)
            except ValueError: 
                pass 
        
        self.sum_label_var.set(f"{current_sum:.2f}")
        if self.sum_label_widget:
            is_sum_ok = abs(current_sum - 100.0) < 1e-7
            is_empty_sum_ok = all_entries_empty and abs(current_sum) < 1e-7
            
            if is_sum_ok or (not self.instruments and abs(current_sum) < 1e-7) : 
                self.sum_label_widget.configure(foreground="darkgreen")
            elif is_empty_sum_ok and self.instruments: 
                 self.sum_label_widget.configure(foreground="orange") 
            else:
                self.sum_label_widget.configure(foreground="red")


    def validate(self) -> bool:
        allocator_name = self.name_var.get().strip()
        if not allocator_name:
            messagebox.showerror("Validation Error", "Allocator Name cannot be empty.", parent=self)
            if self.initial_focus: self.initial_focus.focus_set()
            return False
        self.result_name = allocator_name

        current_sum = 0.0
        temp_allocations_percent = {}
        
        if not self.instruments: 
            self.result_allocations_percent = {}
            return True

        for instrument_name, entry_widget in self.entries.items():
            try:
                val_str = entry_widget.get()
                if not val_str.strip(): 
                    percentage = 0.0
                else:
                    percentage = float(val_str)

                if not (0.0 <= percentage <= 100.0): 
                    messagebox.showerror("Validation Error", f"Allocation for {instrument_name} must be between 0.00 and 100.00.", parent=self)
                    entry_widget.focus_set()
                    return False
                temp_allocations_percent[instrument_name] = percentage
                current_sum += percentage
            except ValueError: 
                messagebox.showerror("Validation Error", f"Invalid number format for {instrument_name}: '{entry_widget.get()}'. Please enter a valid percentage.", parent=self)
                entry_widget.focus_set()
                return False
        
        if abs(current_sum - 100.0) > 1e-7:
            proceed = messagebox.askokcancel("Validation Warning",
                                             f"Allocations sum to {current_sum:.2f}%, which is not 100%.\n"
                                             "This might lead to unexpected behavior or normalization later.\n\n"
                                             "Do you want to save these allocations anyway?",
                                             icon=messagebox.WARNING, parent=self)
            if not proceed:
                if self.entries: next(iter(self.entries.values())).focus_set()
                return False 
        
        self.result_allocations_percent = temp_allocations_percent
        return True

    def apply(self) -> None:
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