"""CHARVIS Wake-Word State Machine Definitions.

Defines explicit lifecycle states and transition exception.
"""

from __future__ import annotations

from enum import Enum


class WakeWordState(str, Enum):
    """Explicit lifecycle states for the wake-word standby engine."""

    STANDBY = "STANDBY"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal state transition is attempted."""

    pass
