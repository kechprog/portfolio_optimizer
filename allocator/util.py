
# portfolio_optimizer/allocator/util.py
import tkinter as tk
from tkinter import ttk
from typing import List, Set, Dict, Any, Optional

class InstrumentListManagerWidget(ttk.Frame):
    """
    A reusable widget for managing a list of instrument tickers.
    Provides UI for adding, displaying, and removing instruments.
    """
    def __init__(self, parent: tk.Misc, initial_instruments_list: Optional[List[str]] = None):
        super().__init__(parent)
        
        if initial_instruments_list is None:
            self.initial_instruments_list = []
        else:
            self.initial_instruments_list = initial_instruments_list

        self.instrument_rows_data: List[Dict[str, Any]] = []
        # Each dict: {'frame': ttk.Frame, 'name_var': tk.StringVar, 'entry': ttk.Entry, 'button': ttk.Button}

        self._build_ui()
        self._populate_initial_instruments()

    def _build_ui(self):
        """Constructs the UI elements for the widget."""
        # Frame to hold the list of instrument rows (scrollable if many)
        # For simplicity, direct packing here. For scrollability, a Canvas would be needed.
        self.instrument_list_display_frame = ttk.Frame(self)
        self.instrument_list_display_frame.pack(side="top", fill="both", expand=True, padx=0, pady=0)

        # "Add Instrument" Button Frame and Button
        add_button_frame = ttk.Frame(self)
        add_button_frame.pack(side="top", fill="x", pady=(5,0)) # Place button below list
        
        self.add_instrument_button = ttk.Button(add_button_frame, text="Add Instrument",
                                           command=self._add_instrument_row_ui_event)
        self.add_instrument_button.pack(pady=2) # Center button in its frame

    def _populate_initial_instruments(self):
        """Adds UI rows for any initial instruments provided."""
        if not self.initial_instruments_list:
            # Add one blank row if no initial instruments are provided, to guide the user
            self._add_instrument_row_ui()
        else:
            for ticker in self.initial_instruments_list:
                self._add_instrument_row_ui(instrument_name_initial=ticker)
    
    def _add_instrument_row_ui_event(self):
        """Handles the click event of the 'Add Instrument' button."""
        new_entry = self._add_instrument_row_ui()
        if new_entry:
            new_entry.focus_set() # Focus the new entry for immediate input

    def _add_instrument_row_ui(self, instrument_name_initial: str = "") -> Optional[ttk.Entry]:
        """
        Adds a new row to the UI for instrument input and deletion.
        Each row contains an entry field for the ticker and a delete button.
        Returns the new Entry widget for focus purposes, or None.
        """
        row_frame = ttk.Frame(self.instrument_list_display_frame)
        row_frame.pack(side="top", fill="x", pady=1, padx=2) # Small padding around row

        name_var = tk.StringVar(value=instrument_name_initial)
        # Make entry expand, give it decent width for tickers
        name_entry = ttk.Entry(row_frame, textvariable=name_var, width=25) 
        name_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        # Make delete button compact. Assuming Danger.Toolbutton.TButton is defined in App or style
        delete_button = ttk.Button(row_frame, text="X", width=3, style="Danger.Toolbutton.TButton",
                                   command=lambda rf=row_frame: self._remove_instrument_row_ui(rf))
        delete_button.pack(side="left", padx=(0,2))

        self.instrument_rows_data.append({
            'frame': row_frame, 
            'name_var': name_var, 
            'entry': name_entry, 
            'button': delete_button
        })
        return name_entry

    def _remove_instrument_row_ui(self, row_frame_to_delete: ttk.Frame):
        """
        Removes the specified instrument row from the UI and internal data.
        If no rows remain, adds a new blank one.
        """
        row_to_remove_data = None
        for i, row_data in enumerate(self.instrument_rows_data):
            if row_data['frame'] == row_frame_to_delete:
                row_to_remove_data = row_data
                del self.instrument_rows_data[i]
                break
        
        if row_to_remove_data:
            row_to_remove_data['frame'].destroy()

        if not self.instrument_rows_data: # If list becomes empty
            self._add_instrument_row_ui() # Add a fresh blank row

    def get_instruments(self) -> Set[str]:
        """
        Retrieves the current set of unique, uppercase instrument tickers from the UI.
        Empty strings or tickers consisting only of whitespace are ignored.
        """
        instruments_set: Set[str] = set()
        for row_data in self.instrument_rows_data:
            instrument_name = row_data['name_var'].get().strip().upper()
            if instrument_name: # Only add valid, non-empty tickers
                instruments_set.add(instrument_name)
        return instruments_set

    def focus_on_last_instrument_entry(self) -> None:
        """Sets focus to the entry field of the last instrument row, if one exists."""
        if self.instrument_rows_data:
            self.instrument_rows_data[-1]['entry'].focus_set()
            
    def focus_on_add_button(self) -> None:
        """Sets focus to the 'Add Instrument' button."""
        self.add_instrument_button.focus_set()

# Example Usage (can be commented out or removed for production)
# if __name__ == '__main__':
#     root = tk.Tk()
#     root.title("Instrument List Manager Test")
#     root.geometry("400x300")

#     # Style for Danger.Toolbutton.TButton if not available globally in your app
#     style = ttk.Style()
#     if 'Danger.Toolbutton.TButton' not in style.element_names(): # Check if style exists
#         style.configure("Danger.Toolbutton.TButton", foreground="#c00000", padding=2, relief="flat", font=('Arial', 10))
#         style.map("Danger.Toolbutton.TButton", 
#                   relief=[('pressed', 'sunken'), ('hover', 'groove'), ('!pressed', 'flat')],
#                   foreground=[('pressed', 'darkred'), ('hover', 'red'), ('!pressed', '#c00000')],
#                   background=[('active', '#fde0e0')])


#     main_frame = ttk.Frame(root, padding=10)
#     main_frame.pack(fill="both", expand=True)
    
#     ttk.Label(main_frame, text="Managed Instrument List:").pack(anchor="w")
    
#     # Test with initial instruments
#     instrument_manager = InstrumentListManagerWidget(main_frame, initial_instruments_list=["AAPL", "MSFT", "GOOG"])
#     instrument_manager.pack(fill="both", expand=True, pady=5)

#     # Test with no initial instruments
#     # instrument_manager_empty = InstrumentListManagerWidget(main_frame)
#     # instrument_manager_empty.pack(fill="both", expand=True, pady=5)

#     def print_instruments():
#         print("Current Instruments:", instrument_manager.get_instruments())

#     get_button = ttk.Button(main_frame, text="Get Instruments from Widget", command=print_instruments)
#     get_button.pack(pady=10)

#     root.mainloop()
