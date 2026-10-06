"""
CHARVIS Background Runtime Package (Phase 16).
Provides safe, single-instance background runtime with local IPC and health monitoring.
"""

from runtime.client import RuntimeClient, RuntimeClientError, RuntimeConnectionRefusedError
from runtime.controller import RuntimeController
from runtime.health import HealthState, RuntimeHealthChecker
from runtime.ipc import IPCServer
from runtime.lifecycle import RuntimeAlreadyRunningError, RuntimeLock
from runtime.manager import RuntimeManager, get_runtime_controller, set_runtime_controller
from runtime.models import IPCRequest, IPCResponse, RuntimeStatus
from runtime.state import (
    InvalidStateTransitionError,
    RuntimeState,
    RuntimeStateMachine,
)

__all__ = [
    "RuntimeState",
    "InvalidStateTransitionError",
    "RuntimeStateMachine",
    "RuntimeStatus",
    "IPCRequest",
    "IPCResponse",
    "RuntimeLock",
    "RuntimeAlreadyRunningError",
    "IPCServer",
    "RuntimeClient",
    "RuntimeClientError",
    "RuntimeConnectionRefusedError",
    "HealthState",
    "RuntimeHealthChecker",
    "RuntimeController",
    "RuntimeManager",
    "get_runtime_controller",
    "set_runtime_controller",
]
