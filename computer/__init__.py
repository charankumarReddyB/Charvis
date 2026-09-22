"""
Computer interaction package for CHARVIS.
Provides deterministic keyboard and mouse automation via PyAutoGUI with strict safety boundaries.
"""

from computer.keyboard import (
    ComputerSafetyError,
    FailSafeTriggeredError,
    KeyboardController,
    normalize_key,
)
from computer.mouse import MouseController

__all__ = [
    "KeyboardController",
    "MouseController",
    "ComputerSafetyError",
    "FailSafeTriggeredError",
    "normalize_key",
]
