"""CHARVIS System Information and Control Tools.

Provides safe querying of system metrics (CPU, RAM, disk, battery, uptime, network)
and controlled, confirmed system actions (workstation lock, shutdown, restart).
Zero shell, command-line, or subprocess execution.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.safety import RiskLevel
from system.control import SystemController
from system.information import SystemInformationProvider
from tools.base import BaseTool
from tools.schemas import ToolParameter, ToolSchema


class GetSystemInfoTool(BaseTool):
    """Tool to retrieve basic operating system and environment specifications."""

    def __init__(self, provider: Optional[SystemInformationProvider] = None) -> None:
        self._provider = provider or SystemInformationProvider()

    @property
    def name(self) -> str:
        return "get_system_info"

    @property
    def description(self) -> str:
        return (
            "Retrieve basic operating system specifications including OS name, release, "
            "version, machine architecture, Python version, and hostname."
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
        self.validate_arguments(kwargs)
        info = self._provider.get_system_info()
        return {
            "success": True,
            **info,
        }


class GetCpuUsageTool(BaseTool):
    """Tool to retrieve bounded CPU utilization metrics."""

    def __init__(self, provider: Optional[SystemInformationProvider] = None) -> None:
        self._provider = provider or SystemInformationProvider()

    @property
    def name(self) -> str:
        return "get_cpu_usage"

    @property
    def description(self) -> str:
        return "Retrieve current CPU utilization percentage and CPU core count metrics."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="interval",
                    param_type="number",
                    description="Measurement sampling duration in seconds (0.05 to 1.0, default: 0.1)",
                    required=False,
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        interval = float(kwargs.get("interval", 0.1))
        metrics = self._provider.get_cpu_usage(interval=interval)
        return {
            "success": True,
            **metrics,
        }


class GetMemoryUsageTool(BaseTool):
    """Tool to retrieve RAM utilization metrics."""

    def __init__(self, provider: Optional[SystemInformationProvider] = None) -> None:
        self._provider = provider or SystemInformationProvider()

    @property
    def name(self) -> str:
        return "get_memory_usage"

    @property
    def description(self) -> str:
        return "Retrieve current RAM utilization metrics including total, used, available memory, and usage percentage."

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
        self.validate_arguments(kwargs)
        metrics = self._provider.get_memory_usage()
        return {
            "success": True,
            **metrics,
        }


class GetDiskUsageTool(BaseTool):
    """Tool to retrieve disk metrics for the configured system drive."""

    def __init__(self, provider: Optional[SystemInformationProvider] = None) -> None:
        self._provider = provider or SystemInformationProvider()

    @property
    def name(self) -> str:
        return "get_disk_usage"

    @property
    def description(self) -> str:
        return (
            "Retrieve disk space metrics (total, used, free space in GB and usage percentage) "
            "for the configured Windows system drive."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="drive",
                    param_type="string",
                    description="Windows drive letter to inspect (e.g. 'C:\\' or 'C:'). Defaults to configured system drive.",
                    required=False,
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        drive = kwargs.get("drive")
        metrics = self._provider.get_disk_usage(drive=drive)
        return {
            "success": True,
            **metrics,
        }


class GetBatteryStatusTool(BaseTool):
    """Tool to retrieve battery state and charging status."""

    def __init__(self, provider: Optional[SystemInformationProvider] = None) -> None:
        self._provider = provider or SystemInformationProvider()

    @property
    def name(self) -> str:
        return "get_battery_status"

    @property
    def description(self) -> str:
        return (
            "Retrieve battery charge level, charging status, and power connection state. "
            "Handles desktop workstations without battery gracefully."
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
        self.validate_arguments(kwargs)
        metrics = self._provider.get_battery_status()
        return {
            "success": True,
            **metrics,
        }


class GetUptimeTool(BaseTool):
    """Tool to retrieve system boot time and uptime duration."""

    def __init__(self, provider: Optional[SystemInformationProvider] = None) -> None:
        self._provider = provider or SystemInformationProvider()

    @property
    def name(self) -> str:
        return "get_uptime"

    @property
    def description(self) -> str:
        return "Retrieve system boot time and total system uptime formatted in days, hours, and minutes."

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
        self.validate_arguments(kwargs)
        metrics = self._provider.get_uptime()
        return {
            "success": True,
            **metrics,
        }


class GetNetworkStatusTool(BaseTool):
    """Tool to retrieve network connectivity and interface status."""

    def __init__(self, provider: Optional[SystemInformationProvider] = None) -> None:
        self._provider = provider or SystemInformationProvider()

    @property
    def name(self) -> str:
        return "get_network_status"

    @property
    def description(self) -> str:
        return (
            "Retrieve basic network status and active interface specifications. "
            "Does not capture packets, perform scanning, or inspect private traffic."
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
        self.validate_arguments(kwargs)
        status = self._provider.get_network_status()
        return {
            "success": True,
            **status,
        }


class LockWorkstationTool(BaseTool):
    """Tool to lock the active Windows desktop workstation."""

    def __init__(self, controller: Optional[SystemController] = None) -> None:
        self._controller = controller or SystemController()

    @property
    def name(self) -> str:
        return "lock_workstation"

    @property
    def description(self) -> str:
        return "Lock the Windows desktop workstation immediately. Requires human confirmation."

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

    def get_confirmation_message(self, arguments: Dict[str, Any]) -> Optional[str]:
        return "Lock the Windows workstation. The desktop session will be locked immediately."

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        res = self._controller.lock_workstation()
        return {
            "success": True,
            **res,
        }


class ShutdownSystemTool(BaseTool):
    """Tool to initiate Windows system shutdown."""

    def __init__(self, controller: Optional[SystemController] = None) -> None:
        self._controller = controller or SystemController()

    @property
    def name(self) -> str:
        return "shutdown_system"

    @property
    def description(self) -> str:
        return "Initiate Windows system shutdown. High-risk operation requiring explicit human authorization."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.HIGH_RISK

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def get_confirmation_message(self, arguments: Dict[str, Any]) -> Optional[str]:
        return "[HIGH RISK] Shut down the computer immediately. All unsaved work across the entire system may be lost."

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        res = self._controller.shutdown_system()
        return {
            "success": True,
            **res,
        }


class RestartSystemTool(BaseTool):
    """Tool to initiate Windows system restart."""

    def __init__(self, controller: Optional[SystemController] = None) -> None:
        self._controller = controller or SystemController()

    @property
    def name(self) -> str:
        return "restart_system"

    @property
    def description(self) -> str:
        return "Initiate Windows system restart. High-risk operation requiring explicit human authorization."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.HIGH_RISK

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def get_confirmation_message(self, arguments: Dict[str, Any]) -> Optional[str]:
        return "[HIGH RISK] Restart the computer immediately. All unsaved work across the entire system may be lost."

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        res = self._controller.restart_system()
        return {
            "success": True,
            **res,
        }
