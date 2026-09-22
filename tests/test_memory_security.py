"""
Tests for memory privacy, sensitive data detection, and security guardrails (Phase 13).
"""

import pytest
from memory.models import MemorySecurityError, MemoryValidationError
from memory.security import (
    is_sensitive_memory,
    mask_memory_for_logging,
    validate_memory_key,
    validate_memory_tags,
    validate_memory_value,
)


class TestMemorySecurity:
    """Test sensitive data detection and memory validation."""

    def test_passwords_and_pins_detected(self) -> None:
        assert is_sensitive_memory("password: mySecretPassword123") is True
        assert is_sensitive_memory("my password is superSecret456") is True
        assert is_sensitive_memory("PIN: 4921") is True
        assert is_sensitive_memory("cvv: 789") is True
        assert is_sensitive_memory("User prefers passwordless authentication") is False

    def test_api_keys_detected(self) -> None:
        # OpenAI style key
        assert is_sensitive_memory("sk-proj-1234567890abcdef1234567890abcdef") is True
        # Anthropic key
        assert is_sensitive_memory("sk-ant-1234567890abcdef1234567890abcdef") is True
        # Google API key
        assert is_sensitive_memory("AIzaSyD1234567890abcdef123456789012345") is True
        # AWS Key ID
        assert is_sensitive_memory("AKIAIOSFODNN7EXAMPLE") is True
        # Generic API key pattern
        assert is_sensitive_memory("api_key = 'abcdef1234567890abcdef'") is True

    def test_tokens_and_jwt_detected(self) -> None:
        # Bearer token
        assert is_sensitive_memory("Authorization: Bearer mySecretToken1234567890") is True
        # JWT token
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozGzN_ce"
        assert is_sensitive_memory(jwt) is True
        # Private key block
        assert is_sensitive_memory("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...") is True

    def test_credit_card_luhn_detection(self) -> None:
        # Valid test Visa number (passes Luhn)
        assert is_sensitive_memory("Card number: 4532 0151 1283 0366") is True
        # Random non-card 16 digit number that fails Luhn
        assert is_sensitive_memory("Order reference: 1234567890123456") is False

    def test_cookies_and_auth_headers_detected(self) -> None:
        assert is_sensitive_memory("Cookie: session_id=abcdef1234567890") is True
        assert is_sensitive_memory("sessionid=xyz987654321000") is True

    def test_otps_detected(self) -> None:
        assert is_sensitive_memory("Your OTP is 492019") is True
        assert is_sensitive_memory("2fa code: 928172") is True
        assert is_sensitive_memory("verification code: 123456") is True

    def test_safe_memories_accepted(self) -> None:
        assert is_sensitive_memory("User prefers Python for coding") is False
        assert is_sensitive_memory("FoodConnect uses Firebase and React Native") is False
        assert is_sensitive_memory("Preferred temperature is 0.7") is False
        assert is_sensitive_memory("Current project is CHARVIS Phase 13") is False

    def test_validate_memory_value_rejects_sensitive(self) -> None:
        with pytest.raises(MemorySecurityError) as exc:
            validate_memory_value("My secret password: SuperSecretP@ss")
        assert "sensitive credentials" in str(exc.value)

    def test_validate_memory_value_accepts_valid(self) -> None:
        val = validate_memory_value("  user prefers concise answers  ")
        assert val == "user prefers concise answers"

    def test_validate_memory_key_bounds(self) -> None:
        with pytest.raises(MemoryValidationError):
            validate_memory_key("")

        with pytest.raises(MemoryValidationError):
            validate_memory_key("k" * 150, max_length=100)

        assert validate_memory_key("  clean_key  ") == "clean_key"

    def test_validate_memory_tags(self) -> None:
        tags = validate_memory_tags(["PYTHON", "  coding  ", "python", "dev"], max_tags=3)
        assert tags == ["python", "coding", "dev"]

    def test_mask_memory_for_logging(self) -> None:
        log_str = mask_memory_for_logging("preferred_lang", "Python")
        assert "preferred_lang" in log_str
        assert "Python" not in log_str
        assert "6 chars" in log_str
