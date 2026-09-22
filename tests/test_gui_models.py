"""
Unit tests for CHARVIS GUI Models (Phase 15).
"""

import threading
import pytest
from gui.models import AppView, SystemState, ChatMessage, TaskDisplayItem, ConfirmationRequest


def test_app_view_values():
    assert AppView.CHAT.value == "chat"
    assert AppView.TASKS.value == "tasks"
    assert AppView.MEMORY.value == "memory"
    assert AppView.SETTINGS.value == "settings"


def test_system_state_values():
    assert SystemState.IDLE.value == "idle"
    assert SystemState.LISTENING.value == "listening"
    assert SystemState.THINKING.value == "thinking"
    assert SystemState.EXECUTING.value == "executing"
    assert SystemState.SPEAKING.value == "speaking"
    assert SystemState.WAITING_CONFIRMATION.value == "waiting_confirmation"
    assert SystemState.ERROR.value == "error"
    assert SystemState.OFFLINE.value == "offline"


def test_system_state_symbol_and_color():
    assert SystemState.IDLE.symbol == "●"
    assert SystemState.IDLE.color.startswith("#")
    assert SystemState.ERROR.symbol == "✕"
    assert SystemState.WAITING_CONFIRMATION.symbol == "⚠️"


def test_chat_message():
    msg = ChatMessage(role="user", content="Hello CHARVIS")
    assert msg.role == "user"
    assert msg.content == "Hello CHARVIS"
    assert msg.timestamp is not None
    assert msg.metadata == {}

    msg2 = ChatMessage(role="tool", content="Result", metadata={"tool_name": "calculator"})
    assert msg2.metadata["tool_name"] == "calculator"


def test_task_display_item():
    task = TaskDisplayItem(
        task_id="task-101",
        goal="Run tests",
        status="running",
        total_steps=5,
        completed_steps=2,
    )
    assert task.task_id == "task-101"
    assert task.goal == "Run tests"
    assert task.status == "running"
    assert task.total_steps == 5
    assert task.completed_steps == 2
    assert task.steps == []


def test_confirmation_request_approve():
    req = ConfirmationRequest(
        tool_name="delete_file",
        arguments={"path": "C:\\test.txt"},
        risk_level="high",
        message="Delete test file",
    )
    assert req.approved is False
    assert not req.event.is_set()

    # Simulate thread approving
    def worker():
        req.event.wait(timeout=2.0)

    t = threading.Thread(target=worker)
    t.start()

    req.approve()
    assert req.approved is True
    assert req.event.is_set()
    t.join(timeout=1.0)
    assert not t.is_alive()


def test_confirmation_request_deny():
    req = ConfirmationRequest(
        tool_name="shell_eval",
        arguments={"cmd": "dir"},
        risk_level="critical",
    )
    assert req.approved is False
    assert not req.event.is_set()

    req.deny()
    assert req.approved is False
    assert req.event.is_set()
