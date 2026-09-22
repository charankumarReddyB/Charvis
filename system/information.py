"""CHARVIS System Information Layer.

Provides controlled, safe retrieval of Windows hardware, OS, and network
metrics using standard Python platform APIs and psutil.
Zero shell or subprocess execution.
"""

from __future__ import annotations

import datetime
import os
import platform
import re
import time
from typing import Any, Dict, List, Optional

import psutil

from config import get_settings
from logger import get_logger

logger = get_logger(__name__)


class SystemInformationProvider:
    """Safe, non-destructive provider for Windows system and hardware telemetry."""

    def __init__(self, system_drive: Optional[str] = None) -> None:
        self.system_drive = system_drive or get_settings().system_drive

    def get_system_info(self) -> Dict[str, Any]:
        """Return safe, high-level operating system and environment details.

        Does not expose sensitive private identifiers or credentials.
        """
        logger.debug("Retrieving system information payload")
        return {
            "os_name": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
        }

    def get_cpu_usage(self, interval: float = 0.1) -> Dict[str, Any]:
        """Return CPU utilization percentage and core metrics.

        Performs a single, bounded non-blocking measurement.
        """
        safe_interval = max(0.05, min(1.0, float(interval)))
        cpu_pct = psutil.cpu_percent(interval=safe_interval)
        logical_cores = psutil.cpu_count(logical=True) or 1
        physical_cores = psutil.cpu_count(logical=False) or logical_cores

        logger.debug("Retrieved CPU usage: %s%% across %d logical cores", cpu_pct, logical_cores)
        return {
            "cpu_percent": float(cpu_pct),
            "logical_cores": int(logical_cores),
            "physical_cores": int(physical_cores),
        }

    def get_memory_usage(self) -> Dict[str, Any]:
        """Return current RAM utilization metrics."""
        vm = psutil.virtual_memory()
        total_gb = round(vm.total / (1024**3), 2)
        used_gb = round(vm.used / (1024**3), 2)
        available_gb = round(vm.available / (1024**3), 2)

        logger.debug("Retrieved memory usage: %s%% (%s GB / %s GB)", vm.percent, used_gb, total_gb)
        return {
            "total_bytes": int(vm.total),
            "used_bytes": int(vm.used),
            "available_bytes": int(vm.available),
            "usage_percent": float(vm.percent),
            "total_gb": total_gb,
            "used_gb": used_gb,
            "available_gb": available_gb,
        }

    def get_disk_usage(self, drive: Optional[str] = None) -> Dict[str, Any]:
        """Return disk usage metrics for the configured system drive.

        Does not scan the filesystem tree or accept arbitrary folder paths.
        """
        target_drive = drive.strip() if drive else self.system_drive

        # Strictly validate that target_drive is a drive root like 'C:\' or 'C:'
        drive_pattern = re.compile(r"^[a-zA-Z]:[\\/]?$")
        if not drive_pattern.match(target_drive):
            logger.warning("Rejected unapproved drive identifier '%s', falling back to '%s'", drive, self.system_drive)
            target_drive = self.system_drive

        # Normalize to Windows root path e.g. 'C:\'
        drive_letter = target_drive[0].upper()
        normalized_drive = f"{drive_letter}:\\"

        try:
            du = psutil.disk_usage(normalized_drive)
        except Exception as err:
            logger.error("Failed to query disk usage for drive %s: %s", normalized_drive, err)
            raise ValueError(f"Could not retrieve disk usage for drive '{normalized_drive}': {err}") from err

        total_gb = round(du.total / (1024**3), 2)
        used_gb = round(du.used / (1024**3), 2)
        free_gb = round(du.free / (1024**3), 2)

        logger.debug("Retrieved disk usage for %s: %s%% (%s GB free)", normalized_drive, du.percent, free_gb)
        return {
            "drive": normalized_drive,
            "total_bytes": int(du.total),
            "used_bytes": int(du.used),
            "free_bytes": int(du.free),
            "usage_percent": float(du.percent),
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
        }

    def get_battery_status(self) -> Dict[str, Any]:
        """Return battery charge level, charging status, and power state.

        Gracefully handles desktop workstations with no battery.
        """
        battery = psutil.sensors_battery()
        if battery is None:
            logger.debug("No battery hardware detected")
            return {
                "has_battery": False,
                "percent": None,
                "power_plugged": True,
                "charging": None,
                "seconds_left": None,
                "message": "No battery detected (desktop workstation or external AC power only).",
            }

        secs_left: Optional[int] = None
        if (
            battery.secsleft is not None
            and battery.secsleft != psutil.POWER_TIME_UNLIMITED
            and battery.secsleft != psutil.POWER_TIME_UNKNOWN
            and battery.secsleft > 0
        ):
            secs_left = int(battery.secsleft)

        logger.debug("Retrieved battery status: %s%%, plugged=%s", battery.percent, battery.power_plugged)
        return {
            "has_battery": True,
            "percent": float(battery.percent),
            "power_plugged": bool(battery.power_plugged),
            "charging": bool(battery.power_plugged and battery.percent < 100),
            "seconds_left": secs_left,
            "message": f"Battery at {battery.percent:.0f}%, {'plugged in' if battery.power_plugged else 'on battery power'}.",
        }

    def get_uptime(self) -> Dict[str, Any]:
        """Return system boot time and uptime duration."""
        boot_timestamp = psutil.boot_time()
        now = time.time()
        uptime_seconds = max(0.0, now - boot_timestamp)

        boot_datetime = datetime.datetime.fromtimestamp(boot_timestamp)
        boot_time_str = boot_datetime.strftime("%Y-%m-%d %H:%M:%S")

        # Format uptime duration
        total_secs = int(uptime_seconds)
        days, rem = divmod(total_secs, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0 or days > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or hours > 0 or days > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        uptime_formatted = " ".join(parts)

        logger.debug("Retrieved uptime: %s (boot: %s)", uptime_formatted, boot_time_str)
        return {
            "boot_time": boot_time_str,
            "uptime_seconds": total_secs,
            "uptime_formatted": uptime_formatted,
        }

    def get_network_status(self) -> Dict[str, Any]:
        """Return high-level network interface and connection status.

        Strictly avoids packet capture, traffic inspection, or port scanning.
        """
        try:
            stats = psutil.net_if_stats()
        except Exception as err:
            logger.warning("Failed to query network interfaces: %s", err)
            stats = {}

        active_interfaces: List[Dict[str, Any]] = []
        has_active_connection = False

        for name, if_stat in stats.items():
            is_loopback = "loopback" in name.lower() or name.startswith("lo")
            if if_stat.isup:
                if not is_loopback:
                    has_active_connection = True
                active_interfaces.append(
                    {
                        "interface": name,
                        "is_up": bool(if_stat.isup),
                        "speed_mbps": int(if_stat.speed) if if_stat.speed > 0 else 0,
                        "is_loopback": is_loopback,
                    }
                )

        logger.debug("Retrieved network status: connected=%s, %d interfaces up", has_active_connection, len(active_interfaces))
        return {
            "connected": has_active_connection,
            "total_interfaces": len(stats),
            "active_interfaces": active_interfaces,
        }
