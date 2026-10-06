"""
CHARVIS User Activation Subsystem (Phase 18).
"""

from activation.hotkey import GlobalHotkeyManager
from activation.manager import ActivationManager
from activation.models import (
    ActivationSession,
    ActivationSource,
    ActivationState,
    ActivationStateError,
)

__all__ = [
    "ActivationState",
    "ActivationSource",
    "ActivationSession",
    "ActivationStateError",
    "ActivationManager",
    "GlobalHotkeyManager",
]
