"""Tests for Browser Security and Risk Classification Subsystem (Phase 10).

Verifies URL scheme validation, sensitive field detection, risk level classification,
and secret masking.
"""

import pytest

from core.safety import RiskLevel
from browser.models import BrowserSecurityError
from browser.security import (
    classify_click_risk,
    is_sensitive_input,
    sanitize_sensitive_value,
    validate_browser_url,
)


def test_url_validation_accepts_http_and_https() -> None:
    """Verify standard HTTP and HTTPS URLs are accepted and normalized."""
    assert validate_browser_url("http://example.com") == "http://example.com"
    assert validate_browser_url("https://example.com/path?arg=1") == "https://example.com/path?arg=1"
    assert validate_browser_url("https://subdomain.test.org:8080/app") == "https://subdomain.test.org:8080/app"


def test_url_validation_rejects_file_scheme() -> None:
    """CRITICAL SECURITY: Verify local file:// URLs are strictly rejected."""
    with pytest.raises(BrowserSecurityError, match="strictly prohibited"):
        validate_browser_url("file:///C:/Windows/System32/drivers/etc/hosts")

    with pytest.raises(BrowserSecurityError, match="strictly prohibited"):
        validate_browser_url("FILE://etc/passwd")


def test_url_validation_rejects_javascript_scheme() -> None:
    """CRITICAL SECURITY: Verify javascript: URLs are strictly rejected."""
    with pytest.raises(BrowserSecurityError, match="strictly prohibited"):
        validate_browser_url("javascript:alert(document.cookie)")

    with pytest.raises(BrowserSecurityError, match="strictly prohibited"):
        validate_browser_url("javascript:void(0)")


def test_url_validation_rejects_data_and_vbscript_schemes() -> None:
    """CRITICAL SECURITY: Verify data: and vbscript: URLs are strictly rejected."""
    with pytest.raises(BrowserSecurityError, match="strictly prohibited"):
        validate_browser_url("data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==")

    with pytest.raises(BrowserSecurityError, match="strictly prohibited"):
        validate_browser_url("vbscript:msgbox('hello')")


def test_url_validation_rejects_browser_internal_and_extension_schemes() -> None:
    """Verify chrome://, edge://, and extension schemes are strictly rejected."""
    with pytest.raises(BrowserSecurityError, match="strictly prohibited"):
        validate_browser_url("chrome://settings")

    with pytest.raises(BrowserSecurityError, match="strictly prohibited"):
        validate_browser_url("edge://flags")

    with pytest.raises(BrowserSecurityError, match="strictly prohibited"):
        validate_browser_url("chrome-extension://abcdefg/manifest.json")


def test_url_validation_rejects_invalid_and_empty_urls() -> None:
    """Verify empty, non-string, or schemeless strings are rejected."""
    with pytest.raises(BrowserSecurityError):
        validate_browser_url("")

    with pytest.raises(BrowserSecurityError):
        validate_browser_url("just a text search")


def test_sensitive_input_detection_passwords() -> None:
    """Verify password inputs are identified as sensitive regardless of casing."""
    assert is_sensitive_input("input#password", field_type="password") is True
    assert is_sensitive_input("input[name='user_pwd']") is True
    assert is_sensitive_input("#user_password") is True
    assert is_sensitive_input("input.secret-key") is True


def test_sensitive_input_detection_financial_and_auth() -> None:
    """Verify credit cards, CVVs, OTPs, and auth tokens are identified as sensitive."""
    assert is_sensitive_input("#credit_card_number") is True
    assert is_sensitive_input("input[name='cvv']") is True
    assert is_sensitive_input("input[name='cvc']") is True
    assert is_sensitive_input("#otp_code") is True
    assert is_sensitive_input("input[name='auth_token']") is True
    assert is_sensitive_input("#bank_account") is True
    assert is_sensitive_input("#security_answer") is True


def test_ordinary_inputs_are_not_flagged_sensitive() -> None:
    """Verify ordinary non-sensitive search and text inputs return False."""
    assert is_sensitive_input("input#search") is False
    assert is_sensitive_input("input[name='query']") is False
    assert is_sensitive_input("textarea#comment") is False
    assert is_sensitive_input("#username") is False


def test_click_risk_classification_ordinary_elements() -> None:
    """Verify normal navigation and search buttons are classified as SAFE."""
    assert classify_click_risk("button#search", "Search") == RiskLevel.SAFE
    assert classify_click_risk("a.nav-link", "Documentation") == RiskLevel.SAFE
    assert classify_click_risk("div.tab-header", "Overview") == RiskLevel.SAFE


def test_click_risk_classification_high_impact_actions() -> None:
    """Verify purchase, checkout, payment, booking, and deletion actions require confirmation."""
    assert classify_click_risk("button#buy-now", "Buy Now") == RiskLevel.CONFIRMATION_REQUIRED
    assert classify_click_risk("button.checkout", "Proceed to Checkout") == RiskLevel.CONFIRMATION_REQUIRED
    assert classify_click_risk("button#submit-payment", "Pay $49.99") == RiskLevel.CONFIRMATION_REQUIRED
    assert classify_click_risk("button#delete-account", "Delete Account") == RiskLevel.CONFIRMATION_REQUIRED
    assert classify_click_risk("button.send-mail", "Send Message") == RiskLevel.CONFIRMATION_REQUIRED
    assert classify_click_risk("button#confirm-booking", "Confirm Booking") == RiskLevel.CONFIRMATION_REQUIRED


def test_sanitize_sensitive_value() -> None:
    """Verify sensitive input values are redacted."""
    assert sanitize_sensitive_value("my_super_secret_password_123") == "***REDACTED***"
    assert sanitize_sensitive_value("4111222233334444") == "***REDACTED***"
    assert sanitize_sensitive_value("") == ""
