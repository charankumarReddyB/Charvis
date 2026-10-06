"""
Data models, enums, and representation structures for the CHARVIS Desktop GUI (Phase 15).
Keeps UI state strictly decoupled from core execution backends.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import threading
import time
from typing import Any, Dict, List, Optional, Union
import uuid

from core.safety import RiskLevel


class AppView(str, Enum):
    """Active navigation views in the GUI."""
    ASSISTANT = "assistant"
    CHAT = "chat"
    TASKS = "tasks"
    MEMORY = "memory"
    SETTINGS = "settings"


class SystemState(str, Enum):
    """Reactive operating status of the CHARVIS system."""
    IDLE = "idle"
    READY = "ready"
    ONLINE = "online"
    OFFLINE = "offline"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    STARTING = "starting"
    STOPPING = "stopping"
    LISTENING = "listening"
    THINKING = "thinking"
    EXECUTING = "executing"
    SPEAKING = "speaking"
    WAITING_CONFIRMATION = "waiting_confirmation"
    PAUSED = "paused"
    ERROR = "error"

    @property
    def symbol(self) -> str:
        return STATE_DISPLAY_MAP.get(self, {}).get("symbol", "●")

    @property
    def color(self) -> str:
        return STATE_DISPLAY_MAP.get(self, {}).get("color", "#949ba4")


# Visual labels and symbols corresponding to each status
STATE_DISPLAY_MAP: Dict[SystemState, Dict[str, str]] = {
    SystemState.ONLINE: {"symbol": "●", "text": "CHARVIS ONLINE", "color": "#23a55a"},
    SystemState.OFFLINE: {"symbol": "○", "text": "CHARVIS OFFLINE", "color": "#6d7078"},
    SystemState.DISCONNECTED: {"symbol": "○", "text": "DISCONNECTED", "color": "#f23f43"},
    SystemState.RECONNECTING: {"symbol": "◐", "text": "RECONNECTING...", "color": "#f0b232"},
    SystemState.STARTING: {"symbol": "◐", "text": "STARTING", "color": "#f0b232"},
    SystemState.STOPPING: {"symbol": "◐", "text": "STOPPING", "color": "#f0b232"},
    SystemState.IDLE: {"symbol": "●", "text": "IDLE", "color": "#23a55a"},
    SystemState.READY: {"symbol": "●", "text": "READY", "color": "#23a55a"},
    SystemState.LISTENING: {"symbol": "🎤", "text": "LISTENING...", "color": "#f0b232"},
    SystemState.THINKING: {"symbol": "🧠", "text": "THINKING...", "color": "#5865f2"},
    SystemState.EXECUTING: {"symbol": "⚙", "text": "EXECUTING...", "color": "#5865f2"},
    SystemState.SPEAKING: {"symbol": "🔊", "text": "SPEAKING...", "color": "#5865f2"},
    SystemState.WAITING_CONFIRMATION: {"symbol": "⚠️", "text": "CONFIRMATION REQUIRED", "color": "#f0b232"},
    SystemState.PAUSED: {"symbol": "⏸", "text": "PAUSED", "color": "#949ba4"},
    SystemState.ERROR: {"symbol": "✕", "text": "ERROR", "color": "#f23f43"},
}


@dataclass
class ChatMessage:
    """Individual chat message representation in the conversation stream."""
    role: str = "assistant"  # "user", "assistant", "tool", "system", "error"
    content: str = ""
    sender: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.sender and not self.role:
            self.role = self.sender.lower()
        elif not self.sender:
            self.sender = self.role.upper()

    @property
    def is_user(self) -> bool:
        return self.role.lower() in ("user", "human")

    @property
    def is_charvis(self) -> bool:
        return self.role.lower() in ("charvis", "assistant")

    @property
    def is_tool(self) -> bool:
        return self.role.lower() == "tool"

    @property
    def is_error(self) -> bool:
        return self.role.lower() == "error"


@dataclass
class TaskDisplayItem:
    """Summary of a multi-step task for rendering in the Tasks panel."""
    task_id: str
    goal: str
    status: str
    current_step: int = 0
    completed_steps: int = 0
    total_steps: int = 0
    progress_percent: float = 0.0
    created_at: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.completed_steps == 0 and self.current_step > 0:
            self.completed_steps = self.current_step
        elif self.current_step == 0 and self.completed_steps > 0:
            self.current_step = self.completed_steps
        if self.total_steps > 0 and self.progress_percent == 0.0:
            self.progress_percent = (self.completed_steps / self.total_steps) * 100.0

    @classmethod
    def from_task_dict(cls, data: Dict[str, Any]) -> "TaskDisplayItem":
        """Build display item from backend task dictionary."""
        steps = data.get("steps", [])
        total = len(steps) if steps else int(data.get("steps_count", 0))
        cur = int(data.get("current_step_index", data.get("current_step", 0)))
        pct = (cur / total * 100.0) if total > 0 else 0.0
        return cls(
            task_id=data.get("task_id", data.get("id", "")),
            goal=data.get("goal", ""),
            status=str(data.get("status", "READY")).lower(),
            current_step=cur,
            completed_steps=cur,
            total_steps=total,
            progress_percent=min(100.0, max(0.0, pct)),
            created_at=data.get("created_at", ""),
            steps=steps,
            logs=list(data.get("execution_logs", [])),
        )


@dataclass
class ConfirmationRequest:
    """Synchronized confirmation request sent to the GUI from background tool execution (Phase 17 hardened)."""
    tool_name: str
    arguments: Dict[str, Any]
    risk_level: Union[RiskLevel, str] = "high"
    custom_message: Optional[str] = None
    message: Optional[str] = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    confirmation_id: Optional[str] = None
    state: str = "PENDING"
    created_at: float = field(default_factory=time.time)
    timeout_seconds: float = 120.0
    event: threading.Event = field(default_factory=threading.Event)
    result: bool = False

    def __post_init__(self):
        self._lock = threading.Lock()
        if not self.confirmation_id:
            self.confirmation_id = self.request_id
        if not self.message and self.custom_message:
            self.message = self.custom_message
        elif not self.custom_message and self.message:
            self.custom_message = self.message

        if hasattr(self.risk_level, "value"):
            self.risk_level_str = self.risk_level.value
        else:
            self.risk_level_str = str(self.risk_level)

    @property
    def approved(self) -> bool:
        return self.result

    @property
    def is_pending(self) -> bool:
        return self.state == "PENDING" and not self.is_expired()

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        now = current_time or time.time()
        return (now - self.created_at) >= self.timeout_seconds

    def approve(self) -> bool:
        """Approve action and unblock background thread if currently PENDING and not expired."""
        with self._lock:
            if self.is_expired():
                self.expire()
                return False
            if self.state != "PENDING":
                return False
            self.state = "APPROVED"
            self.result = True
            self.event.set()
            return True

    def deny(self) -> bool:
        """Deny action and unblock background thread if currently PENDING."""
        with self._lock:
            if self.state != "PENDING":
                return False
            self.state = "DENIED"
            self.result = False
            self.event.set()
            return True

    def expire(self) -> bool:
        """Mark as expired and unblock background thread."""
        with self._lock:
            if self.state != "PENDING":
                return False
            self.state = "EXPIRED"
            self.result = False
            self.event.set()
            return True

    def cancel(self) -> bool:
        """Cancel confirmation and unblock background thread."""
        with self._lock:
            if self.state != "PENDING":
                return False
            self.state = "CANCELLED"
            self.result = False
            self.event.set()
            return True
