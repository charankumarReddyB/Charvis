"""CHARVIS Browser Security & Action Safety Subsystem.

Provides centralized URL validation, sensitive field detection, risk classification,
and secret masking for all browser automation operations.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from core.safety import RiskLevel
from logger import get_logger
from browser.models import BrowserSecurityError

logger = get_logger(__name__)

# Permitted and prohibited URL schemes
ALLOWED_SCHEMES = {"http", "https"}
PROHIBITED_SCHEMES = {
    "file",
    "javascript",
    "data",
    "vbscript",
    "chrome",
    "chrome-extension",
    "edge",
    "brave",
    "about",
    "view-source",
    "blob",
    "ftp",
}

# Regex patterns for sensitive field detection (selector, name, id, type, placeholder)
SENSITIVE_INPUT_PATTERNS = [
    r"pass(word)?",
    r"pwd",
    r"secret",
    r"token",
    r"auth",
    r"otp",
    r"one[-_]?time[-_]?pass",
    r"pin",
    r"ssn",
    r"social[-_]?sec",
    r"card[-_]?num(ber)?",
    r"credit[-_]?card",
    r"debit[-_]?card",
    r"cvv",
    r"cvc",
    r"expir(y|ation)",
    r"bank[-_]?acc(ount)?",
    r"routing[-_]?num",
    r"security[-_]?(code|answer|question)",
    r"private[-_]?key",
]
_COMPILED_SENSITIVE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SENSITIVE_INPUT_PATTERNS]

# Regex patterns for high-impact/external action click detection (text, selector, id, class)
CONFIRMATION_ACTION_PATTERNS = [
    r"\b(buy|purchase|checkout|pay|payment|place[-_ ]order|submit[-_ ]order)\b",
    r"\b(book|reserve|confirm[-_ ]booking)\b",
    r"\b(delete[-_ ]account|close[-_ ]account|deactivate)\b",
    r"\b(transfer[-_ ]funds|send[-_ ]money|wire)\b",
    r"\b(send[-_ ](message|email|mail|dm)|post|tweet|publish)\b",
    r"\b(delete|remove|destroy|erase|purge)\b",
    r"\b(change[-_ ]password|reset[-_ ]password)\b",
]
_COMPILED_ACTION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in CONFIRMATION_ACTION_PATTERNS]


def validate_browser_url(url: str, allow_about_blank: bool = False) -> str:
    """Validate and normalize a destination URL for browser navigation.

    Args:
        url: The candidate URL to navigate to.
        allow_about_blank: Whether 'about:blank' is permitted.

    Returns:
        str: Normalized, validated URL.

    Raises:
        BrowserSecurityError: If the URL scheme is dangerous, malformed, or local file.
    """
    if not url or not isinstance(url, str):
        raise BrowserSecurityError("Navigation URL must be a non-empty string.")

    cleaned_url = url.strip()

    # Special case for blank page initialization
    if allow_about_blank and cleaned_url.lower() == "about:blank":
        return "about:blank"

    # Pre-parse check for scheme
    scheme_match = re.match(r"^([a-zA-Z0-9+.-]+):", cleaned_url)
    if scheme_match:
        scheme = scheme_match.group(1).lower()
        if scheme in PROHIBITED_SCHEMES or scheme not in ALLOWED_SCHEMES:
            logger.warning("Blocked navigation to disallowed scheme: '%s' in URL '%s'", scheme, cleaned_url)
            raise BrowserSecurityError(
                f"Navigation to scheme '{scheme}:' is strictly prohibited. "
                "Only 'http://' and 'https://' are permitted."
            )
    else:
        # If scheme is missing entirely, reject rather than guess dangerous paths
        raise BrowserSecurityError(
            f"Invalid URL '{cleaned_url}'. Destination must include 'http://' or 'https://'."
        )

    try:
        parsed = urlparse(cleaned_url)
    except Exception as err:
        raise BrowserSecurityError(f"Malformed URL '{cleaned_url}': {err}") from err

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise BrowserSecurityError(
            f"Unsupported scheme '{parsed.scheme}'. Only 'http://' and 'https://' URLs are supported."
        )

    if not parsed.netloc:
        raise BrowserSecurityError(f"URL '{cleaned_url}' lacks a valid host domain.")

    return cleaned_url


def is_sensitive_input(selector: str, field_type: str = "", placeholder: str = "") -> bool:
    """Determine whether an input element targets sensitive user information.

    Args:
        selector: CSS selector or locator text used to target the element.
        field_type: HTML 'type' attribute (e.g. 'password', 'tel', 'text').
        placeholder: HTML placeholder or aria-label attribute.

    Returns:
        bool: True if field targets sensitive data, requiring confirmation and redaction.
    """
    if field_type and field_type.strip().lower() == "password":
        return True

    combined_text = f"{selector} {field_type} {placeholder}".lower()
    for pattern in _COMPILED_SENSITIVE_PATTERNS:
        if pattern.search(combined_text):
            return True

    return False


def classify_click_risk(selector: str, element_text: str = "") -> RiskLevel:
    """Classify the safety risk level for clicking a given web element.

    Args:
        selector: Element locator string.
        element_text: Visible button/link text or value.

    Returns:
        RiskLevel: SAFE or CONFIRMATION_REQUIRED based on impact.
    """
    combined = f"{selector} {element_text}".lower()

    # Check for high-impact confirmation patterns
    for pattern in _COMPILED_ACTION_PATTERNS:
        if pattern.search(combined):
            logger.info("Click action on '%s' flagged as CONFIRMATION_REQUIRED", selector)
            return RiskLevel.CONFIRMATION_REQUIRED

    return RiskLevel.SAFE


def sanitize_sensitive_value(text: str) -> str:
    """Mask sensitive input value for logging and response dictionaries."""
    if not text:
        return ""
    return "***REDACTED***"
