"""
CHARVIS GUI Package (Phase 15: Desktop GUI)
"""

from gui.app import CharvisApp
from gui.state import GUIState
from gui.controller import GUIController
from gui.models import AppView, SystemState, ChatMessage, TaskDisplayItem, ConfirmationRequest
import gui.theme as theme

__all__ = [
    "CharvisApp",
    "GUIState",
    "GUIController",
    "AppView",
    "SystemState",
    "ChatMessage",
    "TaskDisplayItem",
    "ConfirmationRequest",
    "theme",
]
