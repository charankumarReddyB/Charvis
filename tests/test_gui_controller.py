"""
Unit tests for CHARVIS GUIController (Phase 15).
"""

import time
import threading
import pytest
from unittest.mock import MagicMock, patch

from gui.state import GUIState
from gui.controller import GUIController
from gui.models import SystemState, AppView, ConfirmationRequest


@pytest.fixture
def mock_brain():
    brain = MagicMock()
    brain.process_user_message.return_value = "Mock response from CHARVIS"
    brain.registry.count.return_value = 68
    brain.memory_manager.get_all.return_value = [
        {"key": "test_user", "value": "Charan", "category": "user_fact", "confidence": 1.0}
    ]
    return brain


@pytest.fixture
def controller_setup(mock_brain):
    state = GUIState()
    dispatched_callbacks = []

    def mock_dispatcher(cb):
        dispatched_callbacks.append(cb)
        # Execute immediately on simulated main thread
        cb()

    ctrl = GUIController(
        state=state,
        ui_dispatcher=mock_dispatcher,
        brain=mock_brain,
    )
    return ctrl, state, dispatched_callbacks, mock_brain


def test_controller_initialization(controller_setup):
    ctrl, state, _, _ = controller_setup
    assert ctrl.state == state
    assert ctrl.brain is not None
    ctrl.shutdown()


def test_controller_send_user_message(controller_setup):
    ctrl, state, _, mock_brain = controller_setup

    ctrl.send_user_message("What is the weather?")
    # Wait for thread pool execution
    time.sleep(0.3)

    assert len(state.messages) >= 2
    assert state.messages[0].role == "user"
    assert state.messages[0].content == "What is the weather?"
    assert state.messages[1].role == "assistant"
    assert "Mock response" in state.messages[1].content
    assert state.system_state == SystemState.IDLE
    ctrl.shutdown()


def test_controller_handle_confirmation_approved(controller_setup):
    ctrl, state, _, _ = controller_setup

    # Test confirmation in background thread
    result_box = []

    def confirm_worker():
        ans = ctrl.handle_confirmation("test_tool", {"arg1": "val1"}, "high", "Custom warning")
        result_box.append(ans)

    t = threading.Thread(target=confirm_worker)
    t.start()

    # Wait for state to receive confirmation request
    for _ in range(20):
        if state.pending_confirmation is not None:
            break
        time.sleep(0.05)

    assert state.pending_confirmation is not None
    assert state.pending_confirmation.tool_name == "test_tool"

    # Approve it
    state.pending_confirmation.approve()
    t.join(timeout=1.0)

    assert len(result_box) == 1
    assert result_box[0] is True
    ctrl.shutdown()


def test_controller_handle_confirmation_denied(controller_setup):
    ctrl, state, _, _ = controller_setup

    result_box = []

    def confirm_worker():
        ans = ctrl.handle_confirmation("dangerous_tool", {}, "critical", "Warning")
        result_box.append(ans)

    t = threading.Thread(target=confirm_worker)
    t.start()

    for _ in range(20):
        if state.pending_confirmation is not None:
            break
        time.sleep(0.05)

    assert state.pending_confirmation is not None
    state.pending_confirmation.deny()
    t.join(timeout=1.0)

    assert len(result_box) == 1
    assert result_box[0] is False
    ctrl.shutdown()


def test_controller_get_memories(controller_setup):
    ctrl, _, _, _ = controller_setup
    mems = ctrl.get_memories()
    assert isinstance(mems, list)
    assert len(mems) == 1
    assert mems[0]["key"] == "test_user"
    ctrl.shutdown()


def test_controller_get_system_status(controller_setup):
    ctrl, _, _, _ = controller_setup
    status = ctrl.get_system_status()
    assert "version" in status
    assert status["tool_count"] == 68
    ctrl.shutdown()


def test_controller_task_lifecycle(controller_setup):
    ctrl, state, _, _ = controller_setup

    mock_task = MagicMock()
    mock_task.task_id = "task-mock-123"
    mock_task.goal = "Open Chrome and check news"
    mock_task.status.value = "completed"
    mock_task.steps = []
    mock_task.to_dict.return_value = {
        "task_id": "task-mock-123",
        "goal": "Open Chrome and check news",
        "status": "ready",
        "steps": [],
        "steps_count": 0,
        "current_step": 0,
    }

    with patch("gui.controller.get_task_planner") as mock_planner_factory, \
         patch("gui.controller.get_task_executor") as mock_exec_factory:
        mock_planner = MagicMock()
        mock_planner.plan.return_value = mock_task
        mock_planner_factory.return_value = mock_planner

        mock_executor = MagicMock()
        mock_executor.run_task.return_value = mock_task
        mock_exec_factory.return_value = mock_executor

        # Test load tasks
        ctrl.load_tasks()
        time.sleep(0.1)

        # Test create task
        ctrl.create_task("Open Chrome and check news")
        time.sleep(0.3)

        assert state.active_task is not None
        assert "Open Chrome" in state.active_task.goal

        # Test run, pause, resume, cancel
        ctrl.run_active_task()
        time.sleep(0.1)

        ctrl.pause_active_task()
        time.sleep(0.1)

        ctrl.resume_active_task()
        time.sleep(0.1)

        ctrl.cancel_active_task()
        time.sleep(0.1)

    ctrl.shutdown()
