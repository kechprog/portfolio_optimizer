"""
Pydantic models for WebSocket message serialization.

Uses discriminated unions for type-safe message routing.
"""

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


# =============================================================================
# Client -> Server Messages
# =============================================================================


class CreateAllocator(BaseModel):
    """Request to create a new allocator."""

    type: Literal["create_allocator"] = "create_allocator"
    allocator_type: str
    config: dict[str, Any]


class UpdateAllocator(BaseModel):
    """Request to update an existing allocator's configuration."""

    type: Literal["update_allocator"] = "update_allocator"
    id: str
    config: dict[str, Any]


class DeleteAllocator(BaseModel):
    """Request to delete an allocator."""

    type: Literal["delete_allocator"] = "delete_allocator"
    id: str


class ComputePortfolio(BaseModel):
    """Request to compute portfolio allocation."""

    type: Literal["compute"] = "compute"
    allocator_id: str
    fit_start_date: str
    fit_end_date: str
    test_end_date: str
    include_dividends: bool = False


class ListAllocators(BaseModel):
    """Request to list all allocators."""

    type: Literal["list_allocators"] = "list_allocators"


class UpdateDashboardSettings(BaseModel):
    """Request to update dashboard settings."""

    type: Literal["update_dashboard_settings"] = "update_dashboard_settings"
    fit_start_date: Optional[str] = None
    fit_end_date: Optional[str] = None
    test_end_date: Optional[str] = None
    include_dividends: Optional[bool] = None


# Discriminated union for all client messages
ClientMessage = Annotated[
    Union[
        CreateAllocator,
        UpdateAllocator,
        DeleteAllocator,
        ComputePortfolio,
        ListAllocators,
        UpdateDashboardSettings,
    ],
    Field(discriminator="type"),
]


# =============================================================================
# Server -> Client Messages
# =============================================================================


class AllocatorCreated(BaseModel):
    """Response after successfully creating an allocator."""

    type: Literal["allocator_created"] = "allocator_created"
    id: str
    allocator_type: str
    config: dict[str, Any]


class AllocatorUpdated(BaseModel):
    """Response after successfully updating an allocator."""

    type: Literal["allocator_updated"] = "allocator_updated"
    id: str
    config: dict[str, Any]


class AllocatorDeleted(BaseModel):
    """Response after successfully deleting an allocator."""

    type: Literal["allocator_deleted"] = "allocator_deleted"
    id: str


class AllocatorsList(BaseModel):
    """Response containing list of all allocators."""

    type: Literal["allocators_list"] = "allocators_list"
    allocators: list[dict[str, Any]]


class Progress(BaseModel):
    """Progress update during computation."""

    type: Literal["progress"] = "progress"
    allocator_id: str
    message: str
    step: int
    total_steps: int


class Result(BaseModel):
    """Computation result."""

    type: Literal["result"] = "result"
    allocator_id: str
    segments: list[dict[str, Any]]
    performance: dict[str, Any]


class Error(BaseModel):
    """Error response."""

    type: Literal["error"] = "error"
    message: str
    code: str = "SYS_001"
    category: str = "system"
    severity: str = "error"
    allocator_id: Optional[str] = None
    recoverable: bool = False


class DashboardSettingsUpdated(BaseModel):
    """Response after successfully updating dashboard settings."""

    type: Literal["dashboard_settings_updated"] = "dashboard_settings_updated"
    fit_start_date: Optional[str] = None
    fit_end_date: Optional[str] = None
    test_end_date: Optional[str] = None
    include_dividends: Optional[bool] = None


# Discriminated union for all server messages
ServerMessage = Annotated[
    Union[
        AllocatorCreated,
        AllocatorUpdated,
        AllocatorDeleted,
        AllocatorsList,
        Progress,
        Result,
        Error,
        DashboardSettingsUpdated,
    ],
    Field(discriminator="type"),
]
