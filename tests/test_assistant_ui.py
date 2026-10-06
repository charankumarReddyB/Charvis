"""
Tests for Assistant UI surface (Phase 19).
Verifies:
- Assistant view initializes and reflects GUIState/SystemState
- Visual states: READY, LISTENING, PROCESSING, SPEAKING, PAUSED, ERROR, OFFLINE
- Main action button transitions dynamically
- Multi-step planner / task progress display
- Compact mode toggling
"""

import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest

from activation.models import ActivationSession, ActivationSource, ActivationState
from gui.controller import GUIController
from gui.models import AppView, ChatMessage, SystemState, TaskDisplayItem
from gui.state import GUIState
from gui.widgets.assistant import AssistantViewWidget, redact_display_text


@pytest.fixture
def tk_root():
    """Headless or hidden Tkinter root for widget unit testing."""
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def mock_controller():
    controller = MagicMock(spec=GUIController)
    controller.state = GUIState()
    controller.activation_manager = MagicMock()
    controller.activation_manager.current_state = ActivationState.INACTIVE
    controller.activation_manager.wake_word_engine = None
    return controller


def test_assistant_ui_initial_ready_state(tk_root, mock_controller):
    """Verify Assistant UI initializes in READY state with proper visual labels."""
    state = GUIState()
    widget = AssistantViewWidget(tk_root, state=state, controller=mock_controller)

    assert widget.status_title_label.cget("text") == "Ready"
    assert widget.status_sub_label.cget("text") == "How can I help you?"
    assert widget.action_btn.cget("text") == "🎤 Activate"
    widget.destroy()


def test_assistant_ui_activate_button_click(tk_root, mock_controller):
    """Clicking Activate button requests activation via controller with GUI source."""
    state = GUIState()
    widget = AssistantViewWidget(tk_root, state=state, controller=mock_controller)

    widget.action_btn.invoke()
    mock_controller.request_activation.assert_called_once_with(ActivationSource.GUI)
    widget.destroy()


def test_assistant_ui_listening_state_display(tk_root, mock_controller):
    """When state transitions to listening, UI displays Listening status and Stop button."""
    state = GUIState()
    widget = AssistantViewWidget(tk_root, state=state, controller=mock_controller)

    state.set_listening(True)
    assert widget.status_title_label.cget("text") == "Listening..."
    assert widget.status_sub_label.cget("text") == "I'm listening"
    assert widget.action_btn.cget("text") == "⏹ Stop Listening"

    # Clicking while listening invokes cancellation
    widget.action_btn.invoke()
    mock_controller.cancel_activation.assert_called_once()
    widget.destroy()


def test_assistant_ui_thinking_and_speaking_states(tk_root, mock_controller):
    """Verify PROCESSING and SPEAKING states update visual cards appropriately."""
    state = GUIState()
    widget = AssistantViewWidget(tk_root, state=state, controller=mock_controller)

    # Thinking state
    state.set_processing(True)
    assert widget.status_title_label.cget("text") == "Thinking..."
    assert "Processing" in widget.status_sub_label.cget("text")

    # Speaking state
    state.set_processing(False)
    state.set_system_state(SystemState.SPEAKING)
    assert widget.status_title_label.cget("text") == "Speaking..."
    assert widget.action_btn.cget("text") == "⏹ Stop Speaking"

    widget.destroy()


def test_assistant_ui_paused_error_and_offline_states(tk_root, mock_controller):
    """Verify PAUSED, ERROR, and OFFLINE states."""
    state = GUIState()
    widget = AssistantViewWidget(tk_root, state=state, controller=mock_controller)

    state.set_system_state(SystemState.PAUSED)
    assert widget.status_title_label.cget("text") == "Paused"

    state.set_system_state(SystemState.ERROR)
    assert widget.status_title_label.cget("text") == "Error"

    state.set_system_state(SystemState.OFFLINE)
    assert widget.status_title_label.cget("text") == "Offline"
    assert widget.status_sub_label.cget("text") == "Runtime unavailable"

    widget.destroy()


def test_assistant_ui_task_planner_progress_display(tk_root, mock_controller):
    """Verify active multi-step task displays progress steps in assistant view."""
    state = GUIState()
    widget = AssistantViewWidget(tk_root, state=state, controller=mock_controller)

    task_item = TaskDisplayItem(
        task_id="task-123",
        goal="Organize project files",
        status="running",
        current_step=2,
        completed_steps=1,
        total_steps=4,
        steps=[
            {"description": "Read directory", "status": "completed"},
            {"description": "Move files", "status": "executing"},
            {"description": "Create archive", "status": "pending"},
            {"description": "Cleanup", "status": "pending"},
        ],
    )
    state.set_active_task(task_item)

    assert bool(widget.task_card.winfo_manager())
    assert "Organize project files" in widget.task_goal_lbl.cget("text")
    assert "Step 2 of 4" in widget.task_progress_lbl.cget("text")

    # When active task is cleared, card hides
    state.set_active_task(None)
    assert not bool(widget.task_card.winfo_manager())
    widget.destroy()


def test_assistant_ui_command_and_response_redaction(tk_root, mock_controller):
    """Verify command and response strings have sensitive credentials redacted in UI."""
    state = GUIState()
    widget = AssistantViewWidget(tk_root, state=state, controller=mock_controller)

    widget.set_command_display("My password is password=SuperSecret123! and token is sk-123456789012345678901234")
    widget.set_response_display("Your auth token is Bearer abcdef1234567890")

    assert "SuperSecret123!" not in widget.command_lbl.cget("text")
    assert "sk-1234567890" not in widget.command_lbl.cget("text")
    assert "abcdef1234567890" not in widget.response_lbl.cget("text")
    widget.destroy()


def test_assistant_ui_toggle_compact_mode_callback(tk_root, mock_controller):
    """Clicking compact button calls the on_toggle_compact callback."""
    compact_mock = MagicMock()
    state = GUIState()
    widget = AssistantViewWidget(
        tk_root,
        state=state,
        controller=mock_controller,
        on_toggle_compact=compact_mock,
    )

    assert hasattr(widget, "compact_btn")
    widget.compact_btn.invoke()
    compact_mock.assert_called_once()
    widget.destroy()
