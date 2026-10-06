"""
Explicit runtime state machine for CHARVIS Background Runtime (Phase 16).
Enforces valid state transitions and raises controlled exceptions on invalid ones.
"""

from enum import Enum
import threading
from typing import Callable, List, Optional, Set

from logger import get_logger

logger = get_logger("CHARVIS.Runtime.State")


class RuntimeState(str, Enum):
    """Explicit lifecycle states of the CHARVIS background runtime."""
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"
    DEGRADED = "DEGRADED"
    PAUSED = "PAUSED"


class InvalidStateTransitionError(RuntimeError):
    """Raised when an illegal or unsupported state transition is attempted."""
    pass


# Strict transition graph
VALID_TRANSITIONS: dict[RuntimeState, Set[RuntimeState]] = {
    RuntimeState.STOPPED: {RuntimeState.STARTING, RuntimeState.ERROR},
    RuntimeState.STARTING: {RuntimeState.RUNNING, RuntimeState.ERROR, RuntimeState.STOPPING},
    RuntimeState.RUNNING: {RuntimeState.STOPPING, RuntimeState.PAUSED, RuntimeState.DEGRADED, RuntimeState.ERROR},
    RuntimeState.PAUSED: {RuntimeState.RUNNING, RuntimeState.STOPPING, RuntimeState.ERROR},
    RuntimeState.DEGRADED: {RuntimeState.RUNNING, RuntimeState.STOPPING, RuntimeState.ERROR},
    RuntimeState.STOPPING: {RuntimeState.STOPPED, RuntimeState.ERROR},
    RuntimeState.ERROR: {RuntimeState.STOPPING, RuntimeState.STOPPED},
}


class RuntimeStateMachine:
    """
    Thread-safe state manager for the CHARVIS background runtime.
    Guarantees state changes are atomic, valid, and observed by registered listeners.
    """

    def __init__(self, initial_state: RuntimeState = RuntimeState.STOPPED) -> None:
        self._lock = threading.Lock()
        self._state: RuntimeState = initial_state
        self._last_error: Optional[str] = None
        self._listeners: List[Callable[[RuntimeState, RuntimeState], None]] = []

    @property
    def state(self) -> RuntimeState:
        with self._lock:
            return self._state

    @property
    def last_error(self) -> Optional[str]:
        with self._lock:
            return self._last_error

    def add_listener(self, listener: Callable[[RuntimeState, RuntimeState], None]) -> None:
        """Register a callback for state changes: fn(old_state, new_state)."""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[RuntimeState, RuntimeState], None]) -> None:
        """Unregister a state change listener."""
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def transition_to(
        self,
        target_state: RuntimeState,
        reason: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Transition the state machine to target_state.
        Raises InvalidStateTransitionError if transition is not permitted.
        """
        listeners_to_notify: List[Callable[[RuntimeState, RuntimeState], None]] = []
        old_state: RuntimeState = RuntimeState.STOPPED

        with self._lock:
            old_state = self._state

            # Idempotent shutdown or same-state transition check
            if old_state == target_state:
                if target_state == RuntimeState.STOPPED:
                    # Idempotent stop is permitted
                    return
                # Redundant transition to other states is ignored with a warning
                logger.debug("Redundant state transition to %s ignored.", target_state.value)
                return

            valid_targets = VALID_TRANSITIONS.get(old_state, set())
            if target_state not in valid_targets:
                msg = f"Invalid runtime state transition from {old_state.value} to {target_state.value}."
                if reason:
                    msg += f" Reason: {reason}"
                logger.error(msg)
                raise InvalidStateTransitionError(msg)

            self._state = target_state
            if error_message:
                self._last_error = error_message
            elif target_state in {RuntimeState.STOPPED, RuntimeState.RUNNING}:
                self._last_error = None

            logger.info(
                "Runtime state transitioned: %s -> %s%s",
                old_state.value,
                target_state.value,
                f" ({reason})" if reason else "",
            )
            listeners_to_notify = list(self._listeners)

        # Notify outside lock to prevent deadlocks
        for listener in listeners_to_notify:
            try:
                listener(old_state, target_state)
            except Exception as e:
                logger.warning("Listener error during state transition: %s", e)

    def set_error(self, error_message: str) -> None:
        """Shortcut to transition directly into ERROR state."""
        self.transition_to(RuntimeState.ERROR, reason=error_message, error_message=error_message)

    def is_running(self) -> bool:
        with self._lock:
            return self._state == RuntimeState.RUNNING

    def is_stopped(self) -> bool:
        with self._lock:
            return self._state == RuntimeState.STOPPED
