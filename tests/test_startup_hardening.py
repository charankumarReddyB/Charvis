"""
Unit tests for Windows startup integration hardening and idempotency (Phase 17).
"""

from pathlib import Path
import tempfile
import pytest
from core.safety import RiskLevel
from startup.windows import WindowsStartupManager
from tools.runtime import DisableStartupTool, EnableStartupTool


def test_startup_tools_risk_levels():
    """Verify enable_startup and disable_startup require human confirmation."""
    enable_tool = EnableStartupTool()
    assert enable_tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED

    disable_tool = DisableStartupTool()
    assert disable_tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED


def test_startup_manager_enable_disable_idempotency():
    """Verify repeated enable and disable calls do not duplicate or error."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        startup_dir = Path(tmp_dir) / "Startup"
        mgr = WindowsStartupManager(startup_dir=startup_dir)

        # Initially disabled
        assert not mgr.get_status().enabled

        # 1st enable
        assert mgr.enable() is True
        assert mgr.get_status().enabled

        # 2nd enable (idempotent)
        assert mgr.enable() is True
        assert mgr.get_status().enabled

        # 1st disable
        assert mgr.disable() is True
        assert not mgr.get_status().enabled

        # 2nd disable (idempotent)
        assert mgr.disable() is True
        assert not mgr.get_status().enabled
