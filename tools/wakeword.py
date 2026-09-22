"""CHARVIS Wake-Word Tools.

Provides tools for inspecting and controlling the wake-word standby subsystem.
All tools are classified as SAFE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from core.safety import RiskLevel
from tools.base import BaseTool
from tools.schemas import ToolSchema
from wakeword.states import WakeWordState

if TYPE_CHECKING:
    from wakeword.engine import WakeWordEngine


# Global reference to active engine instance if running
_ACTIVE_ENGINE: Optional[WakeWordEngine] = None


def set_active_engine(engine: Optional[WakeWordEngine]) -> None:
    """Register the active WakeWordEngine instance for tool inspection."""
    global _ACTIVE_ENGINE
    _ACTIVE_ENGINE = engine


def get_active_engine() -> Optional[WakeWordEngine]:
    """Retrieve the currently active WakeWordEngine, if any."""
    return _ACTIVE_ENGINE


class WakeWordStatusTool(BaseTool):
    """Tool to inspect the current state of the wake-word standby subsystem."""

    def __init__(self, engine: Optional[WakeWordEngine] = None) -> None:
        self._engine = engine

    @property
    def name(self) -> str:
        return "get_wakeword_status"

    @property
    def description(self) -> str:
        return (
            "Check the current status and state of the wake-word standby subsystem. "
            "Returns whether wake-word mode is enabled, disabled, standby, listening, "
            "processing, stopped, or error, along with the configured wake phrase."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        engine = self._engine or get_active_engine()
        if engine is None or engine.state == WakeWordState.STOPPED:
            return {
                "success": True,
                "enabled": False,
                "state": "stopped",
                "wake_phrase": "hey charvis",
                "message": "Wake-word mode is currently disabled (stopped).",
            }

        state_str = engine.state.value.lower()
        is_enabled = engine.state in {
            WakeWordState.STANDBY,
            WakeWordState.LISTENING,
            WakeWordState.PROCESSING,
            WakeWordState.SPEAKING,
        }

        return {
            "success": True,
            "enabled": is_enabled,
            "state": state_str,
            "wake_phrase": engine.detector.wake_phrase,
            "last_error": engine.last_error,
            "message": f"Wake-word mode is currently {state_str}.",
        }


class EnableWakeWordTool(BaseTool):
    """Tool to enable wake-word standby mode when explicitly requested by user."""

    def __init__(self, engine: Optional[WakeWordEngine] = None) -> None:
        self._engine = engine

    @property
    def name(self) -> str:
        return "enable_wakeword"

    @property
    def description(self) -> str:
        return (
            "Enable wake-word standby mode. Do NOT call this tool silently without "
            "an explicit user request to activate wake-word or standby mode."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        engine = self._engine or get_active_engine()
        if engine is None:
            return {
                "success": False,
                "error": "WakeWordEngine is not initialized.",
                "message": "Cannot enable wake-word mode because the engine is not initialized.",
            }

        if engine.state == WakeWordState.STANDBY:
            return {
                "success": True,
                "message": f"Wake-word mode is already active and listening for '{engine.detector.wake_phrase}'.",
            }

        try:
            engine.start()
            return {
                "success": True,
                "message": f"Wake-word mode enabled. Listening for '{engine.detector.wake_phrase}'.",
            }
        except Exception as err:
            return {
                "success": False,
                "error": str(err),
                "message": f"Failed to enable wake-word mode: {err}",
            }


class DisableWakeWordTool(BaseTool):
    """Tool to disable wake-word standby mode."""

    def __init__(self, engine: Optional[WakeWordEngine] = None) -> None:
        self._engine = engine

    @property
    def name(self) -> str:
        return "disable_wakeword"

    @property
    def description(self) -> str:
        return "Disable wake-word standby mode and stop microphone monitoring."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        engine = self._engine or get_active_engine()
        if engine is None or engine.state == WakeWordState.STOPPED:
            return {
                "success": True,
                "message": "Wake-word mode is already stopped.",
            }

        try:
            engine.stop()
            return {
                "success": True,
                "message": "Wake-word mode disabled and microphone monitoring stopped.",
            }
        except Exception as err:
            return {
                "success": False,
                "error": str(err),
                "message": f"Failed to stop wake-word mode: {err}",
            }
