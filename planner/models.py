"""
Data models, enums, and state machines for the CHARVIS Task Planner (Phase 14).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import uuid

from core.safety import RiskLevel


class TaskStatus(str, Enum):
    """Lifecycle states of a multi-step Task."""
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    """Execution states of an individual TaskStep."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class EvaluationResult(str, Enum):
    """Outcome of step evaluation by ResultEvaluator."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    FAILED = "FAILED"
    USER_DENIED = "USER_DENIED"
    RETRY_ELIGIBLE = "RETRY_ELIGIBLE"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    NEEDS_REPLAN = "NEEDS_REPLAN"
    TASK_COMPLETE = "TASK_COMPLETE"


# Legal State Transitions for Task
VALID_TASK_TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
    TaskStatus.CREATED: {
        TaskStatus.PLANNING,
        TaskStatus.READY,
        TaskStatus.PENDING,
        TaskStatus.RUNNING,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.PLANNING: {
        TaskStatus.READY,
        TaskStatus.PENDING,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.READY: {
        TaskStatus.RUNNING,
        TaskStatus.PENDING,
        TaskStatus.PAUSED,
        TaskStatus.CANCELLED,
        TaskStatus.WAITING_CONFIRMATION,
    },
    TaskStatus.PENDING: {
        TaskStatus.RUNNING,
        TaskStatus.READY,
        TaskStatus.PAUSED,
        TaskStatus.CANCELLED,
        TaskStatus.WAITING_CONFIRMATION,
    },
    TaskStatus.RUNNING: {
        TaskStatus.WAITING_CONFIRMATION,
        TaskStatus.PAUSED,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
        TaskStatus.PENDING,
        TaskStatus.READY,
    },
    TaskStatus.WAITING_CONFIRMATION: {
        TaskStatus.RUNNING,
        TaskStatus.PAUSED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.PAUSED: {
        TaskStatus.RUNNING,
        TaskStatus.PENDING,
        TaskStatus.READY,
        TaskStatus.CANCELLED,
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}

# Legal State Transitions for Step
VALID_STEP_TRANSITIONS: Dict[StepStatus, Set[StepStatus]] = {
    StepStatus.PENDING: {
        StepStatus.RUNNING,
        StepStatus.SKIPPED,
        StepStatus.CANCELLED,
        StepStatus.WAITING_CONFIRMATION,
    },
    StepStatus.RUNNING: {
        StepStatus.WAITING_CONFIRMATION,
        StepStatus.COMPLETED,
        StepStatus.FAILED,
        StepStatus.CANCELLED,
    },
    StepStatus.WAITING_CONFIRMATION: {
        StepStatus.RUNNING,
        StepStatus.FAILED,
        StepStatus.CANCELLED,
    },
    StepStatus.COMPLETED: set(),
    StepStatus.FAILED: set(),
    StepStatus.SKIPPED: set(),
    StepStatus.CANCELLED: set(),
}


# Custom Exception Hierarchy
class PlannerError(Exception):
    """Base exception for all task planning and execution errors."""
    pass


class PlanValidationError(PlannerError):
    """Raised when a task plan fails validation against tool registry or schemas."""
    pass


class TaskExecutionError(PlannerError):
    """Raised when task or step execution encounters a critical error."""
    pass


class PlanExecutionError(TaskExecutionError):
    """Alias for TaskExecutionError."""
    pass


class PlanSecurityError(PlannerError):
    """Raised when a plan violates safety policies or contains code injection."""
    pass


class PlannerStateError(PlannerError):
    """Raised on illegal task or step state transitions."""
    pass


class TaskCancelledError(PlannerError):
    """Raised when an operation is attempted on an aborted/cancelled task."""
    pass


class TaskLimitExceededError(PlannerError):
    """Raised when step count, replan count, or retry limits are breached."""
    pass


class MaxStepsExceededError(TaskLimitExceededError):
    """Raised when task step count exceeds limit."""
    pass


class MaxReplansExceededError(TaskLimitExceededError):
    """Raised when task replans count exceeds limit."""
    pass


@dataclass
class TaskStep:
    """Individual sequential action step within a Task."""
    order: int
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.SAFE
    requires_confirmation: bool = False
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0

    @property
    def step_number(self) -> int:
        return self.order

    @step_number.setter
    def step_number(self, val: int) -> None:
        self.order = val

    @property
    def step_id(self) -> str:
        return self.id

    @property
    def retries_count(self) -> int:
        return self.retry_count

    @retries_count.setter
    def retries_count(self, val: int) -> None:
        self.retry_count = val

    def transition_to(self, new_status: StepStatus, reason: Optional[str] = None) -> None:
        """Validate and transition to a new StepStatus."""
        if new_status == self.status:
            return
        allowed = VALID_STEP_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise PlannerStateError(
                f"Illegal step transition from {self.status.value} to {new_status.value} "
                f"for step {self.order} ({self.tool_name}). Reason: {reason}"
            )
        self.status = new_status
        now_iso = datetime.now(timezone.utc).isoformat()
        if new_status == StepStatus.RUNNING and not self.started_at:
            self.started_at = now_iso
        elif new_status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.CANCELLED, StepStatus.SKIPPED):
            self.completed_at = now_iso

    def to_dict(self) -> Dict[str, Any]:
        """Serialize step to dictionary."""
        return {
            "id": self.id,
            "order": self.order,
            "tool_name": self.tool_name,
            "description": self.description,
            "arguments": dict(self.arguments),
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "risk_level": self.risk_level.value,
            "requires_confirmation": self.requires_confirmation,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskStep":
        """Reconstruct step from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            order=int(data.get("order", data.get("step_number", 1))),
            tool_name=data["tool_name"],
            description=data.get("description", ""),
            arguments=dict(data.get("arguments", {})),
            status=StepStatus(data.get("status", StepStatus.PENDING.value)),
            result=data.get("result"),
            error=data.get("error"),
            risk_level=RiskLevel(data.get("risk_level", RiskLevel.SAFE.value)),
            requires_confirmation=bool(data.get("requires_confirmation", False)),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            retry_count=int(data.get("retry_count", data.get("retries_count", 0))),
        )


