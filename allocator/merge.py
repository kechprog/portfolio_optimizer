# portfolio_optimizer/allocator/merge.py

from datetime import date
from typing import Set, Dict, Optional, Type, Any, List, Tuple
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import uuid
import logging

from .allocator import PortfolioAllocator, AllocatorState, PAL
from portfolio import Portfolio

logger = logging.getLogger(__name__)

class MergeAllocator(PortfolioAllocator):
    """
    An allocator that combines portfolios from multiple other allocators with specified weights.
    """
    def __init__(self, **state: AllocatorState):
        super().__init__(**state)
        
        # Store allocator references and their weights
        # Format: {'allocator_name': weight, ...}
        raw_allocator_weights = self._state.get('allocator_weights', {})
        self._allocator_weights: Dict[str, float] = {
            str(k): float(v) for k, v in raw_allocator_weights.items() if isinstance(v, (int, float))
        }
        
        # Normalize weights to sum to 1.0
        total_weight = sum(self._allocator_weights.values())
        if total_weight > 0:
            self._allocator_weights = {
                name: weight / total_weight 
                for name, weight in self._allocator_weights.items()
            }
        
        self._state['allocator_weights'] = self._allocator_weights.copy()
        
        # Reference to app instance to access other allocators (will be set externally)
        self._app_instance = None

    def get_state(self) -> AllocatorState:
        self._state['allocator_weights'] = self._allocator_weights.copy()
        return self._state.copy()

    def set_app_instance(self, app_instance):
        """Set reference to the app instance to access other allocators."""
        self._app_instance = app_instance

    def get_instruments(self) -> Set[str]:
        """
        Override to return the union of all instruments from constituent allocators.
        """
        if not self._app_instance or not self._allocator_weights:
            return set()
        
        all_instruments = set()
        for allocator_name in self._allocator_weights.keys():
            # Find the allocator by name
            for allocator_data in self._app_instance.allocators_store.values():
                if allocator_data['instance'].get_name() == allocator_name:
                    constituent_instruments = allocator_data['instance'].get_instruments()
                    all_instruments.update(constituent_instruments)
                    break
        
        return all_instruments

    @classmethod
    def configure(cls: Type['MergeAllocator'],
                  parent_window: tk.Misc,
                  existing_state: Optional[AllocatorState] = None
                 ) -> Optional[AllocatorState]:
        
        # Need to access app instance to get available allocators
        app_instance = getattr(parent_window, 'app_instance', None)
        
        if not app_instance:
            # Try to find app instance by walking up the widget hierarchy
            widget = parent_window
            while widget and not hasattr(widget, 'allocators_store'):
                widget = widget.master
            app_instance = widget
            
        if not app_instance or not hasattr(app_instance, 'allocators_store'):
            messagebox.showerror("Configuration Error", 
                               "Cannot access allocators. MergeAllocator requires access to existing allocators.",
                               parent=parent_window)
            return None
        
        initial_name = f"Merge Allocator {str(uuid.uuid4())[:4]}"
        initial_allocator_weights: Dict[str, float] = {}

        if existing_state:
            initial_name = str(existing_state.get('name', initial_name))
            weights_data = existing_state.get('allocator_weights', {})
            if isinstance(weights_data, dict):
                initial_allocator_weights = {str(k): float(v) for k, v in weights_data.items()}
        
        dialog_title = f"Configure: {initial_name}" if existing_state else "Create New Merge Allocator"
        
        dialog = MergeAllocatorDialog(parent_window,
                                    title=dialog_title,
                                    app_instance=app_instance,
                                    initial_allocator_weights=initial_allocator_weights,
                                    initial_name=initial_name)

        if (dialog.result_name is not None and 
            dialog.result_allocator_weights is not None):
            
            new_state: AllocatorState = {
                "name": str(dialog.result_name),
                "allocator_weights": dialog.result_allocator_weights.copy(),
                "instruments": set()  # MergeAllocator instruments will be derived from constituent allocators
            }
            
            try:
                _ = cls(**new_state)
            except ValueError as e:
                messagebox.showerror("Configuration Error", 
                                   f"Failed to create allocator state: {e}", 
                                   parent=parent_window)
                return None

            logger.info(f"MergeAllocator '{new_state['name']}' configuration resulted in state: {new_state}")
            return new_state
        
        logger.info(f"MergeAllocator configuration/creation cancelled for '{initial_name}'.")
        return None

    def compute_allocations(self, fitting_start_date: date, fitting_end_date: date, test_end_date: date) -> Portfolio:
        """
        Computes allocations by combining portfolios from constituent allocators with their weights.
        """
        if not self._app_instance:
            logger.error(f"({self.get_name()}): No app instance set. Cannot access other allocators.")
            return Portfolio(start_date=fitting_end_date)
        
        if not self._allocator_weights:
            logger.warning(f"({self.get_name()}): No allocator weights defined. Returning empty portfolio.")
            return Portfolio(start_date=fitting_end_date)
        
        # Get portfolios from constituent allocators
        constituent_portfolios: List[Tuple[str, float, Portfolio]] = []
        
        for allocator_name, weight in self._allocator_weights.items():
            # Find the allocator by name
            found_allocator = None
            for allocator_data in self._app_instance.allocators_store.values():
                if allocator_data['instance'].get_name() == allocator_name:
                    found_allocator = allocator_data['instance']
                    break
            
            if not found_allocator:
                logger.warning(f"({self.get_name()}): Allocator '{allocator_name}' not found. Skipping.")
                continue
            
            try:
                # Compute portfolio for this allocator
                constituent_portfolio = found_allocator.compute_allocations(
                    fitting_start_date, fitting_end_date, test_end_date
                )
                constituent_portfolios.append((allocator_name, weight, constituent_portfolio))
                logger.info(f"({self.get_name()}): Got portfolio from '{allocator_name}' with weight {weight:.3f}")
                
            except Exception as e:
                logger.error(f"({self.get_name()}): Error computing portfolio for '{allocator_name}': {e}")
                continue
        
        if not constituent_portfolios:
            logger.warning(f"({self.get_name()}): No constituent portfolios available. Returning empty portfolio.")
            return Portfolio(start_date=fitting_end_date)
        
        # Merge the portfolios
        merged_portfolio = self._merge_portfolios(constituent_portfolios, fitting_end_date, test_end_date)
        
        logger.info(f"({self.get_name()}): Created merged portfolio from {len(constituent_portfolios)} constituent allocators")
        return merged_portfolio

    def _merge_portfolios(self, constituent_portfolios: List[Tuple[str, float, Portfolio]], 
                         start_date: date, end_date: date) -> Portfolio:
        """
        Merge multiple portfolios with weights into a single portfolio.
        """
        merged_portfolio = Portfolio(start_date=start_date)
        
        if end_date > start_date:
            # Combine allocations from all constituent portfolios
            merged_allocations: Dict[str, float] = {}
            
            for allocator_name, weight, portfolio in constituent_portfolios:
                # Get the segments up to end_date
                segments = portfolio.get(end_date)
                
                if segments:
                    # Use the last segment's allocations (most recent)
                    last_segment = segments[-1]
                    allocations = last_segment['allocations']
                    
                    # Add weighted allocations to merged result
                    for instrument, allocation in allocations.items():
                        if instrument not in merged_allocations:
                            merged_allocations[instrument] = 0.0
                        merged_allocations[instrument] += allocation * weight
                        
                    logger.debug(f"({self.get_name()}): Added allocations from '{allocator_name}' "
                               f"with weight {weight:.3f}: {allocations}")
            
            # Normalize allocations to ensure they sum to 1.0
            total_allocation = sum(merged_allocations.values())
            if total_allocation > 0:
                merged_allocations = {
                    instrument: allocation / total_allocation
                    for instrument, allocation in merged_allocations.items()
                }
            
            merged_portfolio.append(end_date=end_date, allocations=merged_allocations)
            
            logger.info(f"({self.get_name()}): Created merged segment from {start_date} to {end_date} "
                       f"with {len(merged_allocations)} instruments: {merged_allocations}")
        else:
            logger.warning(f"({self.get_name()}): end_date ({end_date}) is not after start_date ({start_date}). "
                          "Returning empty portfolio.")
        
        return merged_portfolio


