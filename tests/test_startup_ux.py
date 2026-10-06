"""
Unit tests for Startup UX and Windows Startup Integration (Phase 18).
Ensures startup remains user-controlled, idempotent, transparent (.bat launcher),
and supports --tray arguments without elevated privileges.
"""

from pathlib import Path
import pytest

from startup.windows import WindowsStartupManager


def test_startup_manager_tray_argument(tmp_path):
    """Verify enabling startup with --tray includes --tray in batch launcher."""
    mgr = WindowsStartupManager(startup_dir=tmp_path)
    assert mgr.enable(extra_args="--tray --background") is True

    status = mgr.get_status()
    assert status.enabled is True
    assert "--tray --background" in status.command

    # Read batch file content directly
    bat_content = (tmp_path / WindowsStartupManager.ENTRY_FILENAME).read_text(encoding="utf-8")
    assert "--tray" in bat_content
    assert "@echo off" in bat_content

    # Disable cleanly
    assert mgr.disable() is True
    assert mgr.get_status().enabled is False


def test_startup_manager_idempotent_operations(tmp_path):
    """Verify repeated enable and disable calls succeed idempotently."""
    mgr = WindowsStartupManager(startup_dir=tmp_path)

    # Multiple enables
    assert mgr.enable() is True
    assert mgr.enable() is True
    assert mgr.get_status().enabled is True

    # Multiple disables
    assert mgr.disable() is True
    assert mgr.disable() is True
    assert mgr.get_status().enabled is False


def test_startup_manager_no_windows_service_or_registry(tmp_path):
    """Verify WindowsStartupManager strictly operates on startup directory files only."""
    mgr = WindowsStartupManager(startup_dir=tmp_path)
    # Ensure manager attributes and methods do not touch winreg or win32service
    assert not hasattr(mgr, "registry_key")
    assert not hasattr(mgr, "service_name")
    assert mgr.get_status().method == "startup_folder"
