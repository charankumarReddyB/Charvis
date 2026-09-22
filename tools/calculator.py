"""
Safe Calculator Tool for CHARVIS.
Evaluates mathematical expressions using AST parsing without eval() or shell execution.
"""

import ast
import operator
from typing import Any, Union

from core.safety import RiskLevel
from logger import get_logger
from tools.base import BaseTool
from tools.schemas import ToolParameter, ToolSchema

logger = get_logger("CHARVIS.Tool.Calculator")

# Allowed operators mapping
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

MAX_EXPONENT = 1000
MAX_STRING_LENGTH = 200


def _safe_eval_node(node: ast.AST) -> Union[int, float]:
    """Recursively evaluate an AST node using safe mathematical operations."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError(f"Unsupported constant type in expression: {type(node.value).__name__}")

    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            operand = _safe_eval_node(node.operand)
            return SAFE_OPERATORS[op_type](operand)
        raise ValueError(f"Disallowed unary operator: {op_type.__name__}")

    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            left = _safe_eval_node(node.left)
            right = _safe_eval_node(node.right)

            # Security guard against ReDoS or memory exhaustion via huge powers
            if op_type is ast.Pow:
                if right > MAX_EXPONENT or right < -MAX_EXPONENT:
                    raise ValueError(
                        f"Exponent {right} exceeds safe limit of {MAX_EXPONENT}."
                    )
                if abs(left) > 10000 and right > 10:
                    raise ValueError("Base value too large for exponentiation.")

            if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
                raise ZeroDivisionError("Division or modulo by zero.")

            return SAFE_OPERATORS[op_type](left, right)
        raise ValueError(f"Disallowed binary operator: {op_type.__name__}")

    raise ValueError(f"Disallowed expression syntax: {type(node).__name__}")


class CalculatorTool(BaseTool):
    """Harmless demonstration tool for evaluating mathematical expressions safely."""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return (
            "Safely evaluate basic mathematical expressions like '25 * 18', '(100 / 4) + 15', "
            "or '2 ** 8'. Supports +, -, *, /, //, %, ** and parentheses."
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
                    name="expression",
                    param_type="string",
                    description="The mathematical expression to evaluate (e.g., '25 * 18')",
                    required=True,
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Union[int, float]:
        """Execute the mathematical calculation safely."""
        self.validate_arguments(kwargs)
        expr = str(kwargs.get("expression", "")).strip()

        if not expr:
            raise ValueError("Expression cannot be empty.")

        if len(expr) > MAX_STRING_LENGTH:
            raise ValueError(f"Expression exceeds maximum allowed length of {MAX_STRING_LENGTH} characters.")

        logger.debug("Evaluating mathematical expression: %s", expr)

        try:
            # Parse into AST in eval mode
            parsed = ast.parse(expr, mode="eval")
            result = _safe_eval_node(parsed.body)

            # Convert whole numbers (e.g., 450.0) to int for cleaner display
            if isinstance(result, float) and result.is_integer():
                result = int(result)

            logger.info("Calculator successfully evaluated '%s' = %s", expr, result)
            return result

        except SyntaxError as e:
            raise ValueError(f"Invalid mathematical syntax: '{expr}'") from e
