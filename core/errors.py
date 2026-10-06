"""
Error classification and standardized exception hierarchy for CHARVIS (Phase 17).
Provides safe, categorized errors preventing raw internal stack/secret leaks to users
while retaining full diagnostics in logs.
"""

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCategory(str, Enum):
    """Standardized error categories across CHARVIS subsystems."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    RESOURCE_ERROR = "RESOURCE_ERROR"
    SAFETY_ERROR = "SAFETY_ERROR"
    CANCELLATION_ERROR = "CANCELLATION_ERROR"
    STATE_ERROR = "STATE_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    PLANNER_ERROR = "PLANNER_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class CharvisError(Exception):
    """
    Base exception for all classified CHARVIS errors.
    Encapsulates user-safe messaging and detailed diagnostic metadata.
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN_ERROR,
        details: Optional[Dict[str, Any]] = None,
        internal_error: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.category = category
        self.details = details or {}
        self.internal_error = internal_error

    def to_dict(self) -> Dict[str, Any]:
        """Return safe structured dictionary representation."""
        return {
            "error": self.message,
            "category": self.category.value,
            "details": self.details,
        }

    def user_friendly_message(self) -> str:
        """User-safe explanation without sensitive internal traceback details."""
        return f"[{self.category.value}] {self.message}"


class ValidationError(CharvisError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, ErrorCategory.VALIDATION_ERROR, details)


class AuthenticationError(CharvisError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, ErrorCategory.AUTHENTICATION_ERROR, details)


class TimeoutError(CharvisError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, ErrorCategory.TIMEOUT_ERROR, details)


class NetworkError(CharvisError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, ErrorCategory.NETWORK_ERROR, details)


class ResourceError(CharvisError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, ErrorCategory.RESOURCE_ERROR, details)


class SafetyError(CharvisError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, ErrorCategory.SAFETY_ERROR, details)


class CancellationError(CharvisError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, ErrorCategory.CANCELLATION_ERROR, details)


class StateError(CharvisError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, ErrorCategory.STATE_ERROR, details)


class ToolExecutionError(CharvisError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, ErrorCategory.TOOL_ERROR, details)


class PlannerExecutionError(CharvisError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, ErrorCategory.PLANNER_ERROR, details)


class RuntimeError(CharvisError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, ErrorCategory.RUNTIME_ERROR, details)
