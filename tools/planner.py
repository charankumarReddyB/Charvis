"""
CHARVIS Task Planner Tools (Phase 14).
Provides controlled tools for multi-step task planning and execution:
- create_task: Decompose a goal into a validated sequential task plan.
- run_task: Sequentially execute the steps of a task.
- pause_task: Pause an in-progress running task.
- resume_task: Resume a paused or confirmation-waiting task.
- cancel_task: Cancel an active or paused task.
- get_task_status: Inspect details, steps, and logs of a task.
- list_tasks: List in-memory tasks filtered by status.
"""

from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from config import get_settings
from core.safety import RiskLevel
from logger import get_logger
from planner.models import (
    PlannerError,
    PlannerStateError,
    PlanValidationError,
    StepStatus,
    Task,
    TaskContext,
    TaskStatus,
)
from tools.base import BaseTool
from tools.schemas import ToolParameter, ToolSchema

if TYPE_CHECKING:
    from planner.evaluator import ResultEvaluator
    from planner.executor import TaskExecutor
    from planner.planner import BaseTaskPlanner, LLMTaskPlanner
    from planner.validator import PlanValidator
    from tools.registry import ToolRegistry
    from tools.router import ToolRouter


logger = get_logger("CHARVIS.Tools.Planner")


class TaskStore:
    """
    In-memory bounded storage for tasks.
    Process-local, does not persist across restarts.
    """

    def __init__(self, max_active_tasks: Optional[int] = None) -> None:
        settings = get_settings()
        self.max_tasks = max_active_tasks or settings.max_active_tasks
        self._tasks: OrderedDict[str, Task] = OrderedDict()

    def add(self, task: Task) -> None:
        """Store a task, evicting oldest terminal task if capacity reached."""
        if len(self._tasks) >= self.max_tasks and task.task_id not in self._tasks:
            # Try to evict oldest completed/failed/cancelled task first
            evicted = False
            for tid, t in list(self._tasks.items()):
                if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                    del self._tasks[tid]
                    logger.info("Evicted terminal task %s to free capacity in TaskStore", tid)
                    evicted = True
                    break
            if not evicted:
                # Evict oldest task
                oldest_id, _ = self._tasks.popitem(last=False)
                logger.info("TaskStore capacity reached (%d). Evicted oldest task %s", self.max_tasks, oldest_id)

        self._tasks[task.task_id] = task

    def get(self, task_id: str) -> Optional[Task]:
        """Retrieve task by ID."""
        return self._tasks.get(task_id)

    def list_all(self, status: Optional[str] = None, limit: int = 10) -> List[Task]:
        """List tasks optionally filtered by status string."""
        tasks = list(self._tasks.values())
        if status and status.lower() != "all":
            tasks = [t for t in tasks if t.status.value.lower() == status.lower()]
        return tasks[-limit:]

    def clear(self) -> None:
        """Clear all tasks."""
        self._tasks.clear()

    def count(self) -> int:
        """Return number of tasks in store."""
        return len(self._tasks)


# Global singleton instances for tools
_ACTIVE_TASK_STORE: Optional[TaskStore] = None
_ACTIVE_TASK_PLANNER: Optional[BaseTaskPlanner] = None
_ACTIVE_TASK_EXECUTOR: Optional[TaskExecutor] = None


def get_task_store() -> TaskStore:
    """Get or create singleton TaskStore."""
    global _ACTIVE_TASK_STORE
    if _ACTIVE_TASK_STORE is None:
        _ACTIVE_TASK_STORE = TaskStore()
    return _ACTIVE_TASK_STORE


def set_task_store(store: Optional[TaskStore]) -> None:
    """Set or override singleton TaskStore."""
    global _ACTIVE_TASK_STORE
    _ACTIVE_TASK_STORE = store


def get_task_planner() -> Any:
    """Get or create singleton BaseTaskPlanner."""
    global _ACTIVE_TASK_PLANNER
    if _ACTIVE_TASK_PLANNER is None:
        from planner.planner import LLMTaskPlanner
        _ACTIVE_TASK_PLANNER = LLMTaskPlanner()
    return _ACTIVE_TASK_PLANNER


def set_task_planner(planner: Optional[Any]) -> None:
    """Set or override singleton BaseTaskPlanner."""
    global _ACTIVE_TASK_PLANNER
    _ACTIVE_TASK_PLANNER = planner


