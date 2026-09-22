"""
Tool schemas, parameters, and result data structures for CHARVIS.
Provider-agnostic definitions with conversion utilities.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolParameter:
    """Definition of a single parameter accepted by a tool."""
    name: str
    param_type: str  # 'string', 'number', 'integer', 'boolean', 'array', 'object'
    description: str
    required: bool = True
    default: Optional[Any] = None

    def to_json_schema(self) -> Dict[str, Any]:
        """Convert parameter definition to JSON Schema property format."""
        schema: Dict[str, Any] = {
            "type": self.param_type,
            "description": self.description,
        }
        if self.default is not None:
            schema["default"] = self.default
        return schema


@dataclass
class ToolSchema:
    """Complete specification of a tool's capabilities and arguments."""
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)

    def to_json_schema(self) -> Dict[str, Any]:
        """Convert full tool schema to standard JSON Schema for function parameters."""
        properties: Dict[str, Any] = {}
        required: List[str] = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

    def to_openai_format(self) -> Dict[str, Any]:
        """Format schema according to OpenAI function-calling specification."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.to_json_schema(),
            },
        }


@dataclass
class ToolResult:
    """Structured outcome of a tool execution."""
    success: bool
    tool_name: str
    data: Any = None
    error: Optional[str] = None

    def to_display_string(self) -> str:
        """Return clean, user-friendly representation of the result."""
        if self.success:
            return str(self.data)
        return f"Error executing tool '{self.tool_name}': {self.error}"
