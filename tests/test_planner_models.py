"""
Unit tests for CHARVIS Task Planner models, dataclasses, and state machines (Phase 14).
"""

import pytest
from core.safety import RiskLevel
from planner.models import (
    EvaluationResult,
    MaxReplansExceededError,
    MaxStepsExceededError,
    PlanExecutionError,
    PlannerError,
    PlannerStateError,
    PlanSecurityError,
    PlanValidationError,
    StepStatus,
    Task,
    TaskCancelledError,
    TaskContext,
    TaskExecutionError,
    TaskLimitExceededError,
    TaskStatus,
    TaskStep,
)


def test_task_status_enum_values():
    """Verify all required TaskStatus enum states exist."""
    assert TaskStatus.CREATED.value == "CREATED"
    assert TaskStatus.PLANNING.value == "PLANNING"
    assert TaskStatus.READY.value == "READY"
    assert TaskStatus.PENDING.value == "PENDING"
    assert TaskStatus.RUNNING.value == "RUNNING"
    assert TaskStatus.WAITING_CONFIRMATION.value == "WAITING_CONFIRMATION"
    assert TaskStatus.PAUSED.value == "PAUSED"
    assert TaskStatus.COMPLETED.value == "COMPLETED"
    assert TaskStatus.FAILED.value == "FAILED"
    assert TaskStatus.CANCELLED.value == "CANCELLED"


def test_step_status_enum_values():
    """Verify all required StepStatus enum states exist."""
    assert StepStatus.PENDING.value == "PENDING"
    assert StepStatus.RUNNING.value == "RUNNING"
    assert StepStatus.WAITING_CONFIRMATION.value == "WAITING_CONFIRMATION"
    assert StepStatus.COMPLETED.value == "COMPLETED"
    assert StepStatus.FAILED.value == "FAILED"
    assert StepStatus.SKIPPED.value == "SKIPPED"
    assert StepStatus.CANCELLED.value == "CANCELLED"


def test_evaluation_result_enum_values():
    """Verify all required EvaluationResult enum states exist."""
    assert EvaluationResult.SUCCESS.value == "SUCCESS"
    assert EvaluationResult.FAILED.value == "FAILED"
    assert EvaluationResult.USER_DENIED.value == "USER_DENIED"
    assert EvaluationResult.RETRY_ELIGIBLE.value == "RETRY_ELIGIBLE"
    assert EvaluationResult.TASK_COMPLETE.value == "TASK_COMPLETE"


def test_task_step_lifecycle_transitions():
    """Verify legal and illegal step transitions."""
    step = TaskStep(order=1, tool_name="calculator", arguments={"expression": "2+2"})
    assert step.status == StepStatus.PENDING
    assert step.step_number == 1
    assert step.retries_count == 0

    # Legal transition: PENDING -> RUNNING
    step.transition_to(StepStatus.RUNNING)
    assert step.status == StepStatus.RUNNING
    assert step.started_at is not None

    # Legal transition: RUNNING -> COMPLETED
    step.transition_to(StepStatus.COMPLETED)
    assert step.status == StepStatus.COMPLETED
    assert step.completed_at is not None

    # Illegal transition: COMPLETED -> RUNNING (terminal state)
    with pytest.raises(PlannerStateError):
        step.transition_to(StepStatus.RUNNING)


def test_task_step_serialization():
    """Verify TaskStep serialization to_dict and from_dict roundtrip."""
    step = TaskStep(
        order=2,
        tool_name="read_file",
        arguments={"path": "report.txt"},
        description="Read report",
        risk_level=RiskLevel.SAFE,
        requires_confirmation=False,
    )
    step_dict = step.to_dict()
    assert step_dict["order"] == 2
    assert step_dict["tool_name"] == "read_file"
    assert step_dict["description"] == "Read report"

    restored = TaskStep.from_dict(step_dict)
    assert restored.order == step.order
    assert restored.tool_name == step.tool_name
    assert restored.arguments == step.arguments
    assert restored.status == step.status


def test_task_lifecycle_transitions():
    """Verify legal and illegal task state transitions."""
    task = Task(goal="Calculate sum and report")
    assert task.status == TaskStatus.CREATED
    assert not task.is_finished

    # CREATED -> READY
    task.transition_to(TaskStatus.READY)
    assert task.status == TaskStatus.READY

    # READY -> RUNNING
    task.transition_to(TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING

    # RUNNING -> PAUSED
    task.transition_to(TaskStatus.PAUSED, reason="User paused")
    assert task.status == TaskStatus.PAUSED

    # PAUSED -> RUNNING
    task.transition_to(TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING

    # RUNNING -> COMPLETED
    task.transition_to(TaskStatus.COMPLETED)
    assert task.status == TaskStatus.COMPLETED
    assert task.is_finished

    # Terminal state cannot transition to RUNNING
    with pytest.raises(PlannerStateError):
        task.transition_to(TaskStatus.RUNNING)


def test_task_serialization():
    """Verify Task to_dict and from_dict roundtrip."""
    step1 = TaskStep(order=1, tool_name="calculator", arguments={"expression": "10*5"})
    task = Task(goal="Compute 10*5", steps=[step1])
    task.context.add_execution_log("Task initialized")

    task_dict = task.to_dict()
    assert task_dict["goal"] == "Compute 10*5"
    assert len(task_dict["steps"]) == 1

    restored = Task.from_dict(task_dict)
    assert restored.goal == task.goal
    assert len(restored.steps) == 1
    assert restored.steps[0].tool_name == "calculator"
    assert "Task initialized" in restored.context.execution_logs


def test_exception_hierarchy():
    """Verify custom exception inheritance and classification."""
    assert issubclass(PlanValidationError, PlannerError)
    assert issubclass(PlannerStateError, PlannerError)
    assert issubclass(PlanSecurityError, PlannerError)
    assert issubclass(TaskCancelledError, PlannerError)
    assert issubclass(TaskLimitExceededError, PlannerError)
    assert issubclass(MaxStepsExceededError, TaskLimitExceededError)
    assert issubclass(MaxReplansExceededError, TaskLimitExceededError)
    assert issubclass(TaskExecutionError, PlannerError)
    assert issubclass(PlanExecutionError, TaskExecutionError)