def get_task_executor() -> Any:
    """Get or create singleton TaskExecutor."""
    global _ACTIVE_TASK_EXECUTOR
    if _ACTIVE_TASK_EXECUTOR is None:
        from planner.executor import TaskExecutor
        from tools.registry import ToolRegistry
        from tools.router import ToolRouter

        registry = ToolRegistry()
        router = ToolRouter(registry)
        _ACTIVE_TASK_EXECUTOR = TaskExecutor(tool_router=router, planner=get_task_planner())
    return _ACTIVE_TASK_EXECUTOR


def set_task_executor(executor: Optional[Any]) -> None:
    """Set or override singleton TaskExecutor."""
    global _ACTIVE_TASK_EXECUTOR
    _ACTIVE_TASK_EXECUTOR = executor



# ==============================================================================
# TOOL 1: CreateTaskTool
# ==============================================================================
class CreateTaskTool(BaseTool):
    """Decompose a high-level user goal into a validated sequential task plan."""

    def __init__(self, planner: Optional[BaseTaskPlanner] = None, store: Optional[TaskStore] = None) -> None:
        self._planner = planner
        self._store = store

    @property
    def planner(self) -> BaseTaskPlanner:
        return self._planner or get_task_planner()

    @property
    def store(self) -> TaskStore:
        return self._store or get_task_store()

    @property
    def name(self) -> str:
        return "create_task"

    @property
    def description(self) -> str:
        return (
            "Decompose a high-level user goal into a validated sequential multi-step task plan. "
            "Returns a structured plan with task_id and steps without executing them."
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
                    name="goal",
                    param_type="string",
                    description="The high-level user goal or objective to decompose into steps.",
                    required=True,
                ),
                ToolParameter(
                    name="context",
                    param_type="object",
                    description="Optional dictionary of initial context variables or constraints.",
                    required=False,
                    default=None,
                ),
            ],
        )

    def execute(self, goal: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cleaned_goal = (goal or "").strip()
        if not cleaned_goal:
            raise PlanValidationError("Task goal cannot be empty")

        task_context = TaskContext(variables=context or {})
        task = self.planner.plan(cleaned_goal, task_context)
        self.store.add(task)

        return {
            "task_id": task.task_id,
            "goal": task.goal,
            "status": task.status.value,
            "steps_count": len(task.steps),
            "steps": [
                {
                    "step_number": s.step_number,
                    "tool_name": s.tool_name,
                    "description": s.description,
                    "risk_level": s.risk_level.value,
                    "requires_confirmation": s.requires_confirmation,
                    "status": s.status.value,
                }
                for s in task.steps
            ],
        }


# ==============================================================================
# TOOL 2: RunTaskTool
# ==============================================================================
class RunTaskTool(BaseTool):
    """Execute the steps of a planned task sequentially."""

    def __init__(self, executor: Optional[TaskExecutor] = None, store: Optional[TaskStore] = None) -> None:
        self._executor = executor
        self._store = store

    @property
    def executor(self) -> TaskExecutor:
        return self._executor or get_task_executor()

    @property
    def store(self) -> TaskStore:
        return self._store or get_task_store()

    @property
    def name(self) -> str:
        return "run_task"

    @property
    def description(self) -> str:
        return (
            "Execute a planned task sequentially through the ToolRouter. "
            "Executes one step after another, pausing if user confirmation is required."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    def get_risk_level(self, arguments: Dict[str, Any]) -> RiskLevel:
        """Dynamically evaluate risk based on next pending step in task."""
        task_id = arguments.get("task_id", "")
        task = self.store.get(task_id)
        if task and task.current_step_index < len(task.steps):
            step = task.steps[task.current_step_index]
            return step.risk_level
        return RiskLevel.SAFE

    def get_confirmation_message(self, arguments: Dict[str, Any]) -> Optional[str]:
        task_id = arguments.get("task_id", "")
        task = self.store.get(task_id)
        if task and task.current_step_index < len(task.steps):
            step = task.steps[task.current_step_index]
            if step.requires_confirmation:
                return (
                    f"Task {task_id} requires confirmation to execute step {step.step_number}: "
                    f"'{step.tool_name}' with args {step.arguments}"
                )
        return None

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="task_id",
                    param_type="string",
                    description="Unique ID of the task to run.",
                    required=True,
                ),
                ToolParameter(
                    name="auto_replan",
                    param_type="boolean",
                    description="Whether to automatically attempt replanning if a non-fatal step fails (default True).",
                    required=False,
                    default=True,
                ),
            ],
        )

    def execute(self, task_id: str, auto_replan: bool = True) -> Dict[str, Any]:
        task = self.store.get(task_id)
        if not task:
            raise PlannerError(f"Task with ID '{task_id}' not found")

        updated_task = self.executor.run_task(task, auto_replan=auto_replan)

        completed_count = sum(1 for s in updated_task.steps if s.status == StepStatus.COMPLETED)
        return {
            "task_id": updated_task.task_id,
            "goal": updated_task.goal,
            "status": updated_task.status.value,
            "current_step_index": updated_task.current_step_index,
            "steps_count": len(updated_task.steps),
            "completed_steps": completed_count,
            "replans_count": updated_task.replans_count,
            "results": updated_task.context.results,
        }


