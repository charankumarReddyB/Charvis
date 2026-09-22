"""Unit tests for CHARVIS System Information Subsystem (Phase 7).

Verifies safe retrieval of CPU, RAM, disk, battery, uptime, and network metrics.
All external hardware and library states are tested with real and mocked environments.
"""

from collections import namedtuple
from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest

from core.safety import RiskLevel
from system.information import SystemInformationProvider
from tools.system import (
    GetBatteryStatusTool,
    GetCpuUsageTool,
    GetDiskUsageTool,
    GetMemoryUsageTool,
    GetNetworkStatusTool,
    GetSystemInfoTool,
    GetUptimeTool,
)


@pytest.fixture
def provider() -> SystemInformationProvider:
    return SystemInformationProvider(system_drive="C:\\")


def test_get_system_info(provider: SystemInformationProvider) -> None:
    """Test get_system_info returns expected keys with non-empty string values."""
    info = provider.get_system_info()
    assert "os_name" in info
    assert "os_release" in info
    assert "os_version" in info
    assert "architecture" in info
    assert "python_version" in info
    assert "hostname" in info

    assert isinstance(info["os_name"], str) and len(info["os_name"]) > 0
    assert isinstance(info["architecture"], str) and len(info["architecture"]) > 0
    assert isinstance(info["python_version"], str) and len(info["python_version"]) > 0


def test_get_cpu_usage(provider: SystemInformationProvider) -> None:
    """Test get_cpu_usage returns bounded metrics."""
    metrics = provider.get_cpu_usage(interval=0.05)
    assert "cpu_percent" in metrics
    assert "logical_cores" in metrics
    assert "physical_cores" in metrics

    assert 0.0 <= metrics["cpu_percent"] <= 100.0
    assert metrics["logical_cores"] >= 1
    assert metrics["physical_cores"] >= 1


def test_get_cpu_usage_mocked(provider: SystemInformationProvider) -> None:
    """Test get_cpu_usage with mocked psutil."""
    with patch("psutil.cpu_percent", return_value=42.5) as mock_pct, \
         patch("psutil.cpu_count", side_effect=[8, 4]):
        metrics = provider.get_cpu_usage(interval=0.1)
        mock_pct.assert_called_once_with(interval=0.1)
        assert metrics["cpu_percent"] == 42.5
        assert metrics["logical_cores"] == 8
        assert metrics["physical_cores"] == 4


def test_get_memory_usage(provider: SystemInformationProvider) -> None:
    """Test get_memory_usage returns valid memory breakdown."""
    metrics = provider.get_memory_usage()
    assert "total_bytes" in metrics
    assert "used_bytes" in metrics
    assert "available_bytes" in metrics
    assert "usage_percent" in metrics
    assert "total_gb" in metrics
    assert "used_gb" in metrics
    assert "available_gb" in metrics

    assert metrics["total_bytes"] > 0
    assert metrics["used_bytes"] >= 0
    assert metrics["available_bytes"] >= 0
    assert 0.0 <= metrics["usage_percent"] <= 100.0


def test_get_memory_usage_mocked(provider: SystemInformationProvider) -> None:
    """Test get_memory_usage calculations with mocked psutil."""
    VirtualMemory = namedtuple("VirtualMemory", ["total", "used", "available", "percent"])
    mock_vm = VirtualMemory(
        total=16 * (1024**3),
        used=8 * (1024**3),
        available=8 * (1024**3),
        percent=50.0,
    )
    with patch("psutil.virtual_memory", return_value=mock_vm):
        metrics = provider.get_memory_usage()
        assert metrics["total_gb"] == 16.0
        assert metrics["used_gb"] == 8.0
        assert metrics["available_gb"] == 8.0
        assert metrics["usage_percent"] == 50.0


def test_get_disk_usage(provider: SystemInformationProvider) -> None:
    """Test get_disk_usage on configured drive."""
    metrics = provider.get_disk_usage()
    assert metrics["drive"] == "C:\\"
    assert metrics["total_bytes"] > 0
    assert metrics["free_bytes"] > 0
    assert 0.0 <= metrics["usage_percent"] <= 100.0


