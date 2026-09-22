"""
Unit tests for ToolRouter execution, argument validation, and error encapsulation.
"""

from typing import Any
import pytest

from core.safety import RiskLevel, SafetyManager
from tools.base import BaseTool
from tools.registry import ToolRegistry
from tools.router import ToolRouter
from tools.schemas import ToolParameter, ToolSchema


class EchoTool(BaseTool):
    @property
    def name(self) -> str:
        return "echo_tool"

    @property
    def description(self) -> str:
        return "Echoes back the message."

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[ToolParameter(name="message", param_type="string", description="Text to echo")],
        )

    def execute(self, **kwargs: Any) -> Any:
        return f"Echo: {kwargs.get('message')}"


class FlakyTool(BaseTool):
    @property
    def name(self) -> str:
        return "flaky_tool"

    @property
    def description(self) -> str:
        return "Always raises an exception."

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(name=self.name, description=self.description, parameters=[])

    def execute(self, **kwargs: Any) -> Any:
        raise RuntimeError("Something exploded inside the tool!")


def test_router_successful_execution():
    """Verify router executes registered tool with valid arguments."""
    registry = ToolRegistry()
    registry.register(EchoTool())
    router = ToolRouter(registry)

    result = router.execute_tool("echo_tool", {"message": "Hello CHARVIS"})
    assert result.success is True
    assert result.tool_name == "echo_tool"
    assert result.data == "Echo: Hello CHARVIS"
    assert result.error is None


def test_router_tool_not_found():
    """Verify requesting non-existent tool returns error without crashing."""
    registry = ToolRegistry()
    router = ToolRouter(registry)

    result = router.execute_tool("nonexistent_tool", {})
    assert result.success is False
    assert result.tool_name == "nonexistent_tool"
    assert "not recognized" in result.error


def test_router_invalid_arguments():
    """Verify invalid tool arguments return error without crashing."""
    registry = ToolRegistry()
    registry.register(EchoTool())
    router = ToolRouter(registry)

    # Missing required parameter 'message'
    result = router.execute_tool("echo_tool", {})
    assert result.success is False
    assert "Missing required parameter" in result.error

    # Wrong type for 'message' (number instead of string)
    result2 = router.execute_tool("echo_tool", {"message": 999})
    assert result2.success is False
    assert "expects string" in result2.error


def test_router_tool_exception_handling():
    """Verify tool raising an unhandled exception is trapped cleanly."""
    registry = ToolRegistry()
    registry.register(FlakyTool())
    router = ToolRouter(registry)

    result = router.execute_tool("flaky_tool", {})
    assert result.success is False
    assert "Execution failed" in result.error
    assert "Something exploded" in result.error
