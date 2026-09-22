"""
Unit tests for CHARVIS Task Planners (BaseTaskPlanner, MockTaskPlanner, LLMTaskPlanner) (Phase 14).
"""

import json
import pytest
from core.providers.base import BaseLLMProvider, LLMResponse
from planner.models import (
    MaxReplansExceededError,
    PlanValidationError,
    StepStatus,
    Task,
    TaskStatus,
    TaskStep,
)
from planner.planner import LLMTaskPlanner, MockTaskPlanner
from planner.validator import PlanValidator
from tools.calculator import CalculatorTool
from tools.registry import ToolRegistry


class DummyProvider(BaseLLMProvider):
    def __init__(self, responses):
        self.responses = list(responses)

    @property
    def provider_name(self) -> str:
        return "dummy"

    @property
    def model_name(self) -> str:
        return "dummy-model"

    def generate_response(self, messages, tools=None, temperature=0.7, max_tokens=None) -> LLMResponse:
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(content="{}", tool_calls=[])


@pytest.fixture
def calc_registry():
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    return reg


def test_mock_task_planner_success(calc_registry):
    """Verify MockTaskPlanner generates a valid Task from preconfigured steps."""
    steps = [
        {"step_number": 1, "tool_name": "calculator", "arguments": {"expression": "2+2"}, "description": "Add 2+2"},
        {"step_number": 2, "tool_name": "calculator", "arguments": {"expression": "4*2"}, "description": "Multiply by 2"},
    ]
    planner = MockTaskPlanner(planned_steps=steps, tool_registry=calc_registry)
    task = planner.plan("Compute simple math")

    assert task.goal == "Compute simple math"
    assert len(task.steps) == 2
    assert task.steps[0].tool_name == "calculator"
    assert task.status == TaskStatus.READY


def test_mock_task_planner_replan(calc_registry):
    """Verify MockTaskPlanner replaces remaining steps during replan."""
    step1 = TaskStep(order=1, tool_name="calculator", arguments={"expression": "1+1"}, status=StepStatus.COMPLETED)
    step2 = TaskStep(order=2, tool_name="calculator", arguments={"expression": "invalid"}, status=StepStatus.FAILED)
    task = Task(goal="Math goal", steps=[step1, step2], current_step=1)

    replan_steps = [
        {"step_number": 2, "tool_name": "calculator", "arguments": {"expression": "2+3"}, "description": "Fixed step"}
    ]
    planner = MockTaskPlanner(replan_steps=replan_steps, tool_registry=calc_registry, max_replans_per_task=2)
    revised_task = planner.replan(task, step2, "Invalid expression")

    assert revised_task.replans_count == 1
    assert len(revised_task.steps) == 2
    assert revised_task.steps[1].arguments == {"expression": "2+3"}
    assert revised_task.status == TaskStatus.READY


def test_mock_task_planner_exceeds_max_replans(calc_registry):
    """Verify MaxReplansExceededError is raised when replan limit is reached."""
    step1 = TaskStep(order=1, tool_name="calculator", arguments={"expression": "1+1"})
    task = Task(goal="Math", steps=[step1], replan_count=2)

    planner = MockTaskPlanner(
        replan_steps=[{"step_number": 1, "tool_name": "calculator", "arguments": {"expression": "2+2"}}],
        tool_registry=calc_registry,
        max_replans_per_task=2,
    )
    with pytest.raises(MaxReplansExceededError):
        planner.replan(task, step1, "Error")


def test_llm_task_planner_success(calc_registry):
    """Verify LLMTaskPlanner parses valid JSON output into a validated Task."""
    llm_output = {
        "goal": "Calculate 10 + 20",
        "steps": [
            {
                "step_number": 1,
                "tool_name": "calculator",
                "arguments": {"expression": "10+20"},
                "description": "Calculate sum",
            }
        ],
    }
    raw_response = f"```json\n{json.dumps(llm_output)}\n```"
    provider = DummyProvider([LLMResponse(content=raw_response, tool_calls=[])])

    planner = LLMTaskPlanner(provider=provider, tool_registry=calc_registry)
    task = planner.plan("Calculate 10 + 20")

    assert task.goal == "Calculate 10 + 20"
    assert len(task.steps) == 1
    assert task.steps[0].tool_name == "calculator"
    assert task.steps[0].arguments == {"expression": "10+20"}
    assert task.status == TaskStatus.READY


def test_llm_task_planner_invalid_json(calc_registry):
    """Verify LLMTaskPlanner handles malformed JSON gracefully with PlanValidationError."""
    provider = DummyProvider([LLMResponse(content="Sorry, here is the plan: Not valid json at all", tool_calls=[])])
    planner = LLMTaskPlanner(provider=provider, tool_registry=calc_registry)

    with pytest.raises(PlanValidationError) as exc:
        planner.plan("Any goal")
    assert "Invalid JSON" in str(exc.value)
