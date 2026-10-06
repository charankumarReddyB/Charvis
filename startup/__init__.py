"""
CHARVIS Windows Startup Integration Package (Phase 16).
Provides safe, user-controlled startup integration using the standard Windows Startup folder.
"""

from startup.models import StartupStatus
from startup.windows import WindowsStartupManager

__all__ = [
    "StartupStatus",
    "WindowsStartupManager",
]
