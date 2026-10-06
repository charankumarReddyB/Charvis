"""
Unit tests for Desktop Notifications and Redaction (Phase 18).
Ensures secrets, passwords, tokens, and API keys are strictly redacted from notifications,
and notifications are debounced without flooding the user.
"""

from unittest.mock import MagicMock
import pytest

from core.notifications import NotificationService, NotificationType


def test_notification_redaction_secrets():
    """Verify SensitiveDataFilter redacts tokens and passwords from notification bodies."""
    service = NotificationService(enabled=True, min_interval_seconds=0.0)
    delivered = []
    service.set_backend(lambda title, msg: delivered.append((title, msg)))

    secret_msg = "Your key is sk-abcdef123456789012345678 and password=SuperSecretPassword123"
    result = service.notify("Test Alert", secret_msg, NotificationType.INFO)

    assert result is True
    assert len(delivered) == 1
    title, msg = delivered[0]
    assert "sk-abcdef123456789012345678" not in msg
    assert "SuperSecretPassword123" not in msg
    assert "[REDACTED" in msg


def test_notification_debouncing_prevents_spam():
    """Verify rapid consecutive notifications of identical type are debounced."""
    service = NotificationService(enabled=True, min_interval_seconds=10.0)
    delivered = []
    service.set_backend(lambda title, msg: delivered.append((title, msg)))

    # First notification should succeed
    res1 = service.notify("Title", "Message 1", NotificationType.INFO)
    assert res1 is True
    assert len(delivered) == 1

    # Immediate second notification with same type should be throttled
    res2 = service.notify("Title", "Message 2", NotificationType.INFO)
    assert res2 is False
    assert len(delivered) == 1

    # Forced notification should bypass debounce
    res3 = service.notify("Title", "Message 3", NotificationType.INFO, force=True)
    assert res3 is True
    assert len(delivered) == 2


def test_notification_disabled_flag():
    """Verify notifications are ignored when disabled."""
    service = NotificationService(enabled=False)
    delivered = []
    service.set_backend(lambda title, msg: delivered.append((title, msg)))

    assert service.notify("Title", "Message", NotificationType.READY) is False
    assert len(delivered) == 0
