"""
Unit tests for CHARVIS GUIState (Phase 15).
"""

import pytest
from gui.state import GUIState
from gui.models import AppView, SystemState, ChatMessage, TaskDisplayItem, ConfirmationRequest


def test_state_defaults():
    state = GUIState()
    assert state.system_state == SystemState.IDLE
    assert state.current_view == AppView.CHAT
    assert state.messages == []
    assert state.active_task is None
    assert state.tasks == []
    assert state.task_logs == []
    assert state.pending_confirmation is None
    assert state.is_busy is False


def test_state_set_system_state_and_subscription():
    state = GUIState()
    notified = []

    def listener(s):
        notified.append(s.system_state)

    state.subscribe(listener)
    state.set_system_state(SystemState.THINKING, "Processing query...")

    assert state.system_state == SystemState.THINKING
    assert state.status_message == "Processing query..."
    assert state.is_busy is True
    assert len(notified) == 1
    assert notified[0] == SystemState.THINKING


def test_state_unsubscribe():
    state = GUIState()
    notified = []

    def listener(s):
        notified.append(s.system_state)

    unsub = state.subscribe(listener)
    state.set_system_state(SystemState.LISTENING)
    assert len(notified) == 1

    unsub()
    state.set_system_state(SystemState.IDLE)
    assert len(notified) == 1  # No second notification


def test_state_messages():
    state = GUIState()
    msg = state.add_message("user", "Hello there")
    assert len(state.messages) == 1
    assert state.messages[0].role == "user"
    assert state.messages[0].content == "Hello there"

    state.clear_messages()
    assert len(state.messages) == 0


def test_state_tasks_and_logs():
    state = GUIState()
    task = TaskDisplayItem(task_id="t1", goal="Goal 1", status="pending")
    state.set_tasks([task])
    assert len(state.tasks) == 1

    state.set_active_task(task)
    assert state.active_task.task_id == "t1"

    state.append_task_log("Step 1 started")
    state.append_task_log("Step 1 completed")
    assert len(state.task_logs) == 2
    assert "Step 1 started" in state.task_logs[0]

    state.clear_task_logs()
    assert len(state.task_logs) == 0


def test_state_confirmation_lifecycle():
    state = GUIState()
    req = ConfirmationRequest(
        tool_name="delete_file",
        arguments={"path": "test.txt"},
        risk_level="high",
    )

    state.request_confirmation(req)
    assert state.pending_confirmation == req
    assert state.system_state == SystemState.WAITING_CONFIRMATION

    state.clear_confirmation()
    assert state.pending_confirmation is None
    assert state.system_state == SystemState.IDLE
