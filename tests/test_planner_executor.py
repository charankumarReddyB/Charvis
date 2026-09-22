"""
Unit tests for CHARVIS TaskExecutor (Phase 14).
"""

from typing import Any, Dict
import pytest
from core.safety import RiskLevel, SafetyManager
from planner.evaluator import ResultEvaluator
from planner.executor import TaskExecutor
from planner.models import (
    PlannerStateError,
    StepStatus,
    Task,
    TaskStatus,
    TaskStep,
)
from planner.planner import MockTaskPlanner
from tools.calculator import CalculatorTool
from tools.filesystem import DeleteFileTool, ReadFileTool
from tools.registry import ToolRegistry
from tools.router import ToolRouter


@pytest.fixture
def executor_setup():
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(ReadFileTool())
    registry.register(DeleteFileTool())

    safety_mgr = SafetyManager(default_policy_strict=True)
    router = ToolRouter(registry, safety_mgr)
    evaluator = ResultEvaluator(max_retries=1)
    executor = TaskExecutor(tool_router=router, safety_manager=safety_mgr, evaluator=evaluator)
    return registry, safety_mgr, router, executor


def test_executor_successful_run(executor_setup):
    """Verify clean sequential execution of all steps through ToolRouter."""
    _, _, _, executor = executor_setup

    step1 = TaskStep(order=1, tool_name="calculator", arguments={"expression": "10+10"}, description="Step 1")
    step2 = TaskStep(order=2, tool_name="calculator", arguments={"expression": "20*2"}, description="Step 2")
    task = Task(goal="Sequential math", steps=[step1, step2], status=TaskStatus.READY)

    result_task = executor.run_task(task)

    assert result_task.status == TaskStatus.COMPLETED
    assert result_task.steps[0].status == StepStatus.COMPLETED
    assert result_task.steps[1].status == StepStatus.COMPLETED
    assert result_task.context.results["step_1"] == 20
    assert result_task.context.results["step_2"] == 40



def test_executor_pauses_for_confirmation_without_callback(executor_setup):
    """Verify executor pauses with WAITING_CONFIRMATION when confirmation is required and no callback is provided."""
    _, _, _, executor = executor_setup

    step1 = TaskStep(
        order=1,
        tool_name="delete_file",
        arguments={"path": "report.pdf"},
        description="Delete file",
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
        requires_confirmation=True,
    )
    task = Task(goal="Delete file", steps=[step1], status=TaskStatus.READY, requires_confirmation=True)

    result_task = executor.run_task(task, confirmation_callback=None)

    assert result_task.status == TaskStatus.WAITING_CONFIRMATION
    assert result_task.steps[0].status == StepStatus.WAITING_CONFIRMATION


def test_executor_user_denial_stops_task(executor_setup):
    """Verify that user denial halts the task immediately with FAILED status and no retries."""
    _, _, _, executor = executor_setup

    step1 = TaskStep(
        order=1,
        tool_name="delete_file",
        arguments={"path": "important.txt"},
        description="Delete file",
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
        requires_confirmation=True,
    )
    task = Task(goal="Delete file", steps=[step1], status=TaskStatus.READY)

    # Denying callback
    def deny_callback(tool_name: str, args: Dict[str, Any], risk: RiskLevel, msg=None) -> bool:
        return False

    result_task = executor.run_task(task, confirmation_callback=deny_callback)

    assert result_task.status == TaskStatus.FAILED
    assert result_task.steps[0].status == StepStatus.FAILED
    assert result_task.steps[0].retries_count == 0


def test_executor_pause_and_resume(executor_setup):
    """Verify pausing a running task and resuming it to completion."""
    _, _, _, executor = executor_setup

    step1 = TaskStep(order=1, tool_name="calculator", arguments={"expression": "1+1"})
    step2 = TaskStep(order=2, tool_name="calculator", arguments={"expression": "2+2"})
    task = Task(goal="Two steps", steps=[step1, step2], status=TaskStatus.RUNNING)

    # Pause task
    executor.pause_task(task, reason="User requested pause")
    assert task.status == TaskStatus.PAUSED

    # Resume task
    resumed = executor.resume_task(task)
    assert resumed.status == TaskStatus.COMPLETED
    assert resumed.steps[0].status == StepStatus.COMPLETED
    assert resumed.steps[1].status == StepStatus.COMPLETED


def test_executor_cancel_task(executor_setup):
    """Verify cancel_task transitions task and running steps to CANCELLED."""
    _, _, _, executor = executor_setup

    step1 = TaskStep(order=1, tool_name="calculator", arguments={"expression": "1+1"})
    task = Task(goal="Cancelled goal", steps=[step1], status=TaskStatus.READY)

    cancelled = executor.cancel_task(task, reason="Abort operation")
    assert cancelled.status == TaskStatus.CANCELLED
    assert cancelled.steps[0].status == StepStatus.CANCELLED

    # Cannot run a cancelled task
    with pytest.raises(PlannerStateError):
        executor.run_task(cancelled)
