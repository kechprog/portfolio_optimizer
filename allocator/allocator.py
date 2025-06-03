\
# portfolio_optimizer/allocator/allocator.py
from abc import ABC, abstractmethod
from typing import Dict, Optional, Type, Any, Set, TypeVar
from datetime import date
import tkinter as tk

# Assuming portfolio.py is in the parent directory of allocator/
# Adjust import path if portfolio.py is located elsewhere relative to this file.
# For example, if portfolio.py is in the same directory as app.py (portfolio_optimizer/),
# and this allocator.py is in portfolio_optimizer/allocator/
from portfolio import Portfolio # Changed from relative to direct

# Type alias for the state dictionary
AllocatorState = Dict[str, Any]

# Forward declaration for PAL type hint if needed, or define directly
# PAL = TypeVar('PAL', bound='PortfolioAllocator') # For generic programming
# For simplicity, we can use 'PortfolioAllocator' directly or define PAL after class.

class PortfolioAllocator(ABC):
    """
    Abstract base class for all portfolio allocators.
    Defines the interface for creating, configuring, and using allocators
    based on a state-driven, more functional approach.
    """

    def __init__(self, **state: AllocatorState):
        """
        Initializes the allocator instance from a given state dictionary.
        The state dictionary is expected to contain all necessary parameters
        for the allocator's operation.

        A mandatory key in the state is 'name'.
        """
        if 'name' not in state or not str(state['name']).strip():
            raise ValueError("Allocator state must include a non-empty 'name'.")
        self._state: AllocatorState = state # Store the provided state

    def get_name(self) -> str:
        """
        Returns the name of the allocator from its state.
        This method is not intended to be overridden by subclasses.
        """
        return str(self._state['name'])

    @abstractmethod
    def get_state(self) -> AllocatorState:
        """
        Returns the current state of the allocator as a dictionary.
        This state should be sufficient to recreate an equivalent allocator.
        Typically, this will return self._state or a copy.
        """
        pass

    @classmethod
    @abstractmethod
    def configure(
        cls: Type['PAL'], # PAL defined after class
        parent_window: tk.Misc,
        existing_state: Optional[AllocatorState] = None
    ) -> Optional[AllocatorState]:
        """
        Opens a configuration dialog for the allocator.
        If 'existing_state' is provided, the dialog is pre-filled/initialized
        with values from this state. If 'existing_state' is None, it assumes
        creation of a new allocator configuration.

        The dialog should allow configuration of all relevant parameters,
        including the allocator's name and its specific set of instruments.

        Args:
            parent_window: The parent tkinter window for the dialog.
            existing_state: Optional. The current state of an existing allocator
                            to be configured, or None for a new allocator.

        Returns:
            A new AllocatorState dictionary if configuration is completed and
            valid. This new state includes all parameters (name, instruments, etc.).
            Returns None if the configuration is cancelled or deemed invalid by the dialog.
            The returned state dictionary *must* include a 'name' key with a non-empty string value.
        """
        pass

    @abstractmethod
    def compute_allocations(self, fitting_start_date: date, fitting_end_date: date) -> Portfolio:
        """
        Computes the portfolio allocations based on the allocator's current state
        and the given fitting period, returning a Portfolio object.

        The returned Portfolio object will typically contain a single segment
        spanning from fitting_start_date to fitting_end_date for allocators
        that do not inherently model time-varying allocations.

        Args:
            fitting_start_date: The start date for the data used in fitting/computation,
                                and likely the start date of the returned Portfolio.
            fitting_end_date: The end date for the data used in fitting/computation,
                              and likely the end date for the primary segment in the Portfolio.

        Returns:
            A Portfolio object representing the allocations for the specified period.
            For allocators that compute a static allocation for the period,
            this Portfolio object will contain one segment from fitting_start_date
            to fitting_end_date with these allocations.
        """
        pass

    # Convenience helper method to access instruments from the state.
    # Subclasses might have instruments stored differently or might not need this.
    def get_instruments(self) -> Set[str]:
        """
        Helper method to retrieve the set of instruments from the allocator's state.
        Assumes instruments are stored under the key 'instruments' as a set or list.
        Returns an empty set if 'instruments' key is not found or is not a collection.
        """
        instruments_data = self._state.get('instruments')
        if isinstance(instruments_data, set):
            return instruments_data
        elif isinstance(instruments_data, (list, tuple)): # Allow list/tuple from JSON
            return set(instruments_data)
        return set() # Default to empty set

# Type alias for PortfolioAllocator class itself, for cleaner type hints in @classmethod
PAL = PortfolioAllocator
