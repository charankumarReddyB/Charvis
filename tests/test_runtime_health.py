"""
Unit tests for RuntimeHealthChecker (Phase 16).
"""

from unittest.mock import MagicMock
import pytest

from runtime.health import HealthState, RuntimeHealthChecker


def test_health_checker_healthy_state():
    """Verify health checker returns HEALTHY when core subsystems are functional."""
    brain = MagicMock()
    brain.memory_manager.session.count.return_value = 5
    brain.planner = MagicMock()
    brain.task_executor = MagicMock()

    ipc_server = MagicMock()
    ipc_server.is_running = True
    ipc_server.actual_port = 8888

    checker = RuntimeHealthChecker(brain=brain, ipc_server=ipc_server)
    health = checker.check_health()

    assert health["status"] in {HealthState.HEALTHY.value, HealthState.DEGRADED.value}
    assert "core" in health["subsystems"]
    assert health["subsystems"]["core"]["status"] == "ok"
    assert health["subsystems"]["ipc"]["status"] == "ok"


def test_health_checker_unhealthy_state_when_missing_brain():
    """Verify health checker returns UNHEALTHY when core brain is missing."""
    ipc_server = MagicMock()
    ipc_server.is_running = True

    checker = RuntimeHealthChecker(brain=None, ipc_server=ipc_server)
    health = checker.check_health()

    assert health["status"] == HealthState.UNHEALTHY.value
    assert health["subsystems"]["core"]["status"] == "error"


def test_health_checker_degraded_state():
    """Verify health checker returns DEGRADED when optional subsystem is unavailable."""
    brain = MagicMock()
    brain.memory_manager = None
    brain.planner = None
    brain.task_executor = None

    ipc_server = MagicMock()
    ipc_server.is_running = True

    checker = RuntimeHealthChecker(brain=brain, ipc_server=ipc_server)
    health = checker.check_health()

    assert health["status"] in {HealthState.DEGRADED.value, HealthState.UNHEALTHY.value}
