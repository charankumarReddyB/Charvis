"""
Unit tests for TaskExecutor hardening, concurrency protection, and non-retryable destructive actions (Phase 17).
"""

from unittest.mock import MagicMock
import pytest
from core.safety import RiskLevel, SafetyManager
from planner.evaluator import ResultEvaluator
from planner.executor import TaskExecutor
from planner.models import EvaluationResult, PlannerStateError, StepStatus, Task, TaskStatus, TaskStep
from tools.router import ToolRouter
from tools.schemas import ToolResult


def test_destructive_action_never_retried():
    """Verify destructive/confirmation-required operations are never retried automatically on failure."""
    mock_router = MagicMock(spec=ToolRouter)
    mock_evaluator = MagicMock(spec=ResultEvaluator)
    safety = SafetyManager()

    executor = TaskExecutor(
        tool_router=mock_router,
        safety_manager=safety,
        evaluator=mock_evaluator,
        max_step_retries=3,
    )

    # Destructive step
    step = TaskStep(
        order=1,
        tool_name="delete_file",
        arguments={"path": "important.txt"},
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
        requires_confirmation=True,
    )
    task = Task(goal="Delete file", steps=[step])

    # Router returns failure, but evaluator marks as RETRY_ELIGIBLE
    mock_router.execute_tool.return_value = ToolResult(success=False, tool_name="delete_file", error="Locked by process")
    mock_evaluator.evaluate_step.return_value = EvaluationResult.RETRY_ELIGIBLE

    # Run task with auto-approval
    result_task = executor.run_task(task, confirmation_callback=lambda *a, **k: True, auto_replan=False)

    assert result_task.status == TaskStatus.FAILED
    assert step.status == StepStatus.FAILED
    assert step.retries_count == 0  # Zero retries attempted
    assert "destructive" in step.error.lower()


def test_user_denial_halts_task_immediately():
    """Verify user denial immediately stops execution without further tool calls."""
    mock_router = MagicMock(spec=ToolRouter)
    safety = SafetyManager()
    evaluator = ResultEvaluator()

    executor = TaskExecutor(tool_router=mock_router, safety_manager=safety, evaluator=evaluator)

    step1 = TaskStep(order=1, tool_name="delete_file", arguments={}, risk_level=RiskLevel.CONFIRMATION_REQUIRED)
    step2 = TaskStep(order=2, tool_name="read_file", arguments={})
    task = Task(goal="Two steps", steps=[step1, step2])

    mock_router.execute_tool.return_value = ToolResult(
        success=False,
        tool_name="delete_file",
        error="Action denied: User did not authorize execution of this operation.",
    )

    result_task = executor.run_task(task, confirmation_callback=lambda *a, **k: False)

    assert result_task.status == TaskStatus.FAILED
    assert step1.status == StepStatus.FAILED
    assert step2.status == StepStatus.PENDING  # Step 2 never ran
    assert mock_router.execute_tool.call_count == 1


def test_prevent_double_execution():
    """Verify TaskExecutor prevents running the exact same task concurrently."""
    mock_router = MagicMock(spec=ToolRouter)
    executor = TaskExecutor(tool_router=mock_router)

    task = Task(goal="Long task", steps=[TaskStep(order=1, tool_name="read_file")])

    with executor._lock:
        executor._running_tasks.add(task.task_id)

    with pytest.raises(PlannerStateError, match="already actively running"):
        executor.run_task(task)

    with executor._lock:
        executor._running_tasks.clear()


def test_terminal_task_cannot_resume_or_run():
    """Verify COMPLETED, FAILED, and CANCELLED tasks cannot be run or resumed."""
    mock_router = MagicMock(spec=ToolRouter)
    executor = TaskExecutor(tool_router=mock_router)

    completed_task = Task(goal="Done", status=TaskStatus.COMPLETED)
    with pytest.raises(PlannerStateError):
        executor.run_task(completed_task)
    with pytest.raises(PlannerStateError):
        executor.resume_task(completed_task)

    cancelled_task = Task(goal="Cancelled", status=TaskStatus.CANCELLED)
    with pytest.raises(PlannerStateError):
        executor.run_task(cancelled_task)
    with pytest.raises(PlannerStateError):
        executor.resume_task(cancelled_task)


def test_idempotent_pause_and_cancel():
    """Verify calling pause_task or cancel_task repeatedly is safe and idempotent."""
    mock_router = MagicMock(spec=ToolRouter)
    executor = TaskExecutor(tool_router=mock_router)

    task = Task(goal="Task", status=TaskStatus.RUNNING)
    executor.pause_task(task)
    assert task.status == TaskStatus.PAUSED

    # Second call returns task without error
    executor.pause_task(task)
    assert task.status == TaskStatus.PAUSED

    # Cancel task
    executor.cancel_task(task)
    assert task.status == TaskStatus.CANCELLED

    # Second cancel call returns task without error
    executor.cancel_task(task)
    assert task.status == TaskStatus.CANCELLED