@dataclass
class TaskContext:
    """Bounded contextual snapshot for task generation, execution, and replanning."""
    goal: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    execution_logs: List[str] = field(default_factory=list)
    completed_steps: List[Dict[str, Any]] = field(default_factory=list)
    current_step: Optional[Dict[str, Any]] = None
    relevant_observations: List[str] = field(default_factory=list)
    relevant_memory: str = ""

    def add_execution_log(self, message: str) -> None:
        """Append an execution message to logs."""
        self.execution_logs.append(message)


@dataclass
class Task:
    """Structured multi-step plan representing a user goal."""
    goal: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.CREATED
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    steps: List[TaskStep] = field(default_factory=list)
    current_step: int = 0
    max_steps: int = 15
    replan_count: int = 0
    requires_confirmation: bool = False
    failure_reason: Optional[str] = None
    context: TaskContext = field(default_factory=TaskContext)

    @property
    def task_id(self) -> str:
        return self.id

    @property
    def current_step_index(self) -> int:
        return self.current_step

    @current_step_index.setter
    def current_step_index(self, val: int) -> None:
        self.current_step = val

    @property
    def replans_count(self) -> int:
        return self.replan_count

    @replans_count.setter
    def replans_count(self, val: int) -> None:
        self.replan_count = val

    def transition_to(self, new_status: TaskStatus, reason: Optional[str] = None) -> None:
        """Validate and transition to a new TaskStatus."""
        if new_status == self.status:
            return
        allowed = VALID_TASK_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise PlannerStateError(
                f"Illegal task transition from {self.status.value} to {new_status.value} "
                f"for task '{self.id}'. Reason: {reason}"
            )
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if reason and not self.failure_reason and new_status == TaskStatus.FAILED:
            self.failure_reason = reason

    @property
    def is_finished(self) -> bool:
        """Check if task has reached a terminal state."""
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize task to dictionary."""
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_step": self.current_step,
            "max_steps": self.max_steps,
            "replan_count": self.replan_count,
            "requires_confirmation": self.requires_confirmation,
            "failure_reason": self.failure_reason,
            "steps": [s.to_dict() for s in self.steps],
            "context": {
                "variables": self.context.variables,
                "results": self.context.results,
                "execution_logs": self.context.execution_logs[-20:],
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Reconstruct task from dictionary."""
        steps = [TaskStep.from_dict(s) for s in data.get("steps", [])]
        ctx_data = data.get("context", {})
        ctx = TaskContext(
            goal=data.get("goal", ""),
            variables=ctx_data.get("variables", {}),
            results=ctx_data.get("results", {}),
            execution_logs=ctx_data.get("execution_logs", []),
        )
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            goal=data["goal"],
            status=TaskStatus(data.get("status", TaskStatus.CREATED.value)),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            steps=steps,
            current_step=int(data.get("current_step", 0)),
            max_steps=int(data.get("max_steps", 15)),
            replan_count=int(data.get("replan_count", 0)),
            requires_confirmation=bool(data.get("requires_confirmation", False)),
            failure_reason=data.get("failure_reason"),
            context=ctx,
        )
