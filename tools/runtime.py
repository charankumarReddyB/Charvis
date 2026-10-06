from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from core.safety import RiskLevel
from logger import get_logger
from tools.base import BaseTool
from tools.schemas import ToolParameter, ToolSchema

if TYPE_CHECKING:
    from runtime.health import RuntimeHealthChecker
    from runtime.manager import RuntimeManager
    from startup.windows import WindowsStartupManager

logger = get_logger("CHARVIS.Tools.Runtime")


# Global instances for tool access
_STARTUP_MANAGER: Optional[Any] = None
_RUNTIME_MANAGER: Optional[Any] = None


def get_startup_manager() -> Any:
    global _STARTUP_MANAGER
    if _STARTUP_MANAGER is None:
        from startup.windows import WindowsStartupManager
        _STARTUP_MANAGER = WindowsStartupManager()
    return _STARTUP_MANAGER


def set_startup_manager(manager: Optional[Any]) -> None:
    global _STARTUP_MANAGER
    _STARTUP_MANAGER = manager


def get_runtime_manager() -> Any:
    global _RUNTIME_MANAGER
    if _RUNTIME_MANAGER is None:
        from runtime.manager import RuntimeManager
        _RUNTIME_MANAGER = RuntimeManager()
    return _RUNTIME_MANAGER


def set_runtime_manager(manager: Optional[Any]) -> None:
    global _RUNTIME_MANAGER
    _RUNTIME_MANAGER = manager


class GetRuntimeStatusTool(BaseTool):
    """Inspect the current operational status, uptime, PID, and active tasks of CHARVIS runtime."""

    def __init__(self, manager: Optional[RuntimeManager] = None) -> None:
        self._manager = manager

    @property
    def name(self) -> str:
        return "get_runtime_status"

    @property
    def description(self) -> str:
        return (
            "Check the current operational status of the CHARVIS background runtime. "
            "Returns runtime state (RUNNING, STOPPED, ERROR, etc.), version, process ID, "
            "uptime in seconds, and active task count."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        mgr = self._manager or get_runtime_manager()
        status = mgr.get_status()
        return status.to_dict()


class GetRuntimeHealthTool(BaseTool):
    """Inspect the operational health of CHARVIS core subsystems."""

    def __init__(self, checker: Optional[RuntimeHealthChecker] = None) -> None:
        self._checker = checker

    @property
    def name(self) -> str:
        return "get_runtime_health"

    @property
    def description(self) -> str:
        return (
            "Inspect the health and responsiveness of CHARVIS subsystems: "
            "AI brain core, memory database, task planner, voice, browser, and local IPC. "
            "Returns HEALTHY, DEGRADED, or UNHEALTHY status."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        if self._checker:
            return self._checker.check_health()
        from runtime.manager import get_runtime_controller
        controller = get_runtime_controller()
        return controller.health_check()


class GetStartupStatusTool(BaseTool):
    """Check whether CHARVIS is configured to launch with Windows."""

    def __init__(self, startup_manager: Optional[WindowsStartupManager] = None) -> None:
        self._startup_manager = startup_manager

    @property
    def name(self) -> str:
        return "get_startup_status"

    @property
    def description(self) -> str:
        return (
            "Inspect whether CHARVIS is currently configured to launch automatically "
            "in the background when logging into Windows."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        mgr = self._startup_manager or get_startup_manager()
        return mgr.get_status().to_dict()


class StopRuntimeTool(BaseTool):
    """Gracefully shut down the background runtime. Requires user confirmation."""

    def __init__(self, manager: Optional[RuntimeManager] = None) -> None:
        self._manager = manager

    @property
    def name(self) -> str:
        return "stop_runtime"

    @property
    def description(self) -> str:
        return (
            "Request a graceful shutdown of the CHARVIS background runtime. "
            "Requires explicit user confirmation."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        mgr = self._manager or get_runtime_manager()
        success = mgr.stop_runtime()
        return {"success": success, "message": "Runtime stop requested"}


class RestartRuntimeTool(BaseTool):
    """Restart the background runtime. Requires user confirmation."""

    def __init__(self, manager: Optional[RuntimeManager] = None) -> None:
        self._manager = manager

    @property
    def name(self) -> str:
        return "restart_runtime"

    @property
    def description(self) -> str:
        return (
            "Restart the CHARVIS background runtime. "
            "Requires explicit user confirmation."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        from runtime.manager import get_runtime_controller
        controller = get_runtime_controller()
        controller.restart()
        return {"success": True, "message": "Runtime restarted"}


class EnableStartupTool(BaseTool):
    """Configure CHARVIS to launch automatically with Windows. Requires user confirmation."""

    def __init__(self, startup_manager: Optional[WindowsStartupManager] = None) -> None:
        self._startup_manager = startup_manager

    @property
    def name(self) -> str:
        return "enable_startup"

    @property
    def description(self) -> str:
        return (
            "Enable CHARVIS to start in the background when logging into Windows. "
            "Places a transparent launcher shortcut in your Windows Startup directory. "
            "Requires explicit user confirmation."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        mgr = self._startup_manager or get_startup_manager()
        success = mgr.enable()
        return {"success": success, "status": mgr.get_status().to_dict()}


class DisableStartupTool(BaseTool):
    """Disable CHARVIS automatic launch with Windows. Requires user confirmation."""

    def __init__(self, startup_manager: Optional[WindowsStartupManager] = None) -> None:
        self._startup_manager = startup_manager

    @property
    def name(self) -> str:
        return "disable_startup"

    @property
    def description(self) -> str:
        return (
            "Disable CHARVIS from starting automatically when logging into Windows. "
            "Removes the launcher shortcut from your Windows Startup directory. "
            "Requires explicit user confirmation."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        mgr = self._startup_manager or get_startup_manager()
        success = mgr.disable()
        return {"success": success, "status": mgr.get_status().to_dict()}


class StartRuntimeTool(BaseTool):
    """Start the CHARVIS background runtime process. Requires user confirmation."""

    def __init__(self, manager: Optional[RuntimeManager] = None) -> None:
        self._manager = manager

    @property
    def name(self) -> str:
        return "start_runtime"

    @property
    def description(self) -> str:
        return (
            "Launch the CHARVIS background runtime process. "
            "Requires explicit user confirmation."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        mgr = self._manager or get_runtime_manager()
        if mgr.is_running():
            return {"success": True, "message": "Runtime is already running", "status": mgr.get_status().to_dict()}
        success = mgr.start_background_process()
        return {"success": success, "message": "Runtime started" if success else "Failed to start runtime"}
