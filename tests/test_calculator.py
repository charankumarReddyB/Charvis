"""
Unit tests for the safe CalculatorTool.
Verifies arithmetic correctness and strict security defenses against code injection.
"""

import pytest
from tools.calculator import CalculatorTool


def test_calculator_basic_arithmetic():
    """Verify standard arithmetic calculations."""
    calc = CalculatorTool()

    assert calc.execute(expression="25 * 18") == 450
    assert calc.execute(expression="10 + 20") == 30
    assert calc.execute(expression="100 - 45") == 55
    assert calc.execute(expression="100 / 4") == 25
    assert calc.execute(expression="10 // 3") == 3
    assert calc.execute(expression="10 % 3") == 1
    assert calc.execute(expression="2 ** 8") == 256


def test_calculator_complex_expression():
    """Verify order of operations and parentheses."""
    calc = CalculatorTool()
    assert calc.execute(expression="(100 / 4) + 15 * 2") == 55
    assert calc.execute(expression="((2 + 3) * 4) - 5") == 15
    assert calc.execute(expression="-5 + 10") == 5
    assert calc.execute(expression="3.5 * 2") == 7


def test_calculator_division_by_zero():
    """Verify division by zero raises ZeroDivisionError cleanly."""
    calc = CalculatorTool()
    with pytest.raises(ZeroDivisionError):
        calc.execute(expression="10 / 0")

    with pytest.raises(ZeroDivisionError):
        calc.execute(expression="10 % 0")


def test_calculator_exponent_limit():
    """Verify huge powers are blocked to prevent DoS."""
    calc = CalculatorTool()
    with pytest.raises(ValueError) as exc_info:
        calc.execute(expression="2 ** 1001")
    assert "exceeds safe limit" in str(exc_info.value)


def test_calculator_empty_and_invalid_syntax():
    """Verify empty expression and syntax errors are caught."""
    calc = CalculatorTool()

    with pytest.raises(ValueError):
        calc.execute(expression="")

    with pytest.raises(ValueError):
        calc.execute(expression="2 + * 3")


# ==============================================================================
# SECURITY INJECTION TESTS
# Verify that arbitrary Python code, function calls, and variable access are blocked
# ==============================================================================

def test_calculator_security_blocks_function_calls():
    """Verify function calls like print() or eval() are blocked."""
    calc = CalculatorTool()
    with pytest.raises(ValueError):
        calc.execute(expression="eval('1 + 1')")

    with pytest.raises(ValueError):
        calc.execute(expression="print('pwned')")


def test_calculator_security_blocks_import():
    """Verify __import__ and os imports are blocked."""
    calc = CalculatorTool()
    with pytest.raises(ValueError):
        calc.execute(expression="__import__('os').system('dir')")


def test_calculator_security_blocks_variable_access():
    """Verify arbitrary variable names and attribute lookups are blocked."""
    calc = CalculatorTool()
    with pytest.raises(ValueError):
        calc.execute(expression="os.name")

    with pytest.raises(ValueError):
        calc.execute(expression="globals()")

    with pytest.raises(ValueError):
        calc.execute(expression="[].__class__.__base__")
