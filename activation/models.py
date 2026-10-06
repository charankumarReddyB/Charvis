"""
Data models and state definitions for the CHARVIS Activation System (Phase 18).
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, Optional
import uuid


class ActivationState(str, Enum):
    """Lifecycle states of user activation."""
    INACTIVE = "INACTIVE"
    ACTIVATING = "ACTIVATING"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class ActivationSource(str, Enum):
    """Entry point triggering the activation request."""
    HOTKEY = "HOTKEY"
    TRAY = "TRAY"
    GUI = "GUI"
    WAKE_WORD = "WAKE_WORD"
    CLI = "CLI"
    VOICE_BUTTON = "VOICE_BUTTON"
    KEYBOARD_SHORTCUT = "KEYBOARD_SHORTCUT"
    TRAY_MENU = "TRAY_MENU"


# Explicit valid state transitions
VALID_ACTIVATION_TRANSITIONS = {
    ActivationState.INACTIVE: {ActivationState.ACTIVATING, ActivationState.LISTENING, ActivationState.ERROR},
    ActivationState.ACTIVATING: {ActivationState.LISTENING, ActivationState.CANCELLED, ActivationState.ERROR},
    ActivationState.LISTENING: {ActivationState.PROCESSING, ActivationState.CANCELLED, ActivationState.ERROR, ActivationState.COMPLETED},
    ActivationState.PROCESSING: {ActivationState.SPEAKING, ActivationState.COMPLETED, ActivationState.CANCELLED, ActivationState.ERROR},
    ActivationState.SPEAKING: {ActivationState.COMPLETED, ActivationState.CANCELLED, ActivationState.ERROR, ActivationState.INACTIVE},
    ActivationState.COMPLETED: {ActivationState.INACTIVE},
    ActivationState.CANCELLED: {ActivationState.INACTIVE},
    ActivationState.ERROR: {ActivationState.INACTIVE},
}


class ActivationStateError(Exception):
    """Raised on illegal activation state transition."""
    pass


InvalidActivationTransitionError = ActivationStateError


@dataclass
class ActivationSession:
    """Represents an active user interaction session."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: ActivationSource = ActivationSource.HOTKEY
    state: ActivationState = ActivationState.INACTIVE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error_message: Optional[str] = None
    command_text: Optional[str] = None
    response_text: Optional[str] = None

    @property
    def is_terminal(self) -> bool:
        return self.state in (ActivationState.COMPLETED, ActivationState.CANCELLED, ActivationState.ERROR)

    def transition_to(self, new_state: ActivationState, error: Optional[str] = None) -> None:
        """Validate and transition to a new activation state."""
        allowed = VALID_ACTIVATION_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise ActivationStateError(
                f"Invalid activation transition from '{self.state.value}' to '{new_state.value}'"
            )
        self.state = new_state
        self.updated_at = time.time()
        if error:
            self.error_message = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to serializable dictionary."""
        return {
            "session_id": self.session_id,
            "source": self.source.value,
            "state": self.state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error_message": self.error_message,
            "command_text": self.command_text,
            "response_text": self.response_text,
        }
