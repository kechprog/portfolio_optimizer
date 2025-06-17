
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
        """Constructs the UI elements for the widget with scrollable container."""
        # Create a frame to hold the canvas and scrollbar
        scroll_container = ttk.Frame(self)
        scroll_container.pack(side="top", fill="both", expand=True, padx=0, pady=0)
        
        # Create canvas for scrollable content
        self.canvas = tk.Canvas(scroll_container, highlightthickness=0)
        
        # Create vertical scrollbar
        v_scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=v_scrollbar.set)
        
        # Pack scrollbar and canvas
        v_scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Create the frame that will hold the instrument rows inside the canvas
        self.instrument_list_display_frame = ttk.Frame(self.canvas)
        
        # Create window in canvas to hold the scrollable frame
        self.canvas_window = self.canvas.create_window((0, 0), window=self.instrument_list_display_frame, anchor="nw")
        
        # Bind canvas resize to update the scrollable frame width
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        
        # Bind frame configure to update scroll region when content changes
        self.instrument_list_display_frame.bind("<Configure>", self._on_frame_configure)
        
        # Bind mousewheel to canvas for scrolling
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.instrument_list_display_frame.bind("<MouseWheel>", self._on_mousewheel)

        # "Add Instrument" Button Frame and Button
        add_button_frame = ttk.Frame(self)
        add_button_frame.pack(side="top", fill="x", pady=(5,0)) # Place button below list
        
        self.add_instrument_button = ttk.Button(add_button_frame, text="Add Instrument",
                                           command=self._add_instrument_row_ui_event)
        self.add_instrument_button.pack(pady=2) # Center button in its frame

    def _on_canvas_configure(self, event):
        """Handle canvas resize to update the scrollable frame width."""
        # Update the canvas window width to match the canvas width
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)

    def _on_frame_configure(self, event):
        """Handle frame configuration changes to update scroll region."""
        self._update_scroll_region()

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _scroll_to_bottom(self):
        """Scroll the canvas to show the bottom (most recently added items)."""
        self.canvas.yview_moveto(1.0)

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
        
        # Update scroll region after adding new row
        self.after_idle(self._update_scroll_region)
        # Scroll to show the newly added row
        self.after_idle(self._scroll_to_bottom)
        
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
            # Update scroll region after removing row
            self.after_idle(self._update_scroll_region)

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

    def _update_scroll_region(self):
        """Update the scroll region to encompass all widgets."""
        # Force update of the display frame geometry
        self.instrument_list_display_frame.update_idletasks()
        
        # Wait a bit more for layout to complete
        self.update_idletasks()
        
        # Try to get bbox first
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=bbox)
        else:
            # Fallback: Calculate the total height manually
            # Force geometry manager to calculate sizes
            self.instrument_list_display_frame.update()
            total_height = self.instrument_list_display_frame.winfo_reqheight()
            total_width = self.instrument_list_display_frame.winfo_reqwidth()
            if total_height > 0:
                self.canvas.configure(scrollregion=(0, 0, total_width, total_height))
            else:
                # Final fallback: calculate based on number of rows
                row_count = len(self.instrument_rows_data)
                estimated_height = row_count * 35  # Approximate height per row
                self.canvas.configure(scrollregion=(0, 0, 300, estimated_height))

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
