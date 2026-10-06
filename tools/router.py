"""
Tool Router for CHARVIS.
Dispatches tool execution requests, validates inputs, coordinates safety checks, and handles errors safely.
"""

from typing import Any, Callable, Dict, Optional
from core.safety import RiskLevel, SafetyManager
from logger import get_logger
from tools.base import ToolValidationError
from tools.registry import ToolRegistry
from tools.schemas import ToolResult

logger = get_logger("CHARVIS.ToolRouter")


class ToolRouter:
    """Dispatches tool execution requests through safety verification and schema validation."""

    registry: ToolRegistry
    safety_manager: SafetyManager

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        safety_manager: Optional[SafetyManager] = None,
    ) -> None:
        self.registry = registry if registry is not None else ToolRegistry()
        self.safety_manager = safety_manager or SafetyManager()
        logger.debug("ToolRouter initialized with %d tools.", self.registry.count())

    def register(self, tool: Any) -> None:
        """Register a tool into router's registry."""
        self.registry.register(tool)

    def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        confirmation_callback: Optional[Callable[[str, Dict[str, Any], RiskLevel], bool]] = None,
    ) -> ToolResult:
        """
        Execute a requested tool safely.

        1. Locate tool in registry.
        2. Validate arguments against schema.
        3. Perform safety check / confirmation if needed.
        4. Execute tool logic.
        5. Return standardized ToolResult.
        """
        logger.info("Tool execution requested: %s (args: %s)", tool_name, list(arguments.keys()))

        # 1. Lookup tool
        tool = self.registry.get(tool_name)
        if not tool:
            err_msg = f"Tool '{tool_name}' is not recognized or not available."
            logger.warning("Tool not found: %s", tool_name)
            return ToolResult(success=False, tool_name=tool_name, error=err_msg)

        # 2. Validate arguments
        try:
            tool.validate_arguments(arguments)
        except ToolValidationError as e:
            logger.warning("Argument validation failed for '%s': %s", tool_name, str(e))
            return ToolResult(success=False, tool_name=tool_name, error=str(e))
        except Exception as e:
            logger.error("Unexpected error during argument validation for '%s': %s", tool_name, str(e))
            return ToolResult(success=False, tool_name=tool_name, error=f"Validation error: {str(e)}")

        # 3. Safety Authorization Check
        custom_msg = tool.get_confirmation_message(arguments)
        effective_risk = tool.risk_level
        if hasattr(tool, "get_risk_level"):
            try:
                dyn_risk = tool.get_risk_level(arguments)
                if isinstance(dyn_risk, RiskLevel):
                    effective_risk = dyn_risk
            except Exception:
                pass

        authorized = self.safety_manager.verify_action(
            tool_name=tool_name,
            arguments=arguments,
            risk_level=effective_risk,
            confirmation_callback=confirmation_callback,
            custom_message=custom_msg,
        )
        if not authorized:
            logger.info("Tool execution for '%s' was denied by user or safety policy.", tool_name)
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error="Action denied: User did not authorize execution of this operation.",
            )

        # 4. Execute tool logic safely
        try:
            result_data = tool.execute(**arguments)
            logger.info("Tool '%s' executed successfully.", tool_name)
            return ToolResult(success=True, tool_name=tool_name, data=result_data)

        except Exception as e:
            logger.error("Error occurred while executing tool '%s': %s", tool_name, str(e))
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=f"Execution failed: {str(e)}",
            )
