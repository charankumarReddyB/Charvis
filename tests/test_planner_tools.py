"""
Unit tests for CHARVIS Task Planner Tools (Phase 14).
"""

from typing import Any, Dict, List, Optional
import pytest
from core.brain import AIBrain
from core.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from core.safety import RiskLevel, SafetyManager
from planner.evaluator import ResultEvaluator
from planner.executor import TaskExecutor
from planner.models import StepStatus, Task, TaskStatus, TaskStep
from planner.planner import MockTaskPlanner
from tools.calculator import CalculatorTool
from tools.planner import (
    CancelTaskTool,
    CreateTaskTool,
    GetTaskStatusTool,
    ListTasksTool,
    PauseTaskTool,
    ResumeTaskTool,
    RunTaskTool,
    TaskStore,
)
from tools.registry import ToolRegistry
from tools.router import ToolRouter


class MockProvider(BaseLLMProvider):
    def __init__(self, responses: Optional[List[LLMResponse]] = None):
        self._responses = list(responses or [])

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-model"

    def generate_response(self, messages, tools=None, temperature=0.7, max_tokens=None) -> LLMResponse:
        if self._responses:
            return self._responses.pop(0)
        return LLMResponse(content="Mock default response", tool_calls=[])


@pytest.fixture
def planner_tools_fixture():
    store = TaskStore(max_active_tasks=5)
    registry = ToolRegistry()
    registry.register(CalculatorTool())

    steps = [
        {"step_number": 1, "tool_name": "calculator", "arguments": {"expression": "50+50"}, "description": "Step 1"},
        {"step_number": 2, "tool_name": "calculator", "arguments": {"expression": "100*2"}, "description": "Step 2"},
    ]
    planner = MockTaskPlanner(planned_steps=steps, tool_registry=registry)
    safety_mgr = SafetyManager()
    router = ToolRouter(registry, safety_mgr)
    executor = TaskExecutor(tool_router=router, safety_manager=safety_mgr, planner=planner)

    create_tool = CreateTaskTool(planner=planner, store=store)
    run_tool = RunTaskTool(executor=executor, store=store)
    pause_tool = PauseTaskTool(executor=executor, store=store)
    resume_tool = ResumeTaskTool(executor=executor, store=store)
    cancel_tool = CancelTaskTool(executor=executor, store=store)
    status_tool = GetTaskStatusTool(store=store)
    list_tool = ListTasksTool(store=store)

    return {
        "store": store,
        "create_tool": create_tool,
        "run_tool": run_tool,
        "pause_tool": pause_tool,
        "resume_tool": resume_tool,
        "cancel_tool": cancel_tool,
        "status_tool": status_tool,
        "list_tool": list_tool,
    }


def test_task_store_eviction():
    """Verify TaskStore evicts terminal tasks when capacity is reached."""
    store = TaskStore(max_active_tasks=2)

    task1 = Task(goal="Goal 1", status=TaskStatus.COMPLETED)
    task2 = Task(goal="Goal 2", status=TaskStatus.RUNNING)
    task3 = Task(goal="Goal 3", status=TaskStatus.READY)

    store.add(task1)
    store.add(task2)
    assert store.count() == 2

    # Adding task3 should evict terminal task1
    store.add(task3)
    assert store.count() == 2
    assert store.get(task1.task_id) is None
    assert store.get(task2.task_id) is not None
    assert store.get(task3.task_id) is not None


def test_create_and_run_task_flow(planner_tools_fixture):
    """Verify end-to-end task creation, status check, and execution flow."""
    f = planner_tools_fixture

    # 1. Create task
    create_res = f["create_tool"].execute(goal="Compute 50+50 then * 2")
    task_id = create_res["task_id"]
    assert create_res["steps_count"] == 2
    assert create_res["status"] == TaskStatus.READY.value

    # 2. Get status before run
    status_res = f["status_tool"].execute(task_id=task_id)
    assert status_res["status"] == TaskStatus.READY.value
    assert len(status_res["steps"]) == 2

    # 3. Run task
    run_res = f["run_tool"].execute(task_id=task_id)
    assert run_res["status"] == TaskStatus.COMPLETED.value
    assert run_res["completed_steps"] == 2
    assert run_res["results"]["step_1"] == 100
    assert run_res["results"]["step_2"] == 200


    # 4. List tasks
    list_res = f["list_tool"].execute(status="completed")
    assert list_res["count"] == 1
    assert list_res["tasks"][0]["task_id"] == task_id


def test_cancel_task_tool(planner_tools_fixture):
    """Verify cancel_task marks task cancelled."""
    f = planner_tools_fixture
    create_res = f["create_tool"].execute(goal="Task to cancel")
    task_id = create_res["task_id"]

    cancel_res = f["cancel_tool"].execute(task_id=task_id, reason="Testing cancellation")
    assert cancel_res["status"] == TaskStatus.CANCELLED.value

    status_res = f["status_tool"].execute(task_id=task_id)
    assert status_res["status"] == TaskStatus.CANCELLED.value


def test_brain_registration_and_tools_count():
    """Verify that AIBrain automatically registers all 68 tools including the 7 Phase 14 tools."""
    brain = AIBrain(provider=MockProvider())
    assert brain.registry.count() == 68

    planner_tools = [
        "create_task",
        "run_task",
        "pause_task",
        "resume_task",
        "cancel_task",
        "get_task_status",
        "list_tasks",
    ]
    for pt in planner_tools:
        tool = brain.registry.get(pt)
        assert tool is not None, f"Tool '{pt}' was not registered in AIBrain"
        assert tool.risk_level == RiskLevel.SAFE
