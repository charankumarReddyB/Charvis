"""
Reactive GUI state management for the CHARVIS Desktop GUI (Phase 15).
Maintains local presentation state, listener subscriptions, and thread-safe updates.
"""

from copy import copy
import threading
from typing import Any, Callable, Dict, List, Optional

from gui.models import (
    AppView,
    ChatMessage,
    ConfirmationRequest,
    SystemState,
    TaskDisplayItem,
)
from logger import get_logger

logger = get_logger("CHARVIS.GUI.State")


class GUIState:
    """
    Central reactive state container for the desktop interface.
    Thread-safe; notifies subscribers whenever relevant UI state mutates.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._listeners: List[Callable[["GUIState"], None]] = []

        # Presentation state
        self.current_view: AppView = AppView.CHAT
        self.system_status: SystemState = SystemState.IDLE
        self.status_message: str = "Ready"
        self.chat_messages: List[ChatMessage] = []
        self.active_task: Optional[TaskDisplayItem] = None
        self.tasks_list: List[TaskDisplayItem] = []
        self.task_logs: List[str] = []
        self.active_confirmation: Optional[ConfirmationRequest] = None
        self.is_listening: bool = False
        self.is_processing: bool = False
        self.is_speaking: bool = False
        self.error_message: Optional[str] = None

    # Property aliases for flexibility
    @property
    def system_state(self) -> SystemState:
        return self.system_status

    @system_state.setter
    def system_state(self, val: SystemState) -> None:
        self.system_status = val

    @property
    def messages(self) -> List[ChatMessage]:
        return self.chat_messages

    @property
    def tasks(self) -> List[TaskDisplayItem]:
        return self.tasks_list

    @property
    def pending_confirmation(self) -> Optional[ConfirmationRequest]:
        return self.active_confirmation

    @property
    def is_busy(self) -> bool:
        return (
            self.is_processing
            or self.is_listening
            or self.system_status in (
                SystemState.THINKING,
                SystemState.EXECUTING,
                SystemState.WAITING_CONFIRMATION,
            )
        )

    # Subscription methods
    def subscribe(self, callback: Callable[["GUIState"], None]) -> Callable[[], None]:
        """Subscribe a listener callback; returns an unsubscribe function."""
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

        def unsubscribe() -> None:
            self.unregister_listener(callback)

        return unsubscribe

    def register_listener(self, callback: Callable[["GUIState"], None]) -> None:
        """Register a callback to be invoked whenever state changes."""
        self.subscribe(callback)

    def unregister_listener(self, callback: Callable[["GUIState"], None]) -> None:
        """Unregister a listener callback."""
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def notify_listeners(self) -> None:
        """Notify all registered listeners of state mutation."""
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(self)
            except Exception as e:
                logger.error("Error in GUIState listener callback: %s", e)

    # View mutation
    def set_current_view(self, view: AppView) -> None:
        self.set_view(view)

    def set_view(self, view: AppView) -> None:
        """Change the active navigation view."""
        with self._lock:
            if self.current_view == view:
                return
            self.current_view = view
        self.notify_listeners()

    # System state mutation
    def set_system_state(self, status: SystemState, message: Optional[str] = None) -> None:
        self.set_system_status(status, message)

    def set_system_status(self, status: SystemState, message: Optional[str] = None) -> None:
        """Update system operational status and optional text description."""
        with self._lock:
            self.system_status = status
            if message is not None:
                self.status_message = message
        self.notify_listeners()

    # Chat mutation
    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChatMessage:
        return self.add_chat_message(sender=role, content=content, metadata=metadata)

    def add_chat_message(
        self,
        sender: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChatMessage:
        """Append a message to the conversation stream."""
        msg = ChatMessage(role=sender.lower(), sender=sender.upper(), content=content, metadata=metadata or {})
        with self._lock:
            self.chat_messages.append(msg)
        self.notify_listeners()
        return msg

    def clear_messages(self) -> None:
        self.clear_chat()

    def clear_chat(self) -> None:
        """Clear all chat messages from presentation state."""
        with self._lock:
            self.chat_messages.clear()
        self.notify_listeners()

    # Task & Log mutation
    def set_tasks(self, tasks: List[TaskDisplayItem]) -> None:
        """Update the list of tasks."""
        with self._lock:
            self.tasks_list = list(tasks)
        self.notify_listeners()

    def set_active_task(self, task: Optional[TaskDisplayItem]) -> None:
        """Set the currently selected/active task."""
        with self._lock:
            self.active_task = task
        self.notify_listeners()

    def append_task_log(self, log_line: str) -> None:
        """Add an entry to live task execution logs."""
        with self._lock:
            self.task_logs.append(log_line)
        self.notify_listeners()

    def clear_task_logs(self) -> None:
        """Clear task execution logs."""
        with self._lock:
            self.task_logs.clear()
        self.notify_listeners()

    # Confirmation request mutation
    def request_confirmation(self, req: ConfirmationRequest) -> None:
        self.set_confirmation_request(req)

    def clear_confirmation(self) -> None:
        self.set_confirmation_request(None)

    def set_confirmation_request(self, req: Optional[ConfirmationRequest]) -> None:
        """Set or clear the active confirmation prompt."""
        with self._lock:
            self.active_confirmation = req
            if req is not None:
                self.system_status = SystemState.WAITING_CONFIRMATION
                self.status_message = f"Confirmation required for '{req.tool_name}'"
            elif self.system_status == SystemState.WAITING_CONFIRMATION:
                self.system_status = SystemState.IDLE
                self.status_message = "Ready"
        self.notify_listeners()

    # Activity flags
    def set_listening(self, listening: bool) -> None:
        """Update microphone listening flag."""
        with self._lock:
            self.is_listening = listening
            if listening:
                self.system_status = SystemState.LISTENING
                self.status_message = "Listening for speech..."
            elif self.system_status == SystemState.LISTENING:
                self.system_status = SystemState.IDLE
                self.status_message = "Ready"
        self.notify_listeners()

    def set_processing(self, processing: bool) -> None:
        """Update AI thinking/processing flag."""
        with self._lock:
            self.is_processing = processing
            if processing:
                self.system_status = SystemState.THINKING
                self.status_message = "CHARVIS is thinking..."
            elif self.system_status == SystemState.THINKING:
                self.system_status = SystemState.IDLE
                self.status_message = "Ready"
        self.notify_listeners()
