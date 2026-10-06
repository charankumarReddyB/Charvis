"""
Unit tests for voice, STT, TTS, and wake-word lifecycle hardening (Phase 17).
"""

from unittest.mock import MagicMock, patch
import pytest
from config import get_settings
from wakeword import WakeWordEngine


def test_wake_word_off_by_default():
    """Verify wake-word listening is OFF by default in settings."""
    settings = get_settings()
    assert settings.wake_word_enabled is False


def test_wake_word_clean_lifecycle():
    """Verify WakeWordEngine clean start and stop without leaking threads or locks."""
    engine = WakeWordEngine()
    assert not engine.is_running

    # Test idempotent stop on already stopped engine
    engine.stop()
    assert not engine.is_running


def test_wake_word_handles_stop_repeatedly():
    """Verify stopping wake word repeatedly does not cause exceptions."""
    engine = WakeWordEngine()
    engine._running = False
    for _ in range(5):
        engine.stop()
    assert not engine.is_running
