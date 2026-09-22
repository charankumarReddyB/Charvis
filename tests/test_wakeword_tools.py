"""Tests for Wake-Word Tools (Phase 9).

Verifies WakeWordStatusTool, EnableWakeWordTool, DisableWakeWordTool,
tool schemas, SAFE classification, ToolRouter execution, and Phase 8 co-existence.
"""

from unittest.mock import MagicMock
import pytest

from core.brain import AIBrain
from core.safety import RiskLevel, SafetyManager
from tools.registry import ToolRegistry
from tools.router import ToolRouter
from tools.voice import ListenTool, SpeakTool
from tools.wakeword import (
    DisableWakeWordTool,
    EnableWakeWordTool,
    WakeWordStatusTool,
    get_active_engine,
    set_active_engine,
)
from wakeword.detector import MockWakeWordDetector
from wakeword.engine import WakeWordEngine, WakeWordState


@pytest.fixture(autouse=True)
def cleanup_active_engine():
    """Ensure active engine is reset before and after each test."""
    set_active_engine(None)
    yield
    set_active_engine(None)


def test_wakeword_status_tool_metadata() -> None:
    """Verify metadata and SAFE risk level for WakeWordStatusTool."""
    tool = WakeWordStatusTool()
    assert tool.name == "get_wakeword_status"
    assert tool.risk_level == RiskLevel.SAFE
    assert "status" in tool.description.lower()
    schema = tool.schema
    assert schema.name == "get_wakeword_status"
    assert len(schema.parameters) == 0


def test_wakeword_status_when_no_engine_or_stopped() -> None:
    """Verify WakeWordStatusTool reports stopped status when no engine is active."""
    tool = WakeWordStatusTool()
    result = tool.execute()
    assert result["success"] is True
    assert result["enabled"] is False
    assert result["state"] == "stopped"


def test_wakeword_status_with_active_engine() -> None:
    """Verify WakeWordStatusTool reports correct state when engine is in STANDBY."""
    engine = WakeWordEngine(detector=MockWakeWordDetector(wake_phrase="hey charvis"))
    engine.start()
    set_active_engine(engine)

    tool = WakeWordStatusTool()
    result = tool.execute()

    assert result["success"] is True
    assert result["enabled"] is True
    assert result["state"] == "standby"
    assert result["wake_phrase"] == "hey charvis"

    engine.stop()


def test_enable_and_disable_wakeword_tools() -> None:
    """Verify EnableWakeWordTool and DisableWakeWordTool lifecycle execution."""
    engine = WakeWordEngine(detector=MockWakeWordDetector(wake_phrase="hey charvis"))
    set_active_engine(engine)

    enable_tool = EnableWakeWordTool()
    assert enable_tool.name == "enable_wakeword"
    assert enable_tool.risk_level == RiskLevel.SAFE

    # Enable engine
    assert engine.state == WakeWordState.STOPPED
    res_enable = enable_tool.execute()
    assert res_enable["success"] is True
    assert engine.state == WakeWordState.STANDBY

    # Disable engine
    disable_tool = DisableWakeWordTool()
    assert disable_tool.name == "disable_wakeword"
    assert disable_tool.risk_level == RiskLevel.SAFE

    res_disable = disable_tool.execute()
    assert res_disable["success"] is True
    assert engine.state == WakeWordState.STOPPED


def test_wakeword_tools_router_integration() -> None:
    """Verify wake-word tools can be dispatched through ToolRouter."""
    registry = ToolRegistry()
    safety = SafetyManager()
    router = ToolRouter(registry=registry, safety_manager=safety)

    engine = WakeWordEngine(detector=MockWakeWordDetector(wake_phrase="hey charvis"))
    status_tool = WakeWordStatusTool(engine=engine)
    registry.register(status_tool)

    result = router.execute_tool("get_wakeword_status", {})
    assert result.success is True
    assert result.data["state"] == "stopped"


def test_phase_8_voice_tools_remain_functional() -> None:
    """Verify ListenTool and SpeakTool remain fully functional alongside wake-word tools."""
    brain = AIBrain()
    listen_tool = brain.registry.get("listen")
    speak_tool = brain.registry.get("speak")

    assert listen_tool is not None
    assert isinstance(listen_tool, ListenTool)
    assert speak_tool is not None
    assert isinstance(speak_tool, SpeakTool)

    # Both tools still registered and SAFE
    assert listen_tool.risk_level == RiskLevel.SAFE
    assert speak_tool.risk_level == RiskLevel.SAFE
