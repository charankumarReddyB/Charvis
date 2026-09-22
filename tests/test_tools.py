"""
Unit tests for tool definitions, schemas, and parameter validation.
"""

from typing import Any
import pytest

from core.safety import RiskLevel
from tools.base import BaseTool, ToolValidationError
from tools.schemas import ToolParameter, ToolResult, ToolSchema


class DummyTool(BaseTool):
    """Simple tool for testing validation."""

    @property
    def name(self) -> str:
        return "dummy_tool"

    @property
    def description(self) -> str:
        return "A dummy testing tool."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(name="text", param_type="string", description="Text input", required=True),
                ToolParameter(name="count", param_type="integer", description="Count input", required=False, default=1),
                ToolParameter(name="flag", param_type="boolean", description="Flag input", required=False, default=False),
            ],
        )

    def execute(self, **kwargs: Any) -> Any:
        return kwargs


def test_tool_schema_to_json():
    """Verify tool schema formats correctly as standard JSON Schema."""
    tool = DummyTool()
    schema = tool.schema.to_json_schema()

    assert schema["type"] == "object"
    assert "text" in schema["properties"]
    assert schema["properties"]["text"]["type"] == "string"
    assert schema["required"] == ["text"]
    assert schema["additionalProperties"] is False


def test_tool_schema_to_openai():
    """Verify tool schema formats correctly for OpenAI function calling."""
    tool = DummyTool()
    openai_format = tool.schema.to_openai_format()

    assert openai_format["type"] == "function"
    assert openai_format["function"]["name"] == "dummy_tool"
    assert "parameters" in openai_format["function"]


def test_tool_validation_success():
    """Verify valid arguments pass schema validation."""
    tool = DummyTool()
    # Should not raise
    tool.validate_arguments({"text": "hello", "count": 3, "flag": True})


def test_tool_validation_missing_required():
    """Verify missing required parameter raises ToolValidationError."""
    tool = DummyTool()
    with pytest.raises(ToolValidationError) as exc_info:
        tool.validate_arguments({"count": 3})
    assert "Missing required parameter 'text'" in str(exc_info.value)


def test_tool_validation_wrong_type():
    """Verify argument of incorrect type raises ToolValidationError."""
    tool = DummyTool()
    # text expects string, pass int
    with pytest.raises(ToolValidationError) as exc_info:
        tool.validate_arguments({"text": 12345})
    assert "expects string" in str(exc_info.value)

    # count expects integer, pass boolean (which is int subclass in Python)
    with pytest.raises(ToolValidationError) as exc_info:
        tool.validate_arguments({"text": "ok", "count": True})
    assert "expects integer, got boolean" in str(exc_info.value)


def test_tool_result_display():
    """Verify ToolResult representation."""
    success_result = ToolResult(success=True, tool_name="dummy", data={"status": "done"})
    assert "status" in success_result.to_display_string()

    fail_result = ToolResult(success=False, tool_name="dummy", error="File not found")
    assert "Error executing tool" in fail_result.to_display_string()
    assert "File not found" in fail_result.to_display_string()
