"""
Unit tests for WindowsStartupManager using sandboxed temporary directories (Phase 16).
Strictly verifies that unit tests NEVER touch the real Windows Startup directory.
"""

from pathlib import Path
import pytest

from startup.windows import WindowsStartupManager


def test_startup_manager_initial_disabled_state(tmp_path):
    """Verify clean temporary directory reports startup disabled."""
    mgr = WindowsStartupManager(startup_dir=tmp_path)
    status = mgr.get_status()

    assert status.enabled is False
    assert status.method == "startup_folder"
    assert status.command is None


def test_startup_manager_enable_and_disable(tmp_path):
    """Verify enable creates batch script and disable removes it safely."""
    mgr = WindowsStartupManager(startup_dir=tmp_path)

    # 1. Enable startup
    assert mgr.enable() is True
    entry = tmp_path / WindowsStartupManager.ENTRY_FILENAME
    assert entry.exists()

    status = mgr.get_status()
    assert status.enabled is True
    assert "main.py" in status.command
    assert "--background" in status.command

    # 2. Repeated enable is idempotent
    assert mgr.enable() is True
    assert entry.exists()

    # 3. Disable startup
    assert mgr.disable() is True
    assert not entry.exists()

    status_disabled = mgr.get_status()
    assert status_disabled.enabled is False

    # 4. Repeated disable is idempotent
    assert mgr.disable() is True


def test_startup_manager_gui_background_arg(tmp_path):
    """Verify passing --gui extra_args includes --gui in launch command."""
    mgr = WindowsStartupManager(startup_dir=tmp_path)
    assert mgr.enable(extra_args="--gui --background") is True

    status = mgr.get_status()
    assert status.enabled is True
    assert "--gui --background" in status.command

    mgr.disable()