def test_get_disk_usage_invalid_drive_fallback(provider: SystemInformationProvider) -> None:
    """Test get_disk_usage rejects directory traversal paths and falls back to configured drive."""
    DiskUsage = namedtuple("DiskUsage", ["total", "used", "free", "percent"])
    mock_du = DiskUsage(total=500 * (1024**3), used=200 * (1024**3), free=300 * (1024**3), percent=40.0)

    with patch("psutil.disk_usage", return_value=mock_du) as mock_disk:
        # Pass dangerous path that should be sanitized / rejected to default drive
        metrics = provider.get_disk_usage(drive="../../Windows/System32")
        mock_disk.assert_called_once_with("C:\\")
        assert metrics["drive"] == "C:\\"
        assert metrics["free_gb"] == 300.0


def test_get_battery_status_present(provider: SystemInformationProvider) -> None:
    """Test get_battery_status when battery hardware is present."""
    Battery = namedtuple("Battery", ["percent", "secsleft", "power_plugged"])
    mock_bat = Battery(percent=85.0, secsleft=7200, power_plugged=False)

    with patch("psutil.sensors_battery", return_value=mock_bat):
        metrics = provider.get_battery_status()
        assert metrics["has_battery"] is True
        assert metrics["percent"] == 85.0
        assert metrics["power_plugged"] is False
        assert metrics["seconds_left"] == 7200


def test_get_battery_status_desktop_no_battery(provider: SystemInformationProvider) -> None:
    """Test get_battery_status gracefully handles systems with no battery."""
    with patch("psutil.sensors_battery", return_value=None):
        metrics = provider.get_battery_status()
        assert metrics["has_battery"] is False
        assert metrics["percent"] is None
        assert metrics["power_plugged"] is True
        assert "No battery detected" in metrics["message"]


def test_get_uptime(provider: SystemInformationProvider) -> None:
    """Test get_uptime formatting and duration."""
    mock_boot = 1700000000.0
    mock_now = mock_boot + 3665.0  # 1 hour, 1 minute, 5 seconds

    with patch("psutil.boot_time", return_value=mock_boot), \
         patch("time.time", return_value=mock_now):
        uptime_data = provider.get_uptime()
        assert uptime_data["uptime_seconds"] == 3665
        assert uptime_data["uptime_formatted"] == "1h 1m 5s"
        assert "boot_time" in uptime_data


def test_get_network_status(provider: SystemInformationProvider) -> None:
    """Test get_network_status parses active interfaces safely."""
    Snetstat = namedtuple("Snetstat", ["isup", "duplex", "speed", "mtu", "flags"])
    mock_stats = {
        "Loopback Pseudo-Interface 1": Snetstat(isup=True, duplex=0, speed=1000, mtu=1500, flags=""),
        "Wi-Fi": Snetstat(isup=True, duplex=0, speed=300, mtu=1500, flags=""),
        "Ethernet": Snetstat(isup=False, duplex=0, speed=0, mtu=1500, flags=""),
    }

    with patch("psutil.net_if_stats", return_value=mock_stats):
        net_info = provider.get_network_status()
        assert net_info["connected"] is True
        assert net_info["total_interfaces"] == 3
        # Should contain loopback and Wi-Fi as active
        active_names = [iface["interface"] for iface in net_info["active_interfaces"]]
        assert "Wi-Fi" in active_names
        assert "Loopback Pseudo-Interface 1" in active_names
        assert "Ethernet" not in active_names


def test_system_information_tools_metadata_and_execution(provider: SystemInformationProvider) -> None:
    """Verify all 7 system info tools are classified as SAFE and execute successfully."""
    tools = [
        GetSystemInfoTool(provider),
        GetCpuUsageTool(provider),
        GetMemoryUsageTool(provider),
        GetDiskUsageTool(provider),
        GetBatteryStatusTool(provider),
        GetUptimeTool(provider),
        GetNetworkStatusTool(provider),
    ]

    for tool in tools:
        assert tool.risk_level == RiskLevel.SAFE, f"Tool {tool.name} must be SAFE"
        result = tool.execute()
        assert result.get("success") is True, f"Tool {tool.name} execution failed: {result}"
