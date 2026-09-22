"""CHARVIS Browser Models and Exceptions.

Defines data structures and domain exceptions for the browser automation subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class BrowserError(Exception):
    """Base exception for all browser subsystem errors."""

    pass


class BrowserSecurityError(BrowserError):
    """Raised when an operation violates browser security boundaries (URL/action/scheme)."""

    pass


class BrowserTimeoutError(BrowserError):
    """Raised when navigation or locator action exceeds the configured timeout."""

    pass


class BrowserNotRunningError(BrowserError):
    """Raised when an action is attempted while the browser session is not active."""

    pass


@dataclass
class PageInfo:
    """Represents a snapshot of current browser page state."""

    url: str
    title: str
    visible_text: str
    status_code: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert page info to dictionary representation."""
        return {
            "url": self.url,
            "title": self.title,
            "visible_text": self.visible_text,
            "status_code": self.status_code,
        }
