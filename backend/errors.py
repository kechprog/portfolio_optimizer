"""
Centralized error handling for the portfolio optimizer application.
"""
from enum import Enum
from typing import Optional


class ErrorCategory(Enum):
    """Categories of errors that can occur in the application."""
    VALIDATION = "validation"
    NETWORK = "network"
    COMPUTE = "compute"
    AUTH = "auth"
    DATABASE = "database"
    SYSTEM = "system"


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    ERROR = "error"
    WARNING = "warning"


class AppError(Exception):
    """
    Base application error class with structured error information.

    Attributes:
        message: Human-readable error message
        code: Machine-readable error code
        category: Error category from ErrorCategory enum
        severity: Error severity from ErrorSeverity enum
        allocator_id: Optional ID of the allocator that encountered the error
        recoverable: Whether the error is recoverable
    """

    def __init__(
        self,
        message: str,
        code: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        allocator_id: Optional[str] = None,
        recoverable: bool = False
    ):
        """
        Initialize an application error.

        Args:
            message: Human-readable error message
            code: Machine-readable error code
            category: Error category from ErrorCategory enum
            severity: Error severity from ErrorSeverity enum (defaults to ERROR)
            allocator_id: Optional ID of the allocator that encountered the error
            recoverable: Whether the error is recoverable (defaults to False)
        """
        self.message = message
        self.code = code
        self.category = category
        self.severity = severity
        self.allocator_id = allocator_id
        self.recoverable = recoverable
        super().__init__(message)

    def to_dict(self) -> dict:
        """
        Convert the error to a dictionary representation.

        Returns:
            Dictionary with error details suitable for API responses
        """
        return {
            "type": "error",
            "message": self.message,
            "code": self.code,
            "category": self.category.value,
            "severity": self.severity.value,
            "allocator_id": self.allocator_id,
            "recoverable": self.recoverable
        }


class ValidationError(AppError):
    """Error raised when validation fails."""

    def __init__(
        self,
        message: str,
        code: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        allocator_id: Optional[str] = None,
        recoverable: bool = False
    ):
        super().__init__(
            message=message,
            code=code,
            category=ErrorCategory.VALIDATION,
            severity=severity,
            allocator_id=allocator_id,
            recoverable=recoverable
        )


class NetworkError(AppError):
    """Error raised when network operations fail."""

    def __init__(
        self,
        message: str,
        code: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        allocator_id: Optional[str] = None,
        recoverable: bool = False
    ):
        super().__init__(
            message=message,
            code=code,
            category=ErrorCategory.NETWORK,
            severity=severity,
            allocator_id=allocator_id,
            recoverable=recoverable
        )


class ComputeError(AppError):
    """Error raised when computation operations fail."""

    def __init__(
        self,
        message: str,
        code: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        allocator_id: Optional[str] = None,
        recoverable: bool = False
    ):
        super().__init__(
            message=message,
            code=code,
            category=ErrorCategory.COMPUTE,
            severity=severity,
            allocator_id=allocator_id,
            recoverable=recoverable
        )


class DatabaseError(AppError):
    """Error raised when database operations fail."""

    def __init__(
        self,
        message: str,
        code: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        allocator_id: Optional[str] = None,
        recoverable: bool = False
    ):
        super().__init__(
            message=message,
            code=code,
            category=ErrorCategory.DATABASE,
            severity=severity,
            allocator_id=allocator_id,
            recoverable=recoverable
        )
