"""
Plan validation engine for CHARVIS Task Planner (Phase 14).
Validates candidate plans against ToolRegistry, schemas, safety policies, and size limits.
"""

from typing import Any, Dict, List, Optional, Set, Union
from config import get_settings
from core.safety import RiskLevel
from logger import get_logger
from planner.models import (
    MaxStepsExceededError,
    PlanSecurityError,
    PlanValidationError,
    Task,
    TaskLimitExceededError,
    TaskStatus,
    TaskStep,
)
from planner.safety import validate_no_executable_code
from tools.base import ToolValidationError
from tools.registry import ToolRegistry

logger = get_logger("CHARVIS.Planner.Validator")


class PlanValidator:
    """
    Validates complete multi-step task plans before execution starts.
    Guarantees that every tool is registered, every argument conforms to schema,
    steps are ordered sequentially, and limits are strictly respected.
    """

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        max_steps: Optional[int] = None,
    ) -> None:
        self.registry = registry or ToolRegistry()
        settings = get_settings()
        self.max_steps = max_steps if max_steps is not None else settings.max_task_steps

    def validate_plan(
        self,
        task_or_goal: Union[Task, str],
        candidate_steps: Optional[List[Any]] = None,
    ) -> Union[Task, List[TaskStep]]:
        """
        Validate either a Task object or (goal, candidate_steps).
        If given a Task, validates and returns the Task.
        If given (goal, candidate_steps), validates and returns List[TaskStep].
        """
        if isinstance(task_or_goal, Task):
            return self._validate_task(task_or_goal)

        # Handle (goal, candidate_steps)
        goal = str(task_or_goal).strip()
        if not goal:
            raise PlanValidationError("Task goal must be a non-empty string.")

        if candidate_steps is None or not candidate_steps:
            raise PlanValidationError("Task must contain at least one step.")

        if len(candidate_steps) > self.max_steps:
            raise MaxStepsExceededError(
                f"Task exceeds maximum step limit of {self.max_steps} steps (got {len(candidate_steps)})."
            )

        steps: List[TaskStep] = []
        for idx, item in enumerate(candidate_steps):
            if isinstance(item, TaskStep):
                steps.append(item)
            elif isinstance(item, dict):
                order = item.get("order", item.get("step_number", idx + 1))
                tool_name = item.get("tool_name", "")
                args = item.get("arguments", {})
                desc = item.get("description", "")
                steps.append(TaskStep(order=order, tool_name=tool_name, arguments=args, description=desc))
            else:
                raise PlanValidationError(f"Invalid step item type: {type(item).__name__}")

        temp_task = Task(goal=goal, steps=steps)
        validated_task = self._validate_task(temp_task)
        return validated_task.steps

    def _validate_task(self, task: Task) -> Task:
        """
        Internal validation of entire Task structure and all TaskSteps.
        """
        # 1. Validate Goal
        if not isinstance(task.goal, str) or not task.goal.strip():
            raise PlanValidationError("Task goal must be a non-empty string.")

        # 2. Validate Task ID
        if not isinstance(task.id, str) or not task.id.strip():
            raise PlanValidationError("Task ID must be a non-empty string.")

        # 3. Validate Step Count
        if not task.steps:
            raise PlanValidationError("Task must contain at least one step.")

        if len(task.steps) > self.max_steps:
            raise MaxStepsExceededError(
                f"Task exceeds maximum step limit of {self.max_steps} steps (got {len(task.steps)})."
            )

        # 4. Validate Step IDs and Sequential Ordering
        seen_ids: Set[str] = set()
        any_confirmation_required = False

        for index, step in enumerate(task.steps):
            expected_order = index + 1
            if step.order != expected_order:
                raise PlanValidationError(
                    f"Step ordering violation: step at index {index} has order {step.order}, expected {expected_order}."
                )

            if step.id in seen_ids:
                raise PlanValidationError(f"Duplicate step ID detected: '{step.id}'.")
            seen_ids.add(step.id)

            # 5. Validate Tool Resolution
            tool = self.registry.get(step.tool_name)
            if not tool:
                raise PlanValidationError(
                    f"Unknown tool '{step.tool_name}' in step {step.order}. "
                    "The planner cannot reference unregistered tools."
                )

            # 6. Validate No Code Injection
            validate_no_executable_code(step.tool_name, step.arguments)

            # 7. Validate Arguments Against Tool Schema
            try:
                tool.validate_arguments(step.arguments)
            except ToolValidationError as e:
                raise PlanValidationError(
                    f"Schema validation failed for step {step.order} ({step.tool_name}): {e}"
                ) from e
            except Exception as e:
                raise PlanValidationError(
                    f"Unexpected error validating arguments for step {step.order} ({step.tool_name}): {e}"
                ) from e

            # 8. Resolve Effective Risk Level & Confirmation
            effective_risk = tool.risk_level
            if hasattr(tool, "get_risk_level"):
                try:
                    dyn_risk = tool.get_risk_level(step.arguments)
                    if isinstance(dyn_risk, RiskLevel):
                        effective_risk = dyn_risk
                except Exception:
                    pass

            step.risk_level = effective_risk
            step.requires_confirmation = effective_risk in (
                RiskLevel.CONFIRMATION_REQUIRED,
                RiskLevel.HIGH_RISK,
            )

            if step.requires_confirmation:
                any_confirmation_required = True

        task.requires_confirmation = any_confirmation_required

        # Mark READY if currently CREATED or PLANNING
        if task.status in (TaskStatus.CREATED, TaskStatus.PLANNING):
            task.transition_to(TaskStatus.READY)

        logger.debug(
            "Plan validated successfully: Task '%s' (%d steps, confirmation_required=%s)",
            task.id[:8],
            len(task.steps),
            task.requires_confirmation,
        )
        return task
