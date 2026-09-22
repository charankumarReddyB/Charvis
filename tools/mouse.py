"""
Mouse Tools for CHARVIS.
Provides structured, safe tool wrappers for moving the mouse, clicking, and scrolling.
Integrates with SafetyManager and enforces strict screen boundaries and rate limits.
"""

from typing import Any, Dict, Optional
from computer.keyboard import FailSafeTriggeredError
from computer.mouse import MouseController
from core.safety import RiskLevel
from tools.base import BaseTool
from tools.schemas import ToolParameter, ToolSchema


class MoveMouseTool(BaseTool):
    """Tool to move the mouse cursor to absolute screen coordinates."""

    def __init__(self, controller: Optional[MouseController] = None) -> None:
        self._controller = controller or MouseController()

    @property
    def name(self) -> str:
        return "move_mouse"

    @property
    def description(self) -> str:
        return (
            "Move the mouse cursor to absolute screen coordinates (x, y). "
            "Example: move_mouse(x=500, y=300)"
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
                    name="x",
                    param_type="integer",
                    description="Target horizontal screen coordinate (pixels from left)",
                    required=True,
                ),
                ToolParameter(
                    name="y",
                    param_type="integer",
                    description="Target vertical screen coordinate (pixels from top)",
                    required=True,
                ),
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        x = kwargs.get("x")
        y = kwargs.get("y")
        try:
            return self._controller.move_mouse(x=x, y=y)
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


class ClickTool(BaseTool):
    """Tool to click the mouse button at the current cursor position."""

    def __init__(self, controller: Optional[MouseController] = None) -> None:
        self._controller = controller or MouseController()

    @property
    def name(self) -> str:
        return "click"

    @property
    def description(self) -> str:
        return (
            "Click the mouse button at the current cursor position. "
            "Example: click(button='left', clicks=1)"
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
                    name="button",
                    param_type="string",
                    description="Mouse button to click: 'left', 'right', or 'middle' (default 'left')",
                    required=False,
                    default="left",
                ),
                ToolParameter(
                    name="clicks",
                    param_type="integer",
                    description="Number of clicks: 1 for single click, 2 for double click (default 1)",
                    required=False,
                    default=1,
                ),
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        button = str(kwargs.get("button", "left"))
        clicks = int(kwargs.get("clicks", 1))
        try:
            return self._controller.click(button=button, clicks=clicks)
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


class DoubleClickTool(BaseTool):
    """Tool to perform a double-click with the mouse at current cursor position."""

    def __init__(self, controller: Optional[MouseController] = None) -> None:
        self._controller = controller or MouseController()

    @property
    def name(self) -> str:
        return "double_click"

    @property
    def description(self) -> str:
        return (
            "Double-click the mouse button at current cursor position. "
            "Example: double_click(button='left')"
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
                    name="button",
                    param_type="string",
                    description="Mouse button to double click ('left', 'right', or 'middle')",
                    required=False,
                    default="left",
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        button = str(kwargs.get("button", "left"))
        try:
            return self._controller.double_click(button=button)
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


class ScrollTool(BaseTool):
    """Tool to scroll the mouse wheel up or down."""

    def __init__(self, controller: Optional[MouseController] = None) -> None:
        self._controller = controller or MouseController()

    @property
    def name(self) -> str:
        return "scroll"

    @property
    def description(self) -> str:
        return (
            "Scroll the mouse wheel. Positive amount scrolls up; negative amount scrolls down. "
            "Example: scroll(amount=5) or scroll(amount=-5)"
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
                    name="amount",
                    param_type="integer",
                    description="Number of scroll units (positive = up, negative = down, range [-100, 100])",
                    required=True,
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        amount = kwargs.get("amount")
        try:
            return self._controller.scroll(amount=amount)
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
