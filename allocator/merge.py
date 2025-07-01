from typing import Dict, Set, Optional, Type, Any, List
from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import uuid

from .allocator import PortfolioAllocator, AllocatorState
from portfolio import Portfolio


class MergeAllocatorConfigDialog(simpledialog.Dialog):
    def __init__(self, parent, title, available_allocators: List[PortfolioAllocator], existing_state=None):
        self.available_allocators = available_allocators
        self.existing_state = existing_state or {}
        self.result = None
        self.allocator_weights = {}
        self.allocator_vars = {}
        super().__init__(parent, title)

    def body(self, master):
        # Name field
        ttk.Label(master, text="Name:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.name_var = tk.StringVar(value=self.existing_state.get('name', ''))
        self.name_entry = ttk.Entry(master, textvariable=self.name_var, width=30)
        self.name_entry.grid(row=0, column=1, columnspan=2, sticky='ew', padx=5, pady=5)

        # Allocator selection frame
        ttk.Label(master, text="Select Allocators and Weights:").grid(row=1, column=0, columnspan=3, sticky='w', padx=5, pady=(10, 5))
        
        # Scrollable frame for allocators
        canvas = tk.Canvas(master, height=200)
        scrollbar = ttk.Scrollbar(master, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.grid(row=2, column=0, columnspan=2, sticky='nsew', padx=5, pady=5)
        scrollbar.grid(row=2, column=2, sticky='ns', pady=5)
        
        # Populate allocator selection
        existing_allocator_weights = self.existing_state.get('allocator_weights', {})
        
        for i, allocator in enumerate(self.available_allocators):
            allocator_name = allocator.get_name()
            
            # Checkbox for selection
            var = tk.BooleanVar(value=allocator_name in existing_allocator_weights)
            self.allocator_vars[allocator_name] = var
            
            checkbox = ttk.Checkbutton(
                scrollable_frame, 
                text=allocator_name, 
                variable=var,
                command=lambda name=allocator_name: self._on_allocator_toggle(name)
            )
            checkbox.grid(row=i, column=0, sticky='w', padx=5, pady=2)
            
            # Weight entry
            weight = existing_allocator_weights.get(allocator_name, 0.0)
            weight_var = tk.DoubleVar(value=weight)
            self.allocator_weights[allocator_name] = weight_var
            
            weight_entry = ttk.Entry(scrollable_frame, textvariable=weight_var, width=10)
            weight_entry.grid(row=i, column=1, padx=5, pady=2)
            
            ttk.Label(scrollable_frame, text="Weight").grid(row=i, column=2, sticky='w', padx=5, pady=2)
        
        # Total weight label
        self.total_weight_var = tk.StringVar()
        ttk.Label(master, text="Total Weight:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.total_weight_label = ttk.Label(master, textvariable=self.total_weight_var)
        self.total_weight_label.grid(row=3, column=1, sticky='w', padx=5, pady=5)
        
        # Update total weight initially
        self._update_total_weight()
        
        # Bind weight changes to update total
        for weight_var in self.allocator_weights.values():
            weight_var.trace('w', lambda *args: self._update_total_weight())
        
        master.grid_columnconfigure(1, weight=1)
        return self.name_entry

    def _on_allocator_toggle(self, allocator_name):
        """Handle allocator checkbox toggle"""
        if not self.allocator_vars[allocator_name].get():
            # If unchecked, set weight to 0
            self.allocator_weights[allocator_name].set(0.0)
        else:
            # If checked and weight is 0, set to some default
            if self.allocator_weights[allocator_name].get() == 0.0:
                self.allocator_weights[allocator_name].set(0.1)

    def _update_total_weight(self):
        """Update the total weight display"""
        total = sum(var.get() for var in self.allocator_weights.values())
        self.total_weight_var.set(f"{total:.3f}")
        
        # Change color based on whether total is close to 1.0
        if abs(total - 1.0) < 0.001:
            self.total_weight_label.config(foreground='green')
        else:
            self.total_weight_label.config(foreground='red')

    def validate(self):
        """Validate the input before accepting"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Name cannot be empty.", parent=self)
            return False
        
        # Check that at least one allocator is selected
        selected_allocators = {}
        for name, var in self.allocator_vars.items():
            if var.get():
                weight_value = self.allocator_weights[name].get()
                if weight_value > 0:
                    selected_allocators[name] = weight_value
        
        if not selected_allocators:
            messagebox.showerror("Error", "Please select at least one allocator with a positive weight.", parent=self)
            return False
        
        # Check that weights sum to 1.0 (within tolerance)
        total_weight = sum(selected_allocators.values())
        if abs(total_weight - 1.0) > 0.001:
            messagebox.showerror("Error", f"Weights must sum to 1.0. Current total: {total_weight:.3f}", parent=self)
            return False
        
        return True

    def apply(self):
        """Apply the configuration"""
        selected_allocators = {}
        for name, var in self.allocator_vars.items():
            if var.get():
                weight_value = self.allocator_weights[name].get()
                if weight_value > 0:
                    selected_allocators[name] = weight_value
        
        self.result = {
            'name': self.name_var.get().strip(),
            'allocator_weights': selected_allocators
        }


class MergeAllocator(PortfolioAllocator):
    """
    An allocator that combines multiple other allocators with specified weights.
    """
    
    def __init__(self, allocator_manager=None, **state: AllocatorState):
        """
        Initialize the MergeAllocator.
        
        Args:
            allocator_manager: Reference to the AllocatorManager instance
            **state: State dictionary containing 'name' and 'allocator_weights'
        """
        super().__init__(**state)
        self.allocator_manager = allocator_manager
        
        # Validate required state
        if 'allocator_weights' not in state:
            raise ValueError("MergeAllocator state must include 'allocator_weights'.")
        
        self.allocator_weights = state['allocator_weights']
        
        # Validate weights sum to 1.0
        total_weight = sum(self.allocator_weights.values())
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(f"Allocator weights must sum to 1.0, got {total_weight}")

    def get_state(self) -> AllocatorState:
        """Return the current state of the allocator"""
        return self._state.copy()

    @classmethod
    def configure(
        cls: Type['MergeAllocator'],
        parent_window: tk.Misc,
        existing_state: Optional[AllocatorState] = None,
        available_allocators: Optional[List[PortfolioAllocator]] = None
    ) -> Optional[AllocatorState]:
        """
        Configure the MergeAllocator through a dialog.
        
        Args:
            parent_window: Parent window for the dialog
            existing_state: Existing state to edit (None for new allocator)
            available_allocators: List of available allocators to choose from
        
        Returns:
            New state dictionary or None if cancelled
        """
        if not available_allocators:
            messagebox.showerror("Error", "No allocators available to merge.", parent=parent_window)
            return None
        
        dialog = MergeAllocatorConfigDialog(
            parent_window, 
            "Configure Merge Allocator", 
            available_allocators,
            existing_state
        )
        
        return dialog.result

    def _compute_allocations_impl(self, fitting_start_date: date, fitting_end_date: date, test_end_date: date) -> Portfolio:
        """
        Compute allocations by combining the allocations from constituent allocators.
        Uses the Portfolio.merge() function for proper portfolio combination.
        """
        if not self.allocator_manager:
            raise RuntimeError("MergeAllocator requires a reference to AllocatorManager")
        
        # Get all constituent portfolios with their weights
        portfolios_with_weights = []
        for allocator_name, weight in self.allocator_weights.items():
            if weight <= 0:
                continue
                
            # Find the allocator by name (only in regular allocators store to avoid circular deps)
            allocator_data = None
            for data in self.allocator_manager.allocators_store.values():
                if data['instance'].get_name() == allocator_name:
                    allocator_data = data
                    break
            
            if not allocator_data:
                continue
                
            allocator = allocator_data['instance']
            
            # Compute the allocator's portfolio
            try:
                allocator_portfolio = allocator.compute_allocations(fitting_start_date, fitting_end_date, test_end_date)
                portfolios_with_weights.append((allocator_portfolio, weight))
            except Exception as e:
                continue
        
        if not portfolios_with_weights:
            # Return empty portfolio if no constituents
            portfolio = Portfolio(fitting_start_date)
            portfolio.append(fitting_end_date, {})
            return portfolio
        
        # The merge allocator should create a portfolio that covers the test period
        # from fitting_end_date to test_end_date, just like other allocators
        
        # Use Portfolio.merge() to properly combine the portfolios
        # Use the correct date range: fitting_end_date to test_end_date
        try:
            merged_portfolio = Portfolio.merge(portfolios_with_weights, fitting_end_date, test_end_date)
            return merged_portfolio
        except Exception as e:
            # Fallback to empty portfolio with correct date range
            portfolio = Portfolio(fitting_end_date)
            portfolio.append(test_end_date, {})
            return portfolio

    def get_instruments(self) -> Set[str]:
        """
        Get the combined set of instruments from all constituent allocators.
        """
        instruments = set()
        
        if not self.allocator_manager:
            return instruments
            
        for allocator_name in self.allocator_weights.keys():
            allocator_data = self.allocator_manager.get_allocator_by_name(allocator_name)
            if allocator_data:
                allocator = allocator_data['instance']
                instruments.update(allocator.get_instruments())
        
        return instruments