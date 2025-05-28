# portfolio_optimizer/allocator/allocator.py

from abc import ABC, abstractmethod
from datetime import date
from typing import Set, Dict, Optional, Type, Any # Added Any for save_state return

import tkinter as tk

class PortfolioAllocator(ABC):
    """
    Abstract Base Class for portfolio allocation strategies.
    Instances are typically created/reconfigured via the `configure_or_create` classmethod.
    """
    def __init__(self, name: str):
        self.name: str = name
        self._allocations: Dict[str, float] = {} # Should always be 0.0-1.0 scale

    @property
    def allocations(self) -> Dict[str, float]:
        """Returns a copy of the current portfolio allocations (0.0-1.0 scale)."""
        return self._allocations.copy()

    @abstractmethod
    def on_instruments_changed(self, new_instrument_set: Set[str]) -> None:
        """
        Called when the set of instruments in the main portfolio changes.
        The allocator should adjust its internal state for the current instance.
        """
        pass

    @classmethod
    @abstractmethod
    def configure_or_create(cls: Type['PAL'],
                            parent_window: tk.Misc,
                            current_instruments: Set[str],
                            existing_allocator: Optional['PortfolioAllocator'] = None,
                           ) -> Optional['PAL']:
        """
        Opens a configuration dialog to create/reconfigure an allocator instance.
        """
        pass

    @abstractmethod
    def compute_allocations(self, fitting_start_date: date, fitting_end_date: date) -> Dict[str, float]:
        """
        Computes and returns portfolio allocations, also storing them in self._allocations.
        """
        pass

    @abstractmethod
    def save_state(self) -> Dict[str, Any]:
        """
        Serializes the allocator's configuration into a dictionary.
        This dictionary should contain all necessary parameters to recreate
        the allocator's specific state, excluding the name (which is handled by App).
        """
        pass

    @abstractmethod
    def load_state(self, config_params: Dict[str, Any], current_instruments: Set[str]) -> None:
        """
        Restores the allocator's state from a dictionary of configuration parameters.
        This method is called after the allocator instance is created with its name.

        Args:
            config_params: The dictionary of parameters from save_state.
            current_instruments: The set of instruments currently active in the app,
                                 which the allocator might need to reconcile with its loaded state.
        """
        pass

from typing import TypeVar
PAL = TypeVar('PAL', bound='PortfolioAllocator')