"""
Unit tests for Exit and Shutdown Behavior (Phase 18).
Ensures clean shutdown releases locks, cleans resources, transitions state to STOPPED,
and handles repeated exit requests idempotently without exceptions.
"""

from unittest.mock import MagicMock, patch
import pytest

from config import get_settings
from core.brain import AIBrain
from gui.tray import SystemTrayManager
from runtime.controller import RuntimeController
from runtime.state import RuntimeState


def test_runtime_controller_clean_shutdown(tmp_path):
    """Verify complete clean shutdown sequence in RuntimeController."""
    settings = get_settings()
    brain = AIBrain()
    controller = RuntimeController(settings=settings, brain=brain, runtime_dir=tmp_path)

    # Start controller
    controller.start(block=False)
    assert controller.state_machine.state == RuntimeState.RUNNING
    assert controller.runtime_lock.is_another_instance_running() is True

    # Clean shutdown
    controller.stop()
    assert controller.state_machine.state == RuntimeState.STOPPED
    assert controller.runtime_lock.is_another_instance_running() is False


def test_repeated_shutdown_is_idempotent(tmp_path):
    """Verify repeated shutdown calls on RuntimeController do not raise exceptions."""
    settings = get_settings()
    brain = AIBrain()
    controller = RuntimeController(settings=settings, brain=brain, runtime_dir=tmp_path)

    controller.start(block=False)
    controller.stop()
    assert controller.state_machine.state == RuntimeState.STOPPED

    # Repeated calls must be harmless
    controller.stop()
    controller.stop()
    assert controller.state_machine.state == RuntimeState.STOPPED


def test_tray_manager_repeated_stop():
    """Verify repeated stop calls on SystemTrayManager are idempotent."""
    tray = SystemTrayManager()
    tray.stop()
    tray.stop()
    assert tray._icon is None
