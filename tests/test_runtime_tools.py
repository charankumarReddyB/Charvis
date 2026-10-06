"""
Unit tests for Phase 16 Runtime and Startup tools (Phase 16).
Verifies registration, execution, and correct risk level categorization.
"""

from unittest.mock import MagicMock
import pytest

from core.safety import RiskLevel
from tools.registry import ToolRegistry
from tools.runtime import (
    DisableStartupTool,
    EnableStartupTool,
    GetRuntimeHealthTool,
    GetRuntimeStatusTool,
    GetStartupStatusTool,
    RestartRuntimeTool,
    StartRuntimeTool,
    StopRuntimeTool,
)


def test_runtime_tools_registration_and_risk_levels():
    """Verify all 7 Phase 16 tools register with correct risk levels."""
    registry = ToolRegistry()

    t_status = GetRuntimeStatusTool()
    t_health = GetRuntimeHealthTool()
    t_startup_status = GetStartupStatusTool()
    t_stop = StopRuntimeTool()
    t_restart = RestartRuntimeTool()
    t_enable_startup = EnableStartupTool()
    t_disable_startup = DisableStartupTool()

    # Register
    registry.register(t_status)
    registry.register(t_health)
    registry.register(t_startup_status)
    registry.register(t_stop)
    registry.register(t_restart)
    registry.register(t_enable_startup)
    registry.register(t_disable_startup)

    assert registry.count() == 7

    # SAFE tools
    assert t_status.risk_level == RiskLevel.SAFE
    assert t_health.risk_level == RiskLevel.SAFE
    assert t_startup_status.risk_level == RiskLevel.SAFE

    # CONFIRMATION_REQUIRED tools
    assert t_stop.risk_level == RiskLevel.CONFIRMATION_REQUIRED
    assert t_restart.risk_level == RiskLevel.CONFIRMATION_REQUIRED
    assert t_enable_startup.risk_level == RiskLevel.CONFIRMATION_REQUIRED
    assert t_disable_startup.risk_level == RiskLevel.CONFIRMATION_REQUIRED


def test_start_runtime_tool_risk_level():
    """Verify StartRuntimeTool also requires confirmation."""
    tool = StartRuntimeTool()
    assert tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED


def test_get_runtime_status_tool_execution():
    """Verify GetRuntimeStatusTool execution returns status dictionary."""
    mock_mgr = MagicMock()
    mock_status = MagicMock()
    mock_status.to_dict.return_value = {"state": "RUNNING", "uptime": 10.0}
    mock_mgr.get_status.return_value = mock_status

    tool = GetRuntimeStatusTool(manager=mock_mgr)
    result = tool.execute()

    assert result["state"] == "RUNNING"
    assert result["uptime"] == 10.0


def test_get_startup_status_tool_execution():
    """Verify GetStartupStatusTool execution."""
    mock_startup = MagicMock()
    mock_st = MagicMock()
    mock_st.to_dict.return_value = {"enabled": False, "method": "startup_folder"}
    mock_startup.get_status.return_value = mock_st

    tool = GetStartupStatusTool(startup_manager=mock_startup)
    result = tool.execute()

    assert result["enabled"] is False
    assert result["method"] == "startup_folder"