class MergeAllocatorDialog(simpledialog.Dialog):
    def __init__(self, parent, title: str, app_instance,
                 initial_allocator_weights: Dict[str, float], 
                 initial_name: str):
        
        self.app_instance = app_instance
        self.initial_allocator_weights = initial_allocator_weights
        self.initial_name = initial_name
        self.name_var = tk.StringVar(value=self.initial_name)
        self.allocator_widgets: Dict[str, Dict[str, Any]] = {}
        self.allocator_id_counter = 0
        self.sum_label_var = tk.StringVar()
        self.sum_label_widget: Optional[ttk.Label] = None
        self.scrollable_frame_for_allocators: Optional[ttk.Frame] = None
        self.result_name: Optional[str] = None
        self.result_allocator_weights: Optional[Dict[str, float]] = None
        
        # Get available allocators (excluding merge allocators to avoid cycles)
        self.available_allocators = []
        for allocator_data in app_instance.allocators_store.values():
            allocator_instance = allocator_data['instance']
            # Exclude MergeAllocator instances to prevent circular dependencies
            if not isinstance(allocator_instance, MergeAllocator):
                self.available_allocators.append(allocator_instance.get_name())
        
        super().__init__(parent, title)

    def body(self, master_frame: tk.Frame) -> tk.Entry | None:
        master_frame.pack_configure(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Allocator name
        name_frame = ttk.Frame(master_frame)
        name_frame.pack(side="top", fill="x", pady=(0, 10))
        ttk.Label(name_frame, text="Allocator Name:").pack(side="left", padx=(0,5))
        self.name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=30)
        self.name_entry.pack(side="left", fill="x", expand=True)

        ttk.Separator(master_frame, orient='horizontal').pack(side="top", fill='x', pady=5)
        
        # Check if there are available allocators
        if not self.available_allocators:
            ttk.Label(master_frame, 
                     text="No allocators available to merge.\nCreate some allocators first.", 
                     font=('Helvetica', 10, 'italic')).pack(pady=20)
            return self.name_entry
        
        # Allocator weights area
        allocator_area_label_frame = ttk.LabelFrame(master_frame, text="Allocator Weights")
        allocator_area_label_frame.pack(side="top", fill="both", expand=True, pady=5)
        
        add_allocator_button = ttk.Button(allocator_area_label_frame, 
                                        text="Add Allocator", 
                                        command=self._add_allocator_row_ui)
        add_allocator_button.pack(pady=5, anchor="nw")

        # Scrollable area for allocator selection
        controls_canvas = tk.Canvas(allocator_area_label_frame, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(allocator_area_label_frame, orient="vertical", command=controls_canvas.yview)
        self.scrollable_frame_for_allocators = ttk.Frame(controls_canvas)
        
        self.scrollable_frame_for_allocators.bind(
            "<Configure>", lambda e: controls_canvas.configure(scrollregion=controls_canvas.bbox("all"))
        )
        controls_canvas.create_window((0, 0), window=self.scrollable_frame_for_allocators, anchor="nw")
        controls_canvas.configure(yscrollcommand=scrollbar.set)

        # Header
        header_frame = ttk.Frame(self.scrollable_frame_for_allocators)
        header_frame.pack(fill="x")
        ttk.Label(header_frame, text="Allocator", font=('Helvetica', 9, 'bold')).pack(side="left", padx=5, pady=2, expand=True, fill="x")
        ttk.Label(header_frame, text="Weight", font=('Helvetica', 9, 'bold')).pack(side="left", padx=5, pady=2, expand=True, fill="x")
        ttk.Label(header_frame, text="Actions", font=('Helvetica', 9, 'bold')).pack(side="left", padx=5, pady=2, ipadx=10)

        controls_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Add existing allocator weights
        for allocator_name, weight in self.initial_allocator_weights.items():
            if allocator_name in self.available_allocators:
                self._add_allocator_row_ui(allocator_name=allocator_name, weight=weight)
        
        # Add one empty row if no initial weights
        if not self.initial_allocator_weights:
            self._add_allocator_row_ui()

        # Sum display
        sum_frame = ttk.Frame(master_frame)
        sum_frame.pack(side="top", fill="x", pady=(10,0), anchor="sw")
        ttk.Label(sum_frame, text="Total Weight:").pack(side="left", padx=5)
        self.sum_label_widget = ttk.Label(sum_frame, textvariable=self.sum_label_var)
        self.sum_label_widget.pack(side="left")
        self._update_sum_and_validate()
        
        return self.name_entry

    def _add_allocator_row_ui(self, allocator_name: str = "", weight: float = 0.0):
        if self.scrollable_frame_for_allocators is None:
            return

        allocator_id = f"alloc_{self.allocator_id_counter}"
        self.allocator_id_counter += 1
        row_frame = ttk.Frame(self.scrollable_frame_for_allocators)
        row_frame.pack(fill="x", pady=1)

        # Allocator selection dropdown
        allocator_var = tk.StringVar(value=allocator_name)
        allocator_combo = ttk.Combobox(row_frame, textvariable=allocator_var, 
                                     values=self.available_allocators, 
                                     state='readonly', width=25)
        allocator_combo.pack(side="left", padx=5, fill="x", expand=True)
        allocator_combo.bind("<<ComboboxSelected>>", lambda e: self._update_sum_and_validate())

        # Weight entry
        weight_var = tk.StringVar(value=f"{weight:.3f}" if weight > 0 else "")
        weight_entry = ttk.Entry(row_frame, textvariable=weight_var, width=10, validate="key")
        vcmd = (weight_entry.register(self._validate_weight_input), '%P', weight_entry)
        weight_entry.configure(validatecommand=vcmd)
        weight_entry.pack(side="left", padx=5, fill="x", expand=True)
        weight_entry.bind("<KeyRelease>", lambda e: self._update_sum_and_validate())
        weight_entry.bind("<FocusOut>", lambda e, current_entry=weight_entry: self._format_weight_entry_on_focus_out(current_entry))

        # Delete button
        del_btn = ttk.Button(row_frame, text="Del", width=4, style="Danger.Toolbutton.TButton",
                           command=lambda a_id=allocator_id: self._delete_allocator_row_ui(a_id))
        del_btn.pack(side="left", padx=(0, 2))

        self.allocator_widgets[allocator_id] = {
            'frame': row_frame, 
            'allocator_var': allocator_var, 
            'allocator_combo': allocator_combo,
            'weight_var': weight_var, 
            'weight_entry': weight_entry
        }
        
        self.scrollable_frame_for_allocators.update_idletasks()
        if not allocator_name:
            allocator_combo.focus_set()
        self._update_sum_and_validate()
        return row_frame

    def _delete_allocator_row_ui(self, allocator_id_to_delete: str):
        if allocator_id_to_delete in self.allocator_widgets:
            self.allocator_widgets[allocator_id_to_delete]['frame'].destroy()
            del self.allocator_widgets[allocator_id_to_delete]
            self._update_sum_and_validate()
            if not self.allocator_widgets:
                self._add_allocator_row_ui()

    def _format_weight_entry_on_focus_out(self, entry_widget: ttk.Entry):
        try:
            val_str = entry_widget.get()
            if val_str:
                formatted_val = f"{float(val_str):.3f}"
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, formatted_val)
            else:
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, "0.000")
        except ValueError:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, "0.000")
        self._update_sum_and_validate()

    def _validate_weight_input(self, P: str, entry_widget: ttk.Entry) -> bool:
        if P == "" or P == ".":
            return True
        try:
            float(P)
            return True
        except ValueError:
            if P.count('.') <= 1 and all(c.isdigit() or c == '.' for c in P if c):
                return True
            return False

    def _update_sum_and_validate(self):
        current_sum = 0.0
        all_weight_entries_valid = True
        selected_allocators: Dict[str, int] = {}
        
        for row_widgets in self.allocator_widgets.values():
            allocator_combo = row_widgets['allocator_combo']
            weight_entry = row_widgets['weight_entry']
            
            allocator_name = allocator_combo.get().strip()
            if allocator_name:
                selected_allocators[allocator_name] = selected_allocators.get(allocator_name, 0) + 1
            
            try:
                weight_str = weight_entry.get()
                if weight_str:
                    current_sum += float(weight_str)
            except ValueError:
                all_weight_entries_valid = False
                weight_entry.config(style="Error.TEntry")

        # Check for duplicate allocator selections
        for row_widgets in self.allocator_widgets.values():
            allocator_combo = row_widgets['allocator_combo']
            allocator_name = allocator_combo.get().strip()
            is_duplicate = allocator_name and selected_allocators.get(allocator_name, 0) > 1
            # Note: Can't easily change combobox style, so we'll handle this in validation

        self.sum_label_var.set(f"{current_sum:.3f}" if all_weight_entries_valid else "Format Error")
        if self.sum_label_widget:
            if not all_weight_entries_valid:
                self.sum_label_widget.configure(foreground="magenta")
            elif abs(current_sum - 1.0) < 1e-6 and current_sum > 0:
                self.sum_label_widget.configure(foreground="darkgreen")
            elif current_sum == 0:
                self.sum_label_widget.configure(foreground="black")
            else:
                self.sum_label_widget.configure(foreground="red")

    def validate(self) -> bool:
        merge_allocator_name = self.name_var.get().strip()
        if not merge_allocator_name:
            messagebox.showerror("Validation Error", "Allocator Name cannot be empty.", parent=self)
            if self.name_entry:
                self.name_entry.focus_set()
            return False
        
        temp_allocator_weights: Dict[str, float] = {}
        selected_allocators_for_duplicate_check: Dict[str, int] = {}
        focused_error_widget = False

        if not self.allocator_widgets:
            messagebox.showerror("Validation Error", "No allocators specified for merging.", parent=self)
            return False

        for row_widgets in self.allocator_widgets.values():
            allocator_combo = row_widgets['allocator_combo']
            weight_entry = row_widgets['weight_entry']
            
            allocator_name = allocator_combo.get().strip()
            if not allocator_name:
                weight_str = weight_entry.get().strip()
                if weight_str and float(weight_str) != 0.0:
                    messagebox.showerror("Validation Error", "Weight specified without selecting allocator.", parent=self)
                    if not focused_error_widget:
                        allocator_combo.focus_set()
                        focused_error_widget = True
                    return False
                continue

            # Check for duplicates
            selected_allocators_for_duplicate_check[allocator_name] = selected_allocators_for_duplicate_check.get(allocator_name, 0) + 1
            if selected_allocators_for_duplicate_check[allocator_name] > 1:
                messagebox.showerror("Validation Error", f"Allocator '{allocator_name}' selected multiple times.", parent=self)
                if not focused_error_widget:
                    allocator_combo.focus_set()
                    focused_error_widget = True
                return False

            try:
                weight_str = weight_entry.get()
                weight = float(weight_str) if weight_str.strip() else 0.0
                if weight < 0.0:
                    messagebox.showerror("Validation Error", f"Weight for '{allocator_name}' must be non-negative.", parent=self)
                    if not focused_error_widget:
                        weight_entry.focus_set()
                        focused_error_widget = True
                        weight_entry.config(style="Error.TEntry")
                    return False
                if weight > 0:
                    temp_allocator_weights[allocator_name] = weight
                weight_entry.config(style="TEntry")
            except ValueError:
                messagebox.showerror("Validation Error", f"Invalid weight for '{allocator_name}': '{weight_entry.get()}'.", parent=self)
                if not focused_error_widget:
                    weight_entry.focus_set()
                    focused_error_widget = True
                    weight_entry.config(style="Error.TEntry")
                return False

        if focused_error_widget:
            return False

        if not temp_allocator_weights:
            messagebox.showerror("Validation Error", "At least one allocator must have a positive weight.", parent=self)
            return False

        current_sum = sum(temp_allocator_weights.values())
        if abs(current_sum - 1.0) > 1e-6:
            proceed = messagebox.askokcancel("Weight Warning", 
                                           f"Weights sum to {current_sum:.3f}, not 1.0. "
                                           f"Weights will be normalized. Continue?", 
                                           icon=messagebox.WARNING, parent=self)
            if not proceed:
                return False

        self.result_name = merge_allocator_name
        self.result_allocator_weights = temp_allocator_weights
        logger.debug(f"MergeAllocatorDialog validation success: name={self.result_name}, weights={self.result_allocator_weights}")
        return True

    def apply(self) -> None:
        pass  # Results set in validate()

    def buttonbox(self) -> None:
        box = ttk.Frame(self)
        self.ok_button = ttk.Button(box, text="Save Allocator", width=15, command=self.ok, default=tk.ACTIVE)
        self.ok_button.pack(side=tk.LEFT, padx=5, pady=5)
        cancel_button = ttk.Button(box, text="Cancel", width=10, command=self.cancel)
        cancel_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack(side=tk.BOTTOM, pady=5)