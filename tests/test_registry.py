"""
Unit tests for ToolRegistry.
"""

from typing import Any
import pytest

from core.safety import RiskLevel
from tools.base import BaseTool
from tools.registry import ToolRegistry, ToolRegistryError
from tools.schemas import ToolSchema


class SampleTool(BaseTool):
    def __init__(self, tool_name: str = "sample_tool") -> None:
        self._name = tool_name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "A sample tool for testing registry."

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(name=self.name, description=self.description, parameters=[])

    def execute(self, **kwargs: Any) -> Any:
        return "sample result"


def test_registry_registration_and_get():
    """Verify registering and retrieving tools."""
    registry = ToolRegistry()
    tool = SampleTool("tool_a")

    assert not registry.has("tool_a")
    registry.register(tool)

    assert registry.has("tool_a")
    assert registry.get("tool_a") is tool
    assert registry.count() == 1


def test_registry_duplicate_rejection():
    """Verify duplicate tool name registration raises ToolRegistryError."""
    registry = ToolRegistry()
    tool1 = SampleTool("duplicate_tool")
    tool2 = SampleTool("duplicate_tool")

    registry.register(tool1)
    with pytest.raises(ToolRegistryError) as exc_info:
        registry.register(tool2)
    assert "already registered" in str(exc_info.value)


def test_registry_invalid_tool_rejection():
    """Verify registering an invalid object raises ToolRegistryError."""
    registry = ToolRegistry()
    with pytest.raises(ToolRegistryError):
        registry.register("not_a_tool")  # type: ignore

    with pytest.raises(ToolRegistryError):
        registry.register(None)  # type: ignore


def test_registry_unregister():
    """Verify unregistering existing and non-existing tools."""
    registry = ToolRegistry()
    tool = SampleTool("temp_tool")

    registry.register(tool)
    assert registry.has("temp_tool")

    removed = registry.unregister("temp_tool")
    assert removed is True
    assert not registry.has("temp_tool")
    assert registry.get("temp_tool") is None

    # Unregistering non-existent tool returns False
    assert registry.unregister("temp_tool") is False


def test_registry_list_tools_and_schemas():
    """Verify listing all tools and their schemas."""
    registry = ToolRegistry()
    tool1 = SampleTool("tool_1")
    tool2 = SampleTool("tool_2")

    registry.register(tool1)
    registry.register(tool2)

    tools = registry.list_tools()
    assert len(tools) == 2
    assert tool1 in tools
    assert tool2 in tools

    schemas = registry.get_schemas()
    assert len(schemas) == 2
    names = [s.name for s in schemas]
    assert "tool_1" in names
    assert "tool_2" in names
