"""
Base tool abstraction for CHARVIS.
Provides strong typing, schema validation, and risk categorization.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from core.safety import RiskLevel
from tools.schemas import ToolSchema


class ToolValidationError(Exception):
    """Raised when arguments fail schema validation."""
    pass


class BaseTool(ABC):
    """
    Abstract base class for all CHARVIS tools.
    Encapsulates tool execution, input validation, and risk specification.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier name for the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable explanation of what the tool does."""
        pass

    @property
    @abstractmethod
    def schema(self) -> ToolSchema:
        """Tool argument schema."""
        pass

    @property
    def risk_level(self) -> RiskLevel:
        """Risk classification tier (defaults to SAFE)."""
        return RiskLevel.SAFE

    def get_risk_level(self, arguments: Dict[str, Any]) -> RiskLevel:
        """Dynamic risk level evaluation based on invocation arguments (defaults to self.risk_level)."""
        return self.risk_level

    def get_confirmation_message(self, arguments: Dict[str, Any]) -> Optional[str]:
        """Optional descriptive warning message for confirmation-required execution."""
        return None

    def validate_arguments(self, arguments: Dict[str, Any]) -> None:
        """
        Validate passed arguments against the tool's schema.
        Raises ToolValidationError on missing required fields or invalid types.
        """
        schema = self.schema
        provided_keys = set(arguments.keys())

        # Check required fields
        for param in schema.parameters:
            if param.required and param.name not in provided_keys:
                raise ToolValidationError(
                    f"Missing required parameter '{param.name}' for tool '{self.name}'."
                )

        # Validate types
        type_mapping = {
            "string": (str,),
            "number": (int, float),
            "integer": (int,),
            "boolean": (bool,),
            "array": (list, tuple),
            "object": (dict,),
        }

        for param in schema.parameters:
            if param.name in arguments:
                val = arguments[param.name]
                if val is not None and param.param_type in type_mapping:
                    expected = type_mapping[param.param_type]
                    # Note: in Python, bool is a subclass of int, so handle boolean cleanly
                    if param.param_type in ("number", "integer") and isinstance(val, bool):
                        raise ToolValidationError(
                            f"Parameter '{param.name}' expects {param.param_type}, got boolean {val}."
                        )
                    if not isinstance(val, expected):
                        raise ToolValidationError(
                            f"Parameter '{param.name}' expects {param.param_type}, got {type(val).__name__}."
                        )

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """
        Execute the tool with validated arguments.

        :param kwargs: Keyword arguments conforming to schema.
        :return: Execution data or result.
        """
        pass