# ==============================================================================
# TOOL 3: PauseTaskTool
# ==============================================================================
class PauseTaskTool(BaseTool):
    """Pause an in-progress running task."""

    def __init__(self, executor: Optional[TaskExecutor] = None, store: Optional[TaskStore] = None) -> None:
        self._executor = executor
        self._store = store

    @property
    def executor(self) -> TaskExecutor:
        return self._executor or get_task_executor()

    @property
    def store(self) -> TaskStore:
        return self._store or get_task_store()

    @property
    def name(self) -> str:
        return "pause_task"

    @property
    def description(self) -> str:
        return "Pause an in-progress running task cleanly between steps."

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
                    name="task_id",
                    param_type="string",
                    description="Unique ID of the task to pause.",
                    required=True,
                ),
                ToolParameter(
                    name="reason",
                    param_type="string",
                    description="Optional explanation for pausing the task.",
                    required=False,
                    default="Paused by user request",
                ),
            ],
        )

    def execute(self, task_id: str, reason: str = "Paused by user request") -> Dict[str, Any]:
        task = self.store.get(task_id)
        if not task:
            raise PlannerError(f"Task with ID '{task_id}' not found")

        updated_task = self.executor.pause_task(task, reason=reason)
        return {
            "task_id": updated_task.task_id,
            "status": updated_task.status.value,
            "current_step_index": updated_task.current_step_index,
            "reason": reason,
        }


# ==============================================================================
# TOOL 4: ResumeTaskTool
# ==============================================================================
class ResumeTaskTool(BaseTool):
    """Resume a paused or confirmation-waiting task."""

    def __init__(self, executor: Optional[TaskExecutor] = None, store: Optional[TaskStore] = None) -> None:
        self._executor = executor
        self._store = store

    @property
    def executor(self) -> TaskExecutor:
        return self._executor or get_task_executor()

    @property
    def store(self) -> TaskStore:
        return self._store or get_task_store()

    @property
    def name(self) -> str:
        return "resume_task"

    @property
    def description(self) -> str:
        return "Resume execution of a paused or confirmation-waiting task."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    def get_risk_level(self, arguments: Dict[str, Any]) -> RiskLevel:
        task_id = arguments.get("task_id", "")
        task = self.store.get(task_id)
        if task and task.current_step_index < len(task.steps):
            step = task.steps[task.current_step_index]
            return step.risk_level
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="task_id",
                    param_type="string",
                    description="Unique ID of the task to resume.",
                    required=True,
                ),
            ],
        )

    def execute(self, task_id: str) -> Dict[str, Any]:
        task = self.store.get(task_id)
        if not task:
            raise PlannerError(f"Task with ID '{task_id}' not found")

        updated_task = self.executor.resume_task(task)
        completed_count = sum(1 for s in updated_task.steps if s.status == StepStatus.COMPLETED)
        return {
            "task_id": updated_task.task_id,
            "status": updated_task.status.value,
            "current_step_index": updated_task.current_step_index,
            "steps_count": len(updated_task.steps),
            "completed_steps": completed_count,
            "results": updated_task.context.results,
        }


