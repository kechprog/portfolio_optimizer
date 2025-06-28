import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import uuid
import logging
from typing import Dict, Any, List, Set, Type, Optional

from allocator.allocator import PortfolioAllocator
from allocator.manual import ManualAllocator
from allocator.mpt.max_sharpe import MaxSharpeAllocator
from allocator.mpt.min_volatility import MinVolatilityAllocator
from portfolio import Portfolio

logger = logging.getLogger(__name__)

GEAR_ICON = "\u2699"
DELETE_ICON = "\u2716"


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
        self.type_combo = ttk.Combobox(master, textvariable=self.type_var, 
                                       values=self.type_names, state='readonly')
        self.type_combo.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(master, text="Name:").grid(row=1, column=0, sticky='w')
        self.name_var = tk.StringVar(value=self.initial_name)
        self.name_entry = ttk.Entry(master, textvariable=self.name_var)
        self.name_entry.grid(row=1, column=1, padx=5, pady=5)
        return self.name_entry

    def apply(self):
        self.result = (self.type_var.get(), self.name_var.get())


class AllocatorManager(ttk.Frame):
    def __init__(self, parent, json_state=None, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.available_allocator_types: Dict[str, Type[PortfolioAllocator]] = {
            "Manual Allocator": ManualAllocator,
            "Max Sharpe": MaxSharpeAllocator,
            "Min Volatility": MinVolatilityAllocator,
        }
        
        self.allocators_store: Dict[str, Dict[str, Any]] = {}
        self.status_callback = None
        
        self._create_ui()
        
        if json_state:
            self._load_from_state(json_state)
        else:
            self._redraw_allocator_list_ui()

    def set_status_callback(self, callback):
        """Set the callback function for status updates"""
        self.status_callback = callback

    def _set_status(self, message: str, error: bool = False, success: bool = False):
        """Internal status setting with fallback"""
        if self.status_callback:
            self.status_callback(message, error=error, success=success)
        else:
            print(f"Status: {message}")

    def _create_ui(self):
        # Top bar with allocator type selection and create button
        top_bar = ttk.Frame(self)
        top_bar.pack(fill="x", pady=(0, 5))
        
        ttk.Label(top_bar, text="Allocator Type:").pack(side="left", padx=(0, 5))
        
        self.new_allocator_type_var = tk.StringVar()
        self.new_allocator_type_combo = ttk.Combobox(
            top_bar, 
            textvariable=self.new_allocator_type_var,
            values=list(self.available_allocator_types.keys()), 
            state="readonly", 
            width=20
        )
        if self.available_allocator_types:
            self.new_allocator_type_combo.current(0)
        self.new_allocator_type_combo.pack(side="left", padx=(0, 10))
        
        ttk.Button(
            top_bar, 
            text="Create Allocator", 
            command=self._on_create_allocator_button_click,
            style="Success.TButton"
        ).pack(side="left")

        # Scrollable list area for allocators
        list_area = ttk.Frame(self)
        list_area.pack(fill="both", expand=True, pady=5)
        
        self.allocators_canvas = tk.Canvas(list_area, borderwidth=0, highlightthickness=0)
        self.allocators_list_scrollframe = ttk.Frame(self.allocators_canvas)
        
        scrollbar = ttk.Scrollbar(list_area, orient="vertical", command=self.allocators_canvas.yview)
        self.allocators_canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        self.allocators_canvas.pack(side="left", fill="both", expand=True)
        self.allocators_canvas.create_window((0, 0), window=self.allocators_list_scrollframe, anchor="nw")
        
        self.allocators_list_scrollframe.bind(
            "<Configure>", 
            lambda e: self.allocators_canvas.configure(scrollregion=self.allocators_canvas.bbox("all"))
        )

    def _redraw_allocator_list_ui(self):
        """Redraw the allocator list UI"""
        for widget in self.allocators_list_scrollframe.winfo_children():
            widget.destroy()
        
        sorted_allocator_items = sorted(
            self.allocators_store.items(), 
            key=lambda item: item[1]['instance'].get_name().lower()
        )
        
        for allocator_id, data in sorted_allocator_items:
            allocator_instance = data['instance']
            is_enabled_var = data['is_enabled_var']
            
            row_frame = ttk.Frame(self.allocators_list_scrollframe)
            row_frame.pack(fill="x", pady=2, padx=2)
            
            # Enabled checkbox
            chk = ttk.Checkbutton(
                row_frame, 
                variable=is_enabled_var, 
                text="", 
                command=self._on_allocator_enable_changed
            )
            chk.pack(side="left", padx=(0, 2))
            
            # Name label
            name_label = ttk.Label(
                row_frame, 
                text=allocator_instance.get_name(), 
                width=20, 
                anchor="w", 
                relief="groove", 
                padding=2
            )
            name_label.pack(side="left", padx=2, fill="x", expand=True)
            
            # Configure button
            config_btn = ttk.Button(
                row_frame, 
                text=GEAR_ICON, 
                width=3, 
                style="Toolbutton.TButton",
                command=lambda aid=allocator_id: self._on_configure_existing_allocator(aid)
            )
            config_btn.pack(side="left", padx=2)

            # Duplicate button
            duplicate_btn = ttk.Button(
                row_frame, 
                text="⧉", 
                width=3, 
                style="Toolbutton.TButton",
                command=lambda aid=allocator_id: self._on_duplicate_allocator_prompt(aid)
            )
            duplicate_btn.pack(side="left", padx=2)

            # Delete button
            del_btn = ttk.Button(
                row_frame, 
                text=DELETE_ICON, 
                width=3, 
                style="Danger.Toolbutton.TButton",
                command=lambda aid=allocator_id: self._on_delete_allocator(aid)
            )
            del_btn.pack(side="left", padx=2)
        
        self.allocators_list_scrollframe.update_idletasks()
        self.allocators_canvas.configure(scrollregion=self.allocators_canvas.bbox("all"))

    def _on_allocator_enable_changed(self):
        """Handle allocator enable/disable changes"""
        self._set_status("Allocator enabled/disabled. Click 'FIT & PLOT' to see changes.")

    def _on_create_allocator_button_click(self):
        """Handle create allocator button click"""
        allocator_type_name = self.new_allocator_type_var.get()
        if not allocator_type_name:
            messagebox.showwarning(
                "Create Allocator", 
                "Please select an allocator type.", 
                parent=self.winfo_toplevel()
            )
            return
        
        AllocatorClass = self.available_allocator_types.get(allocator_type_name)
        if not AllocatorClass:
            messagebox.showerror(
                "Error", 
                f"Unknown allocator type: {allocator_type_name}", 
                parent=self.winfo_toplevel()
            )
            return

        new_allocator_state = AllocatorClass.configure(
            parent_window=self.winfo_toplevel(), 
            existing_state=None
        )

        if new_allocator_state:
            try:
                new_allocator_name = str(new_allocator_state.get('name', ''))
                if not new_allocator_name:
                    messagebox.showerror(
                        "Create Allocator", 
                        "Allocator configuration did not return a valid name.", 
                        parent=self.winfo_toplevel()
                    )
                    return

                new_name_lower = new_allocator_name.lower()
                for data in self.allocators_store.values():
                    if data['instance'].get_name().lower() == new_name_lower:
                        messagebox.showerror(
                            "Create Allocator", 
                            f"An allocator with the name '{new_allocator_name}' already exists.", 
                            parent=self.winfo_toplevel()
                        )
                        return
                
                new_allocator_instance = AllocatorClass(**new_allocator_state)
            except Exception as e:
                messagebox.showerror(
                    "Create Allocator", 
                    f"Failed to create allocator instance: {e}", 
                    parent=self.winfo_toplevel()
                )
                self._set_status(f"Error creating {allocator_type_name}: {e}", error=True)
                return

            allocator_id = str(uuid.uuid4())
            self.allocators_store[allocator_id] = {
                'instance': new_allocator_instance, 
                'is_enabled_var': tk.BooleanVar(value=True)
            }
            self._set_status(f"Allocator '{new_allocator_instance.get_name()}' created.", success=True)
            self._redraw_allocator_list_ui()
        else: 
            self._set_status(f"Allocator creation cancelled for '{allocator_type_name}'.")

    def _on_configure_existing_allocator(self, allocator_id_to_configure: str):
        """Handle configure existing allocator"""
        data_to_configure = self.allocators_store.get(allocator_id_to_configure)
        if not data_to_configure:
            messagebox.showerror(
                "Error", 
                "Allocator not found for configuration.", 
                parent=self.winfo_toplevel()
            )
            return
        
        existing_instance = data_to_configure['instance']
        AllocatorClass = type(existing_instance)
        existing_state = existing_instance.get_state()

        new_state_from_config = AllocatorClass.configure(
            parent_window=self.winfo_toplevel(), 
            existing_state=existing_state
        )

        if new_state_from_config:
            try:
                new_allocator_name = str(new_state_from_config.get('name', ''))
                if not new_allocator_name:
                    messagebox.showerror(
                        "Configure Allocator", 
                        "Allocator configuration did not return a valid name.", 
                        parent=self.winfo_toplevel()
                    )
                    return

                new_name_lower = new_allocator_name.lower()
                for aid, data in self.allocators_store.items():
                    if aid != allocator_id_to_configure and data['instance'].get_name().lower() == new_name_lower:
                        messagebox.showerror(
                            "Configure Allocator", 
                            f"An allocator with the name '{new_allocator_name}' already exists (used by another allocator).", 
                            parent=self.winfo_toplevel()
                        )
                        return
                
                reconfigured_instance = AllocatorClass(**new_state_from_config)
            except Exception as e:
                messagebox.showerror(
                    "Configure Allocator", 
                    f"Failed to reconfigure allocator instance: {e}", 
                    parent=self.winfo_toplevel()
                )
                self._set_status(f"Error reconfiguring {existing_instance.get_name()}: {e}", error=True)
                return

            self.allocators_store[allocator_id_to_configure]['instance'] = reconfigured_instance
            self._set_status(f"Allocator '{reconfigured_instance.get_name()}' reconfigured.", success=True)
            self._redraw_allocator_list_ui()
        else:
            self._set_status(f"Reconfiguration of '{existing_instance.get_name()}' cancelled.")

    def _on_delete_allocator(self, allocator_id_to_delete: str):
        """Handle delete allocator"""
        if allocator_id_to_delete in self.allocators_store:
            allocator_name = self.allocators_store[allocator_id_to_delete]['instance'].get_name()
            if messagebox.askyesno(
                "Confirm Delete", 
                f"Are you sure you want to delete allocator '{allocator_name}'?", 
                parent=self.winfo_toplevel()
            ):
                del self.allocators_store[allocator_id_to_delete]
                self._set_status(f"Allocator '{allocator_name}' deleted.", success=True)
                self._redraw_allocator_list_ui()
        else:
            messagebox.showerror(
                "Error", 
                "Allocator not found for deletion.", 
                parent=self.winfo_toplevel()
            )

    def _on_duplicate_allocator_prompt(self, allocator_id_to_duplicate: str):
        """Handle duplicate allocator prompt"""
        data = self.allocators_store.get(allocator_id_to_duplicate)
        if not data:
            messagebox.showerror(
                "Duplicate Error", 
                "Allocator not found for duplication.", 
                parent=self.winfo_toplevel()
            )
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
            self.winfo_toplevel(),
            "Duplicate Allocator",
            type_names,
            current_type,
            initial_name
        )
        
        if not dialog.result:
            self._set_status("Allocator duplication cancelled.")
            return
        
        chosen_type, new_name = dialog.result

        new_state = dict(original_state)
        new_state['name'] = new_name
        
        try:
            AllocatorClass = self.available_allocator_types[chosen_type]
            new_instance = AllocatorClass(**new_state)
        except Exception as e:
            messagebox.showerror(
                "Duplicate Error", 
                f"Failed to duplicate allocator: {e}", 
                parent=self.winfo_toplevel()
            )
            return

        new_alloc_id = str(uuid.uuid4())
        self.allocators_store[new_alloc_id] = {
            'instance': new_instance,
            'is_enabled_var': tk.BooleanVar(value=True)
        }
        self._set_status(f"Allocator '{new_name}' duplicated as {chosen_type}.", success=True)
        self._redraw_allocator_list_ui()

    def get_state(self) -> Dict[str, Any]:
        """Get the state of all allocators including sub-components"""
        state = {
            "allocators": []
        }

        for aid, data in self.allocators_store.items():
            instance = data['instance']
            allocator_type_name = None
            
            for type_name_key, AllocatorClassInMap in self.available_allocator_types.items():
                if isinstance(instance, AllocatorClassInMap):
                    allocator_type_name = type_name_key
                    break
            
            if not allocator_type_name:
                logger.warning(f"Type for allocator '{instance.get_name()}' not found. Skipping save of this allocator.")
                continue

            allocator_state_to_save = instance.get_state()
            state["allocators"].append({
                "id": aid, 
                "type_name": allocator_type_name, 
                "is_enabled": data['is_enabled_var'].get(),
                "allocator_state": allocator_state_to_save 
            })
        
        return state

    def get_portfolios(self) -> List[Portfolio]:
        """Get list of all portfolios computed by enabled allocators"""
        portfolios = []
        
        for data in self.allocators_store.values():
            if data['is_enabled_var'].get():  # Only include enabled allocators
                allocator = data['instance']
                portfolio = getattr(allocator, '_last_computed_portfolio', None)
                if portfolio and isinstance(portfolio, Portfolio):
                    portfolios.append(portfolio)
        
        return portfolios

    def get_allocator_names_with_portfolios(self) -> List[str]:
        """Get list of allocator names that have computed portfolios"""
        names = []
        
        for data in self.allocators_store.values():
            if data['is_enabled_var'].get():  # Only include enabled allocators
                allocator = data['instance']
                portfolio = getattr(allocator, '_last_computed_portfolio', None)
                if portfolio and isinstance(portfolio, Portfolio):
                    names.append(allocator.get_name())
        
        return sorted(names)

    def get_enabled_allocators_data(self) -> List[Dict[str, Any]]:
        """Get data for enabled allocators for plotting purposes"""
        enabled_allocators_data = []
        
        for aid, data in self.allocators_store.items():
            if data['is_enabled_var'].get():
                allocator = data['instance']
                enabled_allocators_data.append({
                    'id': aid,
                    'instance': allocator, 
                    'is_enabled_var': data['is_enabled_var']
                })
        
        return enabled_allocators_data

    def get_allocator_names(self) -> List[str]:
        """Get sorted list of allocator names"""
        return sorted([data['instance'].get_name() for data in self.allocators_store.values()])

    def get_allocator_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get allocator data by name"""
        for data in self.allocators_store.values():
            if data['instance'].get_name() == name:
                return data
        return None

    def _load_from_state(self, json_state: Dict[str, Any]):
        """Load allocators from JSON state"""
        self.allocators_store.clear()
        
        for saved_alloc_data in json_state.get("allocators", []):
            allocator_type_name = saved_alloc_data.get("type_name")
            AllocatorClass = self.available_allocator_types.get(allocator_type_name)
            
            if not AllocatorClass: 
                logger.warning(f"Unknown allocator type '{allocator_type_name}' in saved state. Skipping.")
                continue
            
            allocator_state_from_save = saved_alloc_data.get("allocator_state")
            if not allocator_state_from_save or not isinstance(allocator_state_from_save, dict):
                logger.warning(f"Missing/invalid 'allocator_state' for type '{allocator_type_name}' in saved state. Skipping.")
                continue
            
            if 'name' not in allocator_state_from_save:
                allocator_state_from_save['name'] = f"Unnamed {allocator_type_name} {str(uuid.uuid4())[:4]}"
            
            if 'instruments' in allocator_state_from_save and isinstance(allocator_state_from_save['instruments'], list):
                allocator_state_from_save['instruments'] = set(allocator_state_from_save['instruments'])

            allocator_id = saved_alloc_data.get("id", str(uuid.uuid4()))
            
            try:
                new_instance = AllocatorClass(**allocator_state_from_save)
            except Exception as e: 
                loaded_name = allocator_state_from_save.get('name', 'unknown allocator')
                logger.error(f"Failed to initialize allocator '{loaded_name}' from saved state: {e}", exc_info=True)
                self._set_status(f"Error loading {loaded_name}: {e}", error=True)
                continue
            
            if new_instance: 
                self.allocators_store[allocator_id] = {
                    'instance': new_instance, 
                    'is_enabled_var': tk.BooleanVar(value=saved_alloc_data.get("is_enabled", True))
                }
        
        self._redraw_allocator_list_ui()