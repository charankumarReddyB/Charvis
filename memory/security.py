"""
Security and privacy guardrails for the CHARVIS Memory System (Phase 13).
Ensures sensitive data (passwords, API keys, tokens, CVVs, card numbers, OTPs)
is strictly detected and rejected before persisting to storage or logs.
"""

import re
from typing import List, Optional
from memory.models import MemorySecurityError, MemoryValidationError


# Regex patterns for identifying sensitive credentials and secrets
SENSITIVE_PATTERNS = [
    # Passwords, PINs, CVVs
    re.compile(r"(?i)\b(password|passwd|passphrase|pwd|pin|cvv|cvc)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bmy\s+(password|pin|cvv|cvc)\s+is\s+\S+"),
    re.compile(r"(?i)\bpassword\s+is\s+\S+"),

    # API Keys & Cloud Credentials
    re.compile(r"\bsk-[a-zA-Z0-9_-]{20,}\b"),                           # OpenAI style keys
    re.compile(r"\bsk-ant-[a-zA-Z0-9_-]{20,}\b"),                       # Anthropic style keys
    re.compile(r"\bAIza[0-9A-Za-z-_]{20,}\b"),                          # Google API keys
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                                # AWS Access Key IDs
    re.compile(r"(?i)\bapi[_-]?key\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{16,}['\"]?"),
    re.compile(r"(?i)\bsecret[_-]?key\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{16,}['\"]?"),

    # Tokens & Private Keys
    re.compile(r"(?i)\bbearer\s+[a-zA-Z0-9_\-\.=]{16,}\b"),             # Bearer tokens
    re.compile(r"\bey[A-Za-z0-9-_=]+\.ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\b"), # JWT tokens
    re.compile(r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----"),        # Private keys

    # OTPs & Verification Codes
    re.compile(r"(?i)\b(otp|2fa(?:\s+code)?|verification\s+code|mfa(?:\s+code)?)\s*(?:is|[:=])\s*\d{4,8}\b"),

    # Browser Cookies & Auth Headers
    re.compile(r"(?i)\b(?:cookie|set-cookie)\s*:\s*\S+"),
    re.compile(r"(?i)\b(?:session_id|sessionid|auth_token)\s*=\s*[a-zA-Z0-9_\-\.]{12,}"),
]

# Credit Card pattern (Visa, Mastercard, Amex, Discover)
CARD_PATTERN = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b|\b3[47]\d{2}[ -]?\d{6}[ -]?\d{5}\b")


def _is_luhn_valid(card_number_str: str) -> bool:
    """Validate digits using Luhn algorithm."""
    digits = [int(c) for c in card_number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, d in enumerate(reverse_digits):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def is_sensitive_memory(text: str) -> bool:
    """
    Check if a text string contains sensitive credentials, secrets, or financial data.
    Returns True if sensitive information is detected, False otherwise.
    """
    if not isinstance(text, str) or not text.strip():
        return False

    # Check standard sensitive regex patterns
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            return True

    # Check for Credit/Debit Cards
    for card_match in CARD_PATTERN.finditer(text):
        matched_digits = card_match.group(0)
        if _is_luhn_valid(matched_digits):
            return True

    return False


def validate_memory_key(key: str, max_length: int = 100) -> str:
    """Validate memory key string and bounds."""
    if not isinstance(key, str) or not key.strip():
        raise MemoryValidationError("Memory key cannot be empty.")
    stripped = key.strip()
    if len(stripped) > max_length:
        raise MemoryValidationError(
            f"Memory key length ({len(stripped)}) exceeds maximum limit of {max_length} characters."
        )
    return stripped


def validate_memory_value(value: str, max_length: int = 2000) -> str:
    """Validate memory value string, bounds, and sensitivity."""
    if not isinstance(value, str) or not value.strip():
        raise MemoryValidationError("Memory value cannot be empty.")
    stripped = value.strip()
    if len(stripped) > max_length:
        raise MemoryValidationError(
            f"Memory value length ({len(stripped)}) exceeds maximum limit of {max_length} characters."
        )
    if is_sensitive_memory(stripped):
        raise MemorySecurityError(
            "Memory storage rejected: sensitive credentials, tokens, or personal secrets detected."
        )
    return stripped


def validate_memory_tags(tags: Optional[List[str]], max_tags: int = 10) -> List[str]:
    """Validate and sanitize memory tags list."""
    if tags is None:
        return []
    if not isinstance(tags, (list, tuple)):
        raise MemoryValidationError("Memory tags must be a list of strings.")

    cleaned: List[str] = []
    for t in tags:
        if isinstance(t, str) and t.strip():
            tag_str = t.strip().lower()
            if len(tag_str) > 30:
                tag_str = tag_str[:30]
            if tag_str not in cleaned:
                cleaned.append(tag_str)

    return cleaned[:max_tags]


def mask_memory_for_logging(key: str, value: str) -> str:
    """Format memory metadata safely for diagnostic logging without exposing full content."""
    return f"[key='{key}', length={len(value)} chars]"
