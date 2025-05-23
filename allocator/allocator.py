# allocator.py

from abc import ABC, abstractmethod
from datetime import date, timedelta
# pandas might be used by other allocators for data manipulation if they fetch price data
# For now, ManualAllocator doesn't directly use it in prepare_plot_data beyond date iteration.
# import pandas as pd
from typing import Set, Dict, List, Optional, Type

import matplotlib.axes
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

class PortfolioAllocator(ABC):
    """
    Abstract Base Class for portfolio allocation strategies.
    Instances are typically created/reconfigured via the `configure_or_create` classmethod.
    """
    def __init__(self, name: str):
        self.name: str = name
        # Allocations are typically set during creation by configure_or_create
        self._allocations: Dict[str, float] = {} # Should always be 0.0-1.0 scale
        # Internal data for plotting, prepared by prepare_plot_data
        self._plot_dates: List[date] = []
        self._plot_values: List[float] = []
        # is_enabled flag will be managed by app.py externally

    @property
    def allocations(self) -> Dict[str, float]:
        """Returns a copy of the current portfolio allocations (0.0-1.0 scale)."""
        return self._allocations.copy()

    @abstractmethod
    def on_instruments_changed(self, new_instrument_set: Set[str]) -> None:
        """
        Called when the set of instruments in the main portfolio changes.
        The allocator should adjust its internal state/allocations for the current instance.
        This method modifies the existing instance.
        """
        pass

    @classmethod
    @abstractmethod
    def configure_or_create(cls: Type['PAL'], # PAL is a TypeVar representing a subclass of PortfolioAllocator
                            parent_window: tk.Misc,
                            current_instruments: Set[str],
                            existing_allocator: Optional['PortfolioAllocator'] = None,
                           ) -> Optional['PAL']:
        """
        Opens a configuration dialog to create a new allocator instance or
        reconfigure settings based on an existing one.

        Args:
            parent_window: The Tkinter parent window for the dialog.
            current_instruments: The current set of instruments to configure for.
            existing_allocator: An optional existing allocator instance. If provided,
                                its settings (name, allocations) are used as defaults
                                in the configuration dialog.

        Returns:
            A new, configured instance of the PortfolioAllocator subclass,
            or None if the configuration is cancelled.
        """
        pass


    @abstractmethod
    def prepare_plot_data(self, fitting_start_date_of_plot: date, plot_end_date: date) -> None:
        """
        Prepares any data needed for draw_plot based on current allocations,
        selected dates, and potentially external data. This method modifies the instance.
        """
        pass

    @abstractmethod
    def draw_plot(self, ax: matplotlib.axes.Axes) -> None:
        """
        Draws the allocator's contribution to the plot on the provided Matplotlib Axes.
        This method should ONLY draw its data series.
        """
        pass