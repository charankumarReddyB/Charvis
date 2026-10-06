"""
Unit tests for Windows Startup models (Phase 16).
"""

from startup.models import StartupStatus


def test_startup_status_defaults_and_serialization():
    """Verify StartupStatus defaults and round-trip serialization."""
    status = StartupStatus()
    assert status.enabled is False
    assert status.method == "startup_folder"
    assert status.command is None

    d = status.to_dict()
    assert d["enabled"] is False
    assert d["method"] == "startup_folder"

    restored = StartupStatus.from_dict(d)
    assert restored.enabled is False
    assert restored.method == "startup_folder"


def test_startup_status_custom_fields():
    """Verify StartupStatus with populated values."""
    status = StartupStatus(
        enabled=True,
        method="startup_folder",
        command="python main.py --background",
        created_at="2026-09-22T12:00:00Z",
        path="C:\\test\\path",
    )
    d = status.to_dict()
    assert d["enabled"] is True
    assert "main.py --background" in d["command"]

    restored = StartupStatus.from_dict(d)
    assert restored.enabled is True
    assert restored.path == "C:\\test\\path"
