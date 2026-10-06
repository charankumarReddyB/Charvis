"""
Security regression suite ensuring Phase 1–16 invariants remain intact (Phase 17).
"""

import pytest
from core.brain import AIBrain
from core.safety import RiskLevel, SafetyManager
from tools.router import ToolRouter


def test_tool_count_is_strictly_75():
    """Verify tool registry contains exactly 75 active tools."""
    brain = AIBrain()
    assert brain.registry.count() == 75


def test_safety_manager_is_authoritative():
    """Verify safety manager requires confirmation for high-risk actions."""
    safety = SafetyManager()
    assert safety.requires_confirmation(RiskLevel.CONFIRMATION_REQUIRED) is True
    assert safety.requires_confirmation(RiskLevel.HIGH_RISK) is True
    assert safety.requires_confirmation(RiskLevel.SAFE) is False


def test_tool_router_denial_blocks_execution():
    """Verify ToolRouter aborts execution if safety manager denies confirmation."""
    safety = SafetyManager()
    router = ToolRouter(safety_manager=safety)

    brain = AIBrain()
    delete_tool = brain.registry.get("delete_file")
    assert delete_tool is not None
    router.register(delete_tool)

    # Deny callback
    result = router.execute_tool(
        tool_name="delete_file",
        arguments={"path": "test.txt"},
        confirmation_callback=lambda *a, **k: False,
    )

    assert result.success is False
    assert "denied" in result.error.lower()


def test_critical_tools_require_confirmation():
    """Verify state-altering tools require confirmation."""
    brain = AIBrain()
    tools_requiring_confirm = [
        "close_application",
        "type_text",
        "hotkey",
        "write_file",
        "delete_file",
        "delete_directory",
        "lock_workstation",
        "shutdown_system",
        "restart_system",
        "stop_runtime",
        "restart_runtime",
        "enable_startup",
        "disable_startup",
    ]

    for tool_name in tools_requiring_confirm:
        tool = brain.registry.get(tool_name)
        assert tool is not None, f"Tool '{tool_name}' must be registered"
        assert tool.risk_level in (RiskLevel.CONFIRMATION_REQUIRED, RiskLevel.HIGH_RISK), (
            f"Tool '{tool_name}' must require confirmation, got {tool.risk_level}"
        )
