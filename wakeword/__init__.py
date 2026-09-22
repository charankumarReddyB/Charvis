"""CHARVIS Wake-Word Subsystem.

Provides controlled, local wake-phrase activation over short audio frames
with explicit state management and strict privacy guarantees.
"""

from wakeword.detector import (
    BaseWakeWordDetector,
    LocalKeywordDetector,
    MockWakeWordDetector,
    normalize_wake_phrase,
)
from wakeword.states import (
    InvalidStateTransitionError,
    WakeWordState,
)
from wakeword.engine import WakeWordEngine

__all__ = [
    "BaseWakeWordDetector",
    "LocalKeywordDetector",
    "MockWakeWordDetector",
    "normalize_wake_phrase",
    "WakeWordEngine",
    "WakeWordState",
    "InvalidStateTransitionError",
]
