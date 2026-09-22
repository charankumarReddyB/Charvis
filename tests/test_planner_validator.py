"""
Unit tests for CHARVIS Task Planner validator (Phase 14).
"""

import pytest
from core.safety import RiskLevel
from planner.models import (
    MaxStepsExceededError,
    PlanSecurityError,
    PlanValidationError,
    Task,
    TaskStatus,
    TaskStep,
)
from planner.validator import PlanValidator
from tools.calculator import CalculatorTool
from tools.filesystem import DeleteFileTool, ReadFileTool
from tools.registry import ToolRegistry


@pytest.fixture
def test_registry():
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(ReadFileTool())
    registry.register(DeleteFileTool())
    return registry


def test_validator_rejects_empty_goal(test_registry):
    """Verify validator rejects whitespace or empty goals."""
    validator = PlanValidator(test_registry)
    task = Task(goal="   ", steps=[TaskStep(order=1, tool_name="calculator", arguments={"expression": "1+1"})])

    with pytest.raises(PlanValidationError) as exc:
        validator.validate_plan(task)
    assert "Task goal must be a non-empty string" in str(exc.value)


def test_validator_rejects_empty_steps(test_registry):
    """Verify validator rejects tasks with zero steps."""
    validator = PlanValidator(test_registry)
    task = Task(goal="Do something", steps=[])

    with pytest.raises(PlanValidationError) as exc:
        validator.validate_plan(task)
    assert "must contain at least one step" in str(exc.value)


def test_validator_enforces_max_steps_limit(test_registry):
    """Verify plans exceeding max_task_steps are rejected with MaxStepsExceededError."""
    validator = PlanValidator(test_registry, max_steps=5)
    steps = [
        TaskStep(order=i, tool_name="calculator", arguments={"expression": f"{i}+{i}"})
        for i in range(1, 7)
    ]
    task = Task(goal="Six steps", steps=steps)

    with pytest.raises(MaxStepsExceededError) as exc:
        validator.validate_plan(task)
    assert "exceeds maximum step limit" in str(exc.value)


def test_validator_enforces_sequential_ordering(test_registry):
    """Verify step order numbers must be strictly sequential (1, 2, 3...)."""
    validator = PlanValidator(test_registry)
    step1 = TaskStep(order=1, tool_name="calculator", arguments={"expression": "1+1"})
    step2 = TaskStep(order=3, tool_name="calculator", arguments={"expression": "2+2"})
    task = Task(goal="Compute", steps=[step1, step2])

    with pytest.raises(PlanValidationError) as exc:
        validator.validate_plan(task)
    assert "Step ordering violation" in str(exc.value)


def test_validator_rejects_unregistered_tool(test_registry):
    """Verify candidate steps with unknown tools are blocked."""
    validator = PlanValidator(test_registry)
    step1 = TaskStep(order=1, tool_name="nonexistent_alien_tool", arguments={})
    task = Task(goal="Unknown action", steps=[step1])

    with pytest.raises(PlanValidationError) as exc:
        validator.validate_plan(task)
    assert "Unknown tool 'nonexistent_alien_tool'" in str(exc.value)


def test_validator_schema_validation(test_registry):
    """Verify arguments schema is checked against tool requirements."""
    validator = PlanValidator(test_registry)
    # calculator requires "expression" parameter
    step = TaskStep(order=1, tool_name="calculator", arguments={})
    task = Task(goal="Missing expression", steps=[step])

    with pytest.raises(PlanValidationError) as exc:
        validator.validate_plan(task)
    assert "Schema validation failed" in str(exc.value)


def test_validator_rejects_code_injection(test_registry):
    """Verify code injection inside tool arguments triggers PlanSecurityError."""
    validator = PlanValidator(test_registry)
    step = TaskStep(
        order=1,
        tool_name="read_file",
        arguments={"path": "os.system('rm -rf /')"},
    )
    task = Task(goal="Security check", steps=[step])

    with pytest.raises(PlanSecurityError) as exc:
        validator.validate_plan(task)
    assert "illegal executable code" in str(exc.value).lower()



def test_validator_resolves_risk_and_confirmation(test_registry):
    """Verify effective risk levels and confirmation flags are accurately set."""
    validator = PlanValidator(test_registry)
    step1 = TaskStep(order=1, tool_name="calculator", arguments={"expression": "2*2"})
    step2 = TaskStep(order=2, tool_name="delete_file", arguments={"path": "data.csv"})
    task = Task(goal="Calculate and delete", steps=[step1, step2])

    validated_task = validator.validate_plan(task)
    assert validated_task.status == TaskStatus.READY
    assert validated_task.steps[0].risk_level == RiskLevel.SAFE
    assert validated_task.steps[0].requires_confirmation is False

    assert validated_task.steps[1].risk_level == RiskLevel.CONFIRMATION_REQUIRED
    assert validated_task.steps[1].requires_confirmation is True
    assert validated_task.requires_confirmation is True
