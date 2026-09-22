"""
Keyboard Tools for CHARVIS.
Provides structured, safe tool wrappers for typing text, pressing keys, and executing hotkeys.
Integrates with SafetyManager to require confirmation for typing and sensitive shortcuts.
"""

from typing import Any, Dict, List, Optional, Union
from computer.keyboard import (
    ComputerSafetyError,
    FailSafeTriggeredError,
    KeyboardController,
    is_high_risk_hotkey,
    normalize_key,
    parse_hotkey_sequence,
)
from core.safety import RiskLevel
from tools.base import BaseTool
from tools.schemas import ToolParameter, ToolSchema


class TypeTextTool(BaseTool):
    """Tool to type text into the currently active desktop application window."""

    def __init__(self, controller: Optional[KeyboardController] = None) -> None:
        self._controller = controller or KeyboardController()

    @property
    def name(self) -> str:
        return "type_text"

    @property
    def description(self) -> str:
        return (
            "Type text into the currently focused desktop application window. "
            "Requires user confirmation. "
            "Example: type_text(text='Hello from CHARVIS')"
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="text",
                    param_type="string",
                    description="Text to type into the active application window",
                    required=True,
                )
            ],
        )

    def get_confirmation_message(self, arguments: Dict[str, Any]) -> Optional[str]:
        text = str(arguments.get("text", ""))
        preview = text[:50] + "..." if len(text) > 50 else text
        return f"Will type {len(text)} character(s) into active window: '{preview}'."

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        text = kwargs.get("text", "")
        try:
            return self._controller.type_text(text)
        except FailSafeTriggeredError as e:
            return {
                "success": False,
                "error": "emergency_stop",
                "message": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "error": "execution_failed",
                "message": str(e),
            }


class PressKeyTool(BaseTool):
    """Tool to press a specific keyboard key (e.g., 'enter', 'escape', 'tab', 'f5')."""

    def __init__(self, controller: Optional[KeyboardController] = None) -> None:
        self._controller = controller or KeyboardController()

    @property
    def name(self) -> str:
        return "press_key"

    @property
    def description(self) -> str:
        return (
            "Press a valid keyboard key (e.g. 'enter', 'escape', 'tab', 'backspace', 'up', 'down', 'f5'). "
            "Example: press_key(key='enter')"
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="key",
                    param_type="string",
                    description="Name of the key to press (e.g. 'enter', 'tab', 'space', 'escape')",
                    required=True,
                ),
                ToolParameter(
                    name="presses",
                    param_type="integer",
                    description="Number of times to press the key (1-10, default 1)",
                    required=False,
                    default=1,
                ),
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        key = str(kwargs.get("key", "")).strip()
        presses = int(kwargs.get("presses", 1))
        try:
            return self._controller.press_key(key=key, presses=presses)
        except FailSafeTriggeredError as e:
            return {
                "success": False,
                "error": "emergency_stop",
                "message": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "error": "execution_failed",
                "message": str(e),
            }


class HotkeyTool(BaseTool):
    """Tool to trigger keyboard shortcuts/hotkeys (e.g. 'ctrl+c', 'alt+tab', 'win+d')."""

    def __init__(self, controller: Optional[KeyboardController] = None) -> None:
        self._controller = controller or KeyboardController()

    @property
    def name(self) -> str:
        return "hotkey"

    @property
    def description(self) -> str:
        return (
            "Trigger a keyboard shortcut / hotkey combination (e.g. 'ctrl+c', 'ctrl+v', 'alt+tab', 'win+d'). "
            "Requires user confirmation. "
            "Example: hotkey(key_combination='ctrl+c')"
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="key_combination",
                    param_type="string",
                    description="Key combination separated by '+' (e.g. 'ctrl+c', 'alt+tab', 'win+d')",
                    required=True,
                )
            ],
        )

    def get_confirmation_message(self, arguments: Dict[str, Any]) -> Optional[str]:
        raw_combo = str(arguments.get("key_combination", "")).strip()
        try:
            norm_keys = parse_hotkey_sequence(raw_combo)
            combo_str = "+".join(norm_keys)
            if is_high_risk_hotkey(norm_keys):
                return (
                    f"[HIGH RISK SHORTCUT] '{combo_str}' will be triggered. "
                    "This action may terminate or close the foreground window or lock the session."
                )
            return f"Will execute keyboard shortcut: '{combo_str}'."
        except Exception as e:
            return f"Invalid shortcut requested: {str(e)}"

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        raw_combo = str(kwargs.get("key_combination", "")).strip()
        try:
            return self._controller.hotkey(raw_combo)
        except FailSafeTriggeredError as e:
            return {
                "success": False,
                "error": "emergency_stop",
                "message": str(e),
            }
        except ComputerSafetyError as e:
            return {
                "success": False,
                "error": "blocked_by_safety_policy",
                "message": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "error": "execution_failed",
                "message": str(e),
            }
