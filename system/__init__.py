"""CHARVIS System Management Subsystem.

Provides hardware/OS information querying and controlled Windows system actions.
"""

from system.information import SystemInformationProvider
from system.control import SystemController

__all__ = [
    "SystemInformationProvider",
    "SystemController",
]
