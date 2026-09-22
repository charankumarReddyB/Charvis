"""Unit tests for CHARVIS Windows System Control Layer (Phase 7).

Verifies workstation locking, shutdown, and restart controls.
CRITICAL: All Windows C-APIs and privilege adjustments are strictly mocked.
Never actually locks, shuts down, or restarts the test runner machine.
"""

from unittest.mock import MagicMock, patch
import pytest

from core.safety import RiskLevel, SafetyManager
from system.control import SystemController
from tools.router import ToolRouter
from tools.system import (
    LockWorkstationTool,
    RestartSystemTool,
    ShutdownSystemTool,
)


@pytest.fixture
def mock_controller() -> SystemController:
    controller = SystemController()
    controller._lock_workstation_api = MagicMock(return_value=True)
    controller._shutdown_system_api = MagicMock(return_value=True)
    controller._restart_system_api = MagicMock(return_value=True)
    controller._enable_shutdown_privilege = MagicMock()
    return controller


def test_lock_workstation_success(mock_controller: SystemController) -> None:
    """Test lock_workstation calls the lock API and returns success."""
    result = mock_controller.lock_workstation()
    assert result["status"] == "locked"
    mock_controller._lock_workstation_api.assert_called_once()


def test_lock_workstation_api_failure(mock_controller: SystemController) -> None:
    """Test lock_workstation raises RuntimeError on API failure."""
    mock_controller._lock_workstation_api.return_value = False
    with patch("ctypes.GetLastError", return_value=5):
        with pytest.raises(RuntimeError, match="LockWorkStation failed"):
            mock_controller.lock_workstation()


def test_shutdown_system_success(mock_controller: SystemController) -> None:
    """Test shutdown_system acquires privilege and executes shutdown API."""
    result = mock_controller.shutdown_system()
    assert result["status"] == "shutting_down"
    mock_controller._enable_shutdown_privilege.assert_called_once()
    mock_controller._shutdown_system_api.assert_called_once()


def test_shutdown_system_api_failure(mock_controller: SystemController) -> None:
    """Test shutdown_system raises RuntimeError on API failure."""
    mock_controller._shutdown_system_api.return_value = False
    with patch("ctypes.GetLastError", return_value=1314):
        with pytest.raises(RuntimeError, match="Windows shutdown failed"):
            mock_controller.shutdown_system()


def test_restart_system_success(mock_controller: SystemController) -> None:
    """Test restart_system acquires privilege and executes restart API."""
    result = mock_controller.restart_system()
    assert result["status"] == "restarting"
    mock_controller._enable_shutdown_privilege.assert_called_once()
    mock_controller._restart_system_api.assert_called_once()


def test_restart_system_api_failure(mock_controller: SystemController) -> None:
    """Test restart_system raises RuntimeError on API failure."""
    mock_controller._restart_system_api.return_value = False
    with patch("ctypes.GetLastError", return_value=1314):
        with pytest.raises(RuntimeError, match="Windows restart failed"):
            mock_controller.restart_system()


def test_system_control_non_windows_rejection() -> None:
    """Test SystemController raises OSError on non-Windows platforms."""
    controller = SystemController()
    controller._is_windows = False
    with pytest.raises(OSError, match="only supported on Windows"):
        controller.lock_workstation()
    with pytest.raises(OSError, match="only supported on Windows"):
        controller.shutdown_system()
    with pytest.raises(OSError, match="only supported on Windows"):
        controller.restart_system()


def test_system_control_tool_risk_levels(mock_controller: SystemController) -> None:
    """Verify tool risk classifications."""
    lock_tool = LockWorkstationTool(mock_controller)
    shutdown_tool = ShutdownSystemTool(mock_controller)
    restart_tool = RestartSystemTool(mock_controller)

    assert lock_tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED
    assert shutdown_tool.risk_level == RiskLevel.HIGH_RISK
    assert restart_tool.risk_level == RiskLevel.HIGH_RISK


def test_system_control_confirmation_messages(mock_controller: SystemController) -> None:
    """Verify confirmation warning messages explain risk to user."""
    lock_tool = LockWorkstationTool(mock_controller)
    shutdown_tool = ShutdownSystemTool(mock_controller)
    restart_tool = RestartSystemTool(mock_controller)

    lock_msg = lock_tool.get_confirmation_message({})
    assert "lock" in lock_msg.lower()

    shutdown_msg = shutdown_tool.get_confirmation_message({})
    assert "HIGH RISK" in shutdown_msg
    assert "shut down" in shutdown_msg.lower()
    assert "unsaved work" in shutdown_msg.lower()

    restart_msg = restart_tool.get_confirmation_message({})
    assert "HIGH RISK" in restart_msg
    assert "restart" in restart_msg.lower()
    assert "unsaved work" in restart_msg.lower()


def test_safety_enforcement_denied_confirmation(mock_controller: SystemController) -> None:
    """Verify SafetyManager and ToolRouter block execution when user denies confirmation."""
    from tools.registry import ToolRegistry

    registry = ToolRegistry()
    lock_tool = LockWorkstationTool(mock_controller)
    shutdown_tool = ShutdownSystemTool(mock_controller)
    restart_tool = RestartSystemTool(mock_controller)

    registry.register(lock_tool)
    registry.register(shutdown_tool)
    registry.register(restart_tool)

    safety = SafetyManager()
    router = ToolRouter(registry, safety)

    # Deny callback
    deny_callback = MagicMock(return_value=False)

    # 1. Lock denied
    res_lock = router.execute_tool("lock_workstation", {}, confirmation_callback=deny_callback)
    assert res_lock.success is False
    assert "did not authorize" in res_lock.error.lower()
    mock_controller._lock_workstation_api.assert_not_called()

    # 2. Shutdown denied
    res_shut = router.execute_tool("shutdown_system", {}, confirmation_callback=deny_callback)
    assert res_shut.success is False
    assert "did not authorize" in res_shut.error.lower()
    mock_controller._shutdown_system_api.assert_not_called()

    # 3. Restart denied
    res_reboot = router.execute_tool("restart_system", {}, confirmation_callback=deny_callback)
    assert res_reboot.success is False
    assert "did not authorize" in res_reboot.error.lower()
    mock_controller._restart_system_api.assert_not_called()


def test_safety_enforcement_approved_confirmation(mock_controller: SystemController) -> None:
    """Verify SafetyManager and ToolRouter execute action when user approves confirmation."""
    from tools.registry import ToolRegistry

    registry = ToolRegistry()
    lock_tool = LockWorkstationTool(mock_controller)
    shutdown_tool = ShutdownSystemTool(mock_controller)
    restart_tool = RestartSystemTool(mock_controller)

    registry.register(lock_tool)
    registry.register(shutdown_tool)
    registry.register(restart_tool)

    safety = SafetyManager()
    router = ToolRouter(registry, safety)

    approve_callback = MagicMock(return_value=True)

    # Lock approved
    res_lock = router.execute_tool("lock_workstation", {}, confirmation_callback=approve_callback)
    assert res_lock.success is True
    assert res_lock.data["status"] == "locked"
    mock_controller._lock_workstation_api.assert_called_once()

    # Shutdown approved
    res_shut = router.execute_tool("shutdown_system", {}, confirmation_callback=approve_callback)
    assert res_shut.success is True
    assert res_shut.data["status"] == "shutting_down"
    mock_controller._shutdown_system_api.assert_called_once()

    # Restart approved
    res_reboot = router.execute_tool("restart_system", {}, confirmation_callback=approve_callback)
    assert res_reboot.success is True
    assert res_reboot.data["status"] == "restarting"
    mock_controller._restart_system_api.assert_called_once()
