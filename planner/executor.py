"""
Task Executor for CHARVIS (Phase 14 & Phase 17 Hardening).
Coordinates sequential execution of a multi-step Task through ToolRouter and SafetyManager.
Enforces task identity validation, destructive operation non-retry, atomic transitions, and concurrency safety.
"""

import threading
from typing import Any, Callable, Dict, Optional, Set

from config import get_settings
from core.safety import RiskLevel, SafetyManager
from logger import get_logger
from planner.evaluator import ResultEvaluator
from planner.models import (
    EvaluationResult,
    MaxReplansExceededError,
    PlannerError,
    PlannerStateError,
    PlanValidationError,
    StepStatus,
    Task,
    TaskStatus,
    TaskStep,
)
from planner.planner import BaseTaskPlanner
from tools.router import ToolRouter
from tools.schemas import ToolResult

logger = get_logger("CHARVIS.TaskExecutor")


class TaskExecutor:
    """
    Coordinates sequential execution of a multi-step Task.
    Strictly adheres to:
      TaskExecutor -> ToolRouter -> SafetyManager -> Tool -> ResultEvaluator
    """

    def __init__(
        self,
        tool_router: ToolRouter,
        safety_manager: Optional[SafetyManager] = None,
        evaluator: Optional[ResultEvaluator] = None,
        planner: Optional[BaseTaskPlanner] = None,
        max_step_retries: Optional[int] = None,
    ) -> None:
        self.tool_router = tool_router
        self.safety_manager = safety_manager or (getattr(tool_router, "safety_manager", None) if tool_router else None) or SafetyManager()
        self.evaluator = evaluator or ResultEvaluator()
        self.planner = planner

        settings = get_settings()
        self.max_step_retries = max_step_retries if max_step_retries is not None else settings.max_step_retries
        self._running_tasks: Set[str] = set()
        self._lock = threading.Lock()

    def is_task_running(self, task_id: str) -> bool:
        """Check if a task is currently executing in this executor."""
        with self._lock:
            return task_id in self._running_tasks

    def run_task(
        self,
        task: Task,
        confirmation_callback: Optional[Callable[[str, Dict[str, Any], RiskLevel], bool]] = None,
        auto_replan: bool = True,
    ) -> Task:
        """
        Execute steps of a task sequentially.
        Enforces task identity validation, destructive operation non-retry, atomic transitions,
        and concurrency protection against double execution.
        """
        if not task or not task.task_id:
            raise PlannerError("Invalid task: task and task_id must be provided.")

        with self._lock:
            if task.task_id in self._running_tasks:
                raise PlannerStateError(f"Task {task.task_id} is already actively running.")
            self._running_tasks.add(task.task_id)

        try:
            logger.info("Executing task %s: '%s' (current step index: %d)", task.task_id, task.goal, task.current_step_index)

            # Transition task to RUNNING if it is READY, PENDING, CREATED, PAUSED, or WAITING_CONFIRMATION
            if task.status in (TaskStatus.READY, TaskStatus.PENDING, TaskStatus.CREATED, TaskStatus.PAUSED, TaskStatus.WAITING_CONFIRMATION):
                task.transition_to(TaskStatus.RUNNING, "Starting or resuming sequential execution")
            elif task.status == TaskStatus.RUNNING:
                pass  # already running
            else:
                raise PlannerStateError(
                    f"Cannot run task {task.task_id} in terminal or invalid state: {task.status.value}"
                )

            while task.current_step_index < len(task.steps):
                # Check if task was externally paused or cancelled
                if task.status == TaskStatus.PAUSED:
                    logger.info("Task %s is PAUSED; halting execution loop.", task.task_id)
                    return task
                if task.status == TaskStatus.CANCELLED:
                    logger.info("Task %s was CANCELLED; halting execution loop.", task.task_id)
                    return task

                step: TaskStep = task.steps[task.current_step_index]

                # Verify step identity and boundary
                if not hasattr(step, "id") or not step.id:
                    step.id = f"{task.task_id}_step_{step.step_number}"

                # If step is already completed, advance to next
                if step.status == StepStatus.COMPLETED:
                    task.current_step_index += 1
                    continue

                # Check if step requires confirmation and no confirmation callback is available
                requires_confirm = step.requires_confirmation or self.safety_manager.requires_confirmation(step.risk_level)
                if requires_confirm and confirmation_callback is None:
                    step.transition_to(StepStatus.WAITING_CONFIRMATION, "Waiting for user confirmation callback")
                    task.transition_to(
                        TaskStatus.WAITING_CONFIRMATION,
                        f"Step {step.step_number} ({step.tool_name}) requires user confirmation",
                    )
                    logger.info("Task %s paused at step %d awaiting user confirmation.", task.task_id, step.step_number)
                    return task

                # Step execution loop (handling retries)
                step_completed = False
                while not step_completed:
                    if step.status != StepStatus.RUNNING:
                        step.transition_to(StepStatus.RUNNING, "Executing tool via ToolRouter")

                    task.context.add_execution_log(
                        f"Executing step {step.step_number}/{len(task.steps)}: {step.tool_name}"
                    )

                    tool_result: ToolResult = self.tool_router.execute_tool(
                        tool_name=step.tool_name,
                        arguments=step.arguments,
                        confirmation_callback=confirmation_callback,
                    )

                    eval_result = self.evaluator.evaluate_step(step, tool_result)

                    if eval_result == EvaluationResult.SUCCESS:
                        step.result = tool_result.data
                        step.transition_to(StepStatus.COMPLETED, "Tool executed successfully")
                        task.context.results[f"step_{step.step_number}"] = tool_result.data
                        task.context.add_execution_log(
                            f"Step {step.step_number} ({step.tool_name}) COMPLETED"
                        )
                        step_completed = True
                        task.current_step_index += 1

                    elif eval_result == EvaluationResult.USER_DENIED:
                        step.error = tool_result.error or "User denied action"
                        step.transition_to(StepStatus.FAILED, "Action denied by user or safety policy")
                        task.context.add_execution_log(
                            f"Step {step.step_number} ({step.tool_name}) DENIED: {step.error}"
                        )
                        task.transition_to(TaskStatus.FAILED, f"Task stopped: Step {step.step_number} denied by user")
                        return task

                    elif eval_result == EvaluationResult.RETRY_ELIGIBLE:
                        # Phase 17 Hardening: Destructive / confirmation-required operations MUST NEVER be retried automatically
                        is_destructive = (
                            step.requires_confirmation
                            or self.safety_manager.requires_confirmation(step.risk_level)
                            or step.risk_level in (RiskLevel.CONFIRMATION_REQUIRED, RiskLevel.HIGH_RISK)
                        )
                        if is_destructive:
                            logger.warning(
                                "Step %d (%s) is destructive or requires confirmation; automatic retry is prohibited.",
                                step.step_number,
                                step.tool_name,
                            )
                            step.error = f"Destructive operation failed: {tool_result.error}. Automatic retry is prohibited."
                            step.transition_to(StepStatus.FAILED, step.error)
                            task.context.add_execution_log(
                                f"Step {step.step_number} ({step.tool_name}) FAILED (destructive retry prohibited): {tool_result.error}"
                            )
                            break

                        if step.retries_count < self.max_step_retries:
                            step.retries_count += 1
                            logger.warning(
                                "Step %d (%s) failed with transient error: %s. Retrying (%d/%d)...",
                                step.step_number,
                                step.tool_name,
                                tool_result.error,
                                step.retries_count,
                                self.max_step_retries,
                            )
                            task.context.add_execution_log(
                                f"Step {step.step_number} retry {step.retries_count}/{self.max_step_retries}"
                            )
                            continue  # retry loop
                        else:
                            # Retries exhausted
                            step.error = tool_result.error
                            step.transition_to(
                                StepStatus.FAILED,
                                f"Step failed after {step.retries_count} retries: {tool_result.error}",
                            )
                            task.context.add_execution_log(
                                f"Step {step.step_number} FAILED after retries: {tool_result.error}"
                            )
                            break

                    else:  # FAILED or NON_RETRYABLE
                        step.error = tool_result.error
                        step.transition_to(StepStatus.FAILED, f"Tool execution failed: {tool_result.error}")
                        task.context.add_execution_log(
                            f"Step {step.step_number} FAILED: {tool_result.error}"
                        )
                        break

                if not step_completed:
                    # Step failed. Check if auto_replan is possible
                    if (
                        auto_replan
                        and self.planner is not None
                        and task.replans_count < getattr(self.planner, "max_replans_per_task", 3)
                    ):
                        logger.info(
                            "Attempting replan for task %s after step %d failure...",
                            task.task_id,
                            step.step_number,
                        )
                        try:
                            task = self.planner.replan(task, step, step.error or "Step failed")
                            task.transition_to(TaskStatus.RUNNING, "Resuming execution after replan")
                            continue  # continue outer while loop with revised steps
                        except (MaxReplansExceededError, PlanValidationError, PlannerError) as pe:
                            logger.warning("Replan failed or max replans exceeded: %s", pe)
                            task.transition_to(TaskStatus.FAILED, f"Replan failed: {pe}")
                            return task
                        except Exception as ex:
                            logger.error("Unexpected error during replan: %s", ex)
                            task.transition_to(TaskStatus.FAILED, f"Replan error: {ex}")
                            return task
                    else:
                        task.transition_to(
                            TaskStatus.FAILED,
                            f"Step {step.step_number} ({step.tool_name}) failed: {step.error}",
                        )
                        return task

            # If all steps are completed
            task.transition_to(TaskStatus.COMPLETED, "All steps completed successfully")
            task.context.add_execution_log(f"Task {task.task_id} COMPLETED successfully")
            logger.info("Task %s completed successfully (%d steps).", task.task_id, len(task.steps))
            return task

        finally:
            with self._lock:
                self._running_tasks.discard(task.task_id)

    def pause_task(self, task: Task, reason: str = "Paused by user request") -> Task:
        """Pause an in-progress task idempotently."""
        if not task or not task.task_id:
            raise PlannerError("Invalid task object.")
        if task.status == TaskStatus.PAUSED:
            logger.info("Task %s is already PAUSED.", task.task_id)
            return task
        if task.status != TaskStatus.RUNNING:
            raise PlannerStateError(f"Cannot pause task in status '{task.status.value}'")
        task.transition_to(TaskStatus.PAUSED, reason)
        logger.info("Task %s paused: %s", task.task_id, reason)
        return task

    def resume_task(
        self,
        task: Task,
        confirmation_callback: Optional[Callable[[str, Dict[str, Any], RiskLevel], bool]] = None,
        auto_replan: bool = True,
    ) -> Task:
        """Resume a paused or confirmation-waiting task idempotently."""
        if not task or not task.task_id:
            raise PlannerError("Invalid task object.")
        if task.status == TaskStatus.RUNNING:
            logger.info("Task %s is already RUNNING.", task.task_id)
            return task
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            raise PlannerStateError(f"Cannot resume completed/terminal task '{task.task_id}' (status: {task.status.value})")
        if task.status not in (TaskStatus.PAUSED, TaskStatus.WAITING_CONFIRMATION, TaskStatus.READY, TaskStatus.PENDING):
            raise PlannerStateError(f"Cannot resume task in status '{task.status.value}'")
        logger.info("Resuming task %s...", task.task_id)
        return self.run_task(task, confirmation_callback=confirmation_callback, auto_replan=auto_replan)

    def cancel_task(self, task: Task, reason: str = "Cancelled by user") -> Task:
        """Cancel an in-progress, pending, or paused task idempotently."""
        if not task or not task.task_id:
            raise PlannerError("Invalid task object.")
        if task.status == TaskStatus.CANCELLED:
            logger.info("Task %s is already CANCELLED.", task.task_id)
            return task
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            raise PlannerStateError(f"Cannot cancel task already in terminal status '{task.status.value}'")

        # If current step is running, mark it cancelled as well
        if task.current_step_index < len(task.steps):
            cur_step = task.steps[task.current_step_index]
            if cur_step.status in (StepStatus.RUNNING, StepStatus.WAITING_CONFIRMATION, StepStatus.PENDING):
                cur_step.transition_to(StepStatus.CANCELLED, reason)

        task.transition_to(TaskStatus.CANCELLED, reason)
        task.context.add_execution_log(f"Task {task.task_id} CANCELLED: {reason}")
        logger.info("Task %s cancelled: %s", task.task_id, reason)
        return task
