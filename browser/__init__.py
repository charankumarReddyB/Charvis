"""CHARVIS Browser Automation Subsystem.

Provides controlled, sandboxed web browser automation with strict URL validation,
sensitive field protection, isolated profile contexts, and action safety.
"""

from browser.controller import BrowserController
from browser.models import (
    BrowserError,
    BrowserNotRunningError,
    BrowserSecurityError,
    BrowserTimeoutError,
    PageInfo,
)
from browser.security import (
    classify_click_risk,
    is_sensitive_input,
    sanitize_sensitive_value,
    validate_browser_url,
)

__all__ = [
    "BrowserController",
    "PageInfo",
    "BrowserError",
    "BrowserSecurityError",
    "BrowserTimeoutError",
    "BrowserNotRunningError",
    "validate_browser_url",
    "is_sensitive_input",
    "classify_click_risk",
    "sanitize_sensitive_value",
]
