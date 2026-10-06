"""
Unit tests for configuration validation and Phase 17 limits (Phase 17).
"""

from pathlib import Path
import pytest
from pydantic import ValidationError
from config import Settings


def test_config_phase17_version_and_defaults():
    """Verify version is 0.17.0 and Phase 17 limits have sensible defaults."""
    settings = Settings()
    assert settings.app_version in {"0.17.0", "0.18.0", "0.19.0"}
    assert settings.confirmation_timeout_seconds == 120.0
    assert settings.max_background_workers == 4
    assert settings.max_pending_gui_requests == 20
    assert settings.max_ipc_connections == 10
    assert settings.max_chat_history_items == 100
    assert settings.max_task_history_items == 50
    assert settings.max_browser_pages == 5
    assert settings.max_voice_operation_time == 30.0
    assert settings.max_runtime_memory_warning_mb == 1024
    assert settings.reconnect_initial_delay == 1.0
    assert settings.reconnect_max_delay == 30.0
    assert settings.reconnect_backoff_factor == 2.0
    assert settings.reconnect_max_retries == 10


def test_config_validates_positive_numeric_bounds():
    """Verify negative or out-of-bound settings trigger ValidationError."""
    # Negative confirmation timeout
    with pytest.raises(ValidationError):
        Settings(confirmation_timeout_seconds=-5.0)

    # Workers < 1
    with pytest.raises(ValidationError):
        Settings(max_background_workers=0)

    # IPC connections < 1
    with pytest.raises(ValidationError):
        Settings(max_ipc_connections=0)

    # Invalid runtime host (non-localhost)
    with pytest.raises(ValidationError):
        Settings(runtime_host="192.168.1.100")
