"""
Tool Registry for CHARVIS.
Central repository for discovering, registering, and retrieving active tools.
"""

from typing import Dict, List, Optional
from logger import get_logger
from tools.base import BaseTool
from tools.schemas import ToolSchema

logger = get_logger("CHARVIS.ToolRegistry")


class ToolRegistryError(Exception):
    """Raised on tool registration or retrieval failures."""
    pass


class ToolRegistry:
    """Manages active tool instances in the CHARVIS ecosystem."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}
        logger.debug("ToolRegistry initialized.")

    def register(self, tool: BaseTool) -> None:
        """
        Register a tool instance into the registry.
        Rejects non-BaseTool instances and duplicate tool names.
        """
        if not isinstance(tool, BaseTool):
            raise ToolRegistryError(
                f"Invalid tool object: expected BaseTool subclass, got {type(tool).__name__}."
            )

        name = tool.name
        if not name or not isinstance(name, str) or not name.strip():
            raise ToolRegistryError("Tool must define a non-empty string name.")

        if name in self._tools:
            raise ToolRegistryError(
                f"Tool with name '{name}' is already registered in ToolRegistry."
            )

        self._tools[name] = tool
        logger.info("Registered tool: %s (Risk: %s)", name, tool.risk_level.value)

    def unregister(self, name: str) -> bool:
        """
        Remove a tool by name from the registry.
        Returns True if tool was removed, False if it was not found.
        """
        if name in self._tools:
            del self._tools[name]
            logger.info("Unregistered tool: %s", name)
            return True
        return False

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieve a registered tool by name, or None if not found."""
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """Check if a tool exists in the registry."""
        return name in self._tools

    def list_tools(self) -> List[BaseTool]:
        """Return a list of all registered tools."""
        return list(self._tools.values())

    def get_schemas(self) -> List[ToolSchema]:
        """Return a list of ToolSchema for all registered tools."""
        return [tool.schema for tool in self._tools.values()]

    def count(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)