# ==============================================================================
# TOOL 5: CancelTaskTool
# ==============================================================================
class CancelTaskTool(BaseTool):
    """Cancel an active, pending, or paused task."""

    def __init__(self, executor: Optional[TaskExecutor] = None, store: Optional[TaskStore] = None) -> None:
        self._executor = executor
        self._store = store

    @property
    def executor(self) -> TaskExecutor:
        return self._executor or get_task_executor()

    @property
    def store(self) -> TaskStore:
        return self._store or get_task_store()

    @property
    def name(self) -> str:
        return "cancel_task"

    @property
    def description(self) -> str:
        return "Cancel an active, pending, or paused task cleanly."

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
                    name="task_id",
                    param_type="string",
                    description="Unique ID of the task to cancel.",
                    required=True,
                ),
                ToolParameter(
                    name="reason",
                    param_type="string",
                    description="Optional cancellation reason.",
                    required=False,
                    default="Cancelled by user",
                ),
            ],
        )

    def execute(self, task_id: str, reason: str = "Cancelled by user") -> Dict[str, Any]:
        task = self.store.get(task_id)
        if not task:
            raise PlannerError(f"Task with ID '{task_id}' not found")

        updated_task = self.executor.cancel_task(task, reason=reason)
        return {
            "task_id": updated_task.task_id,
            "status": updated_task.status.value,
            "reason": reason,
        }


# ==============================================================================
# TOOL 6: GetTaskStatusTool
# ==============================================================================
class GetTaskStatusTool(BaseTool):
    """Inspect detailed status, steps, and execution logs of a task."""

    def __init__(self, store: Optional[TaskStore] = None) -> None:
        self._store = store

    @property
    def store(self) -> TaskStore:
        return self._store or get_task_store()

    @property
    def name(self) -> str:
        return "get_task_status"

    @property
    def description(self) -> str:
        return "Inspect current status, progress, step details, errors, and execution logs of a task."

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
                    name="task_id",
                    param_type="string",
                    description="Unique ID of the task to inspect.",
                    required=True,
                ),
            ],
        )

    def execute(self, task_id: str) -> Dict[str, Any]:
        task = self.store.get(task_id)
        if not task:
            raise PlannerError(f"Task with ID '{task_id}' not found")

        return {
            "task_id": task.task_id,
            "goal": task.goal,
            "status": task.status.value,
            "current_step_index": task.current_step_index,
            "replans_count": task.replans_count,
            "created_at": task.created_at if isinstance(task.created_at, str) else task.created_at.isoformat(),
            "updated_at": task.updated_at if isinstance(task.updated_at, str) else task.updated_at.isoformat(),
            "steps": [
                {
                    "step_number": s.step_number,
                    "tool_name": s.tool_name,
                    "description": s.description,
                    "status": s.status.value,
                    "risk_level": s.risk_level.value,
                    "requires_confirmation": s.requires_confirmation,
                    "retries_count": s.retries_count,
                    "error": s.error,
                    "result": s.result,
                }
                for s in task.steps
            ],
            "execution_logs": task.context.execution_logs[-20:],
        }


# ==============================================================================
# TOOL 7: ListTasksTool
# ==============================================================================
class ListTasksTool(BaseTool):
    """List tasks held in memory with optional status filtering."""

    def __init__(self, store: Optional[TaskStore] = None) -> None:
        self._store = store

    @property
    def store(self) -> TaskStore:
        return self._store or get_task_store()

    @property
    def name(self) -> str:
        return "list_tasks"

    @property
    def description(self) -> str:
        return "List all in-memory tasks, optionally filtered by status (e.g. pending, running, completed, paused, failed)."

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
                    name="status",
                    param_type="string",
                    description="Optional status filter ('all', 'pending', 'running', 'completed', 'paused', 'failed', 'cancelled').",
                    required=False,
                    default=None,
                ),
                ToolParameter(
                    name="limit",
                    param_type="integer",
                    description="Maximum number of tasks to return (default 10).",
                    required=False,
                    default=10,
                ),
            ],
        )

    def execute(self, status: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        tasks = self.store.list_all(status=status, limit=limit)
        return {
            "count": len(tasks),
            "filter_status": status or "all",
            "tasks": [
                {
                    "task_id": t.task_id,
                    "goal": t.goal,
                    "status": t.status.value,
                    "steps_count": len(t.steps),
                    "current_step_index": t.current_step_index,
                    "created_at": t.created_at if isinstance(t.created_at, str) else t.created_at.isoformat(),
                }

                for t in tasks
            ],
        }
