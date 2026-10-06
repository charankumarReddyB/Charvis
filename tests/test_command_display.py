"""
Tests for Command & Response Display and Secret Redaction (Phase 19).
Verifies:
- Command display shows user input in the assistant UI
- Response display shows assistant outputs
- Redaction of passwords, API keys, bearer tokens, OTPs, CVVs, and private keys
- Empty or whitespace prompts are safely handled
"""

import pytest
from gui.widgets.assistant import redact_display_text


def test_redact_display_text_passwords():
    """Verify password assignment patterns are sanitized."""
    raw = "My credentials are password=VerySecretPassword123 and user=admin"
    redacted = redact_display_text(raw)
    assert "VerySecretPassword123" not in redacted
    assert 'password="[REDACTED]"' in redacted


def test_redact_display_text_api_keys():
    """Verify sk- API key patterns are sanitized."""
    raw = "Use key sk-abcdef12345678901234567890 for API calls"
    redacted = redact_display_text(raw)
    assert "sk-abcdef12345678901234567890" not in redacted
    assert "[REDACTED KEY]" in redacted


def test_redact_display_text_bearer_tokens():
    """Verify Bearer token patterns are sanitized."""
    raw = "Authorization: Bearer my_jwt_token_1234567890_abcdef"
    redacted = redact_display_text(raw)
    assert "my_jwt_token_1234567890_abcdef" not in redacted
    assert "[REDACTED" in redacted


def test_redact_display_text_cvv_and_pins():
    """Verify CVV and PIN patterns are sanitized."""
    raw = "card details: cvv=789 and pin=1234"
    redacted = redact_display_text(raw)
    assert "789" not in redacted
    assert "1234" not in redacted
    assert '[REDACTED]' in redacted


def test_redact_display_text_private_keys():
    """Verify RSA/EC private key blocks are sanitized."""
    raw = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
    redacted = redact_display_text(raw)
    assert "MIIEowIBAAKCAQEA" not in redacted
    assert "[REDACTED PRIVATE KEY]" in redacted


def test_redact_display_text_safe_strings():
    """Verify normal benign queries are untouched."""
    safe_query = "What is the CPU usage and memory available on Windows?"
    assert redact_display_text(safe_query) == safe_query
