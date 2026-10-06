"""
Unit tests for RuntimeController lifecycle, idempotent shutdown, and status (Phase 16).
"""

from unittest.mock import MagicMock, patch
import pytest

from runtime.controller import RuntimeController
from runtime.lifecycle import RuntimeAlreadyRunningError
from runtime.state import RuntimeState


@pytest.fixture
def mock_brain():
    brain = MagicMock()
    brain.process_user_message.return_value = "Hello from mock brain"
    brain.memory_manager.session.count.return_value = 0
    brain.memory_manager.storage.close.return_value = None
    return brain


def test_controller_initial_state(tmp_path, mock_brain):
    """Verify controller starts in STOPPED state."""
    controller = RuntimeController(brain=mock_brain, runtime_dir=tmp_path)
    assert controller.state == RuntimeState.STOPPED
    status = controller.get_status()
    assert status.state == "STOPPED"
    assert status.process_id is None


def test_controller_start_and_stop_lifecycle(tmp_path, mock_brain):
    """Verify clean start, status check, and graceful shutdown."""
    controller = RuntimeController(brain=mock_brain, runtime_dir=tmp_path)

    controller.start(block=False)
    assert controller.state == RuntimeState.RUNNING

    status = controller.get_status()
    assert status.state == "RUNNING"
    assert status.process_id is not None
    assert status.port is not None
    assert status.port > 0

    # Clean shutdown
    controller.stop()
    assert controller.state == RuntimeState.STOPPED


def test_controller_idempotent_shutdown(tmp_path, mock_brain):
    """Verify calling stop() multiple times is completely safe."""
    controller = RuntimeController(brain=mock_brain, runtime_dir=tmp_path)
    controller.start(block=False)
    assert controller.state == RuntimeState.RUNNING

    controller.stop()
    assert controller.state == RuntimeState.STOPPED

    # Second stop call
    controller.stop()
    assert controller.state == RuntimeState.STOPPED


def test_controller_prevents_duplicate_start(tmp_path, mock_brain):
    """Verify second start() call when already RUNNING is safely ignored."""
    controller = RuntimeController(brain=mock_brain, runtime_dir=tmp_path)
    controller.start(block=False)
    assert controller.state == RuntimeState.RUNNING

    # Calling start again on same controller should be a no-op
    controller.start(block=False)
    assert controller.state == RuntimeState.RUNNING

    controller.stop()


def test_controller_duplicate_instance_rejection(tmp_path, mock_brain):
    """Verify starting another controller when lock is held raises RuntimeAlreadyRunningError."""
    controller1 = RuntimeController(brain=mock_brain, runtime_dir=tmp_path)
    controller1.start(block=False)

    controller2 = RuntimeController(brain=mock_brain, runtime_dir=tmp_path)
    with pytest.raises(RuntimeAlreadyRunningError):
        controller2.start(block=False)

    controller1.stop()
