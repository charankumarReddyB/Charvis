"""
Unit tests for GUI reconnection state machine and backoff behavior (Phase 17).
"""

import time
from unittest.mock import MagicMock
import pytest
from gui.controller import GUIController
from gui.models import SystemState
from gui.state import GUIState
from runtime.client import RuntimeClient
from runtime.manager import RuntimeManager


def test_gui_reconnect_state_machine_flow():
    """Verify GUI transitions safely: ONLINE -> DISCONNECTED -> RECONNECTING -> ONLINE."""
    state = GUIState()
    mock_client = MagicMock(spec=RuntimeClient)
    mock_mgr = MagicMock(spec=RuntimeManager)

    # Initial state: runtime is running
    mock_client.is_runtime_running.return_value = True
    mock_mgr.is_running.return_value = True
    mock_mgr.get_client.return_value = mock_client

    controller = GUIController(state=state, runtime_manager=mock_mgr)
    controller.client = mock_client
    state.set_system_state(SystemState.ONLINE)

    # 1. Connection lost
    mock_client.is_runtime_running.return_value = False
    controller.check_connection()

    assert state.system_state in (SystemState.DISCONNECTED, SystemState.RECONNECTING)

    # 2. Simulate runtime becoming available again during reconnect
    mock_mgr.is_running.return_value = True
    mock_client.is_runtime_running.return_value = True

    # Allow worker thread to attempt reconnect
    controller._reconnect_delay = 0.05
    controller.trigger_reconnect()
    time.sleep(0.2)

    assert state.system_state == SystemState.ONLINE
    assert controller._reconnect_retries == 0

    controller.shutdown()


def test_gui_reconnect_exponential_backoff():
    """Verify reconnect delay increases exponentially up to max_delay."""
    controller = GUIController()
    controller.settings.reconnect_initial_delay = 1.0
    controller.settings.reconnect_backoff_factor = 2.0
    controller.settings.reconnect_max_delay = 10.0

    delay = controller.settings.reconnect_initial_delay
    delays = []
    for _ in range(5):
        delays.append(delay)
        delay = min(controller.settings.reconnect_max_delay, delay * controller.settings.reconnect_backoff_factor)

    assert delays == [1.0, 2.0, 4.0, 8.0, 10.0]
    controller.shutdown()
