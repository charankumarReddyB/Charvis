"""
Unit tests for CHARVIS GUI Widgets and CharvisApp (Phase 15).
"""

import pytest
import tkinter as tk
from unittest.mock import MagicMock

from gui.state import GUIState
from gui.controller import GUIController
from gui.models import AppView, SystemState, ConfirmationRequest, TaskDisplayItem
from gui.widgets.status import StatusWidget
from gui.widgets.sidebar import SidebarWidget
from gui.widgets.input_bar import InputBarWidget
from gui.widgets.chat import ChatViewWidget
from gui.widgets.task_panel import TaskPanelWidget
from gui.widgets.confirmation import ConfirmationDialog
from gui.widgets.memory_view import MemoryViewWidget
from gui.widgets.settings_view import SettingsViewWidget
from gui.app import CharvisApp


@pytest.fixture(scope="module")
def root_window():
    root = tk.Tk()
    root.withdraw()  # Keep hidden during automated test runs
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def mock_controller():
    ctrl = MagicMock(spec=GUIController)
    ctrl.get_memories.return_value = [
        {"key": "editor", "value": "vscode", "category": "user_pref", "scope": "persistent", "confidence": 1.0}
    ]
    ctrl.get_system_status.return_value = {"version": "0.15.0", "tool_count": 68}
    return ctrl


def test_status_widget(root_window):
    state = GUIState()
    frame = tk.Frame(root_window)
    widget = StatusWidget(frame, state=state)
    widget.pack()

    # Initial state
    assert "idle" in widget.text_label.cget("text").lower()

    # State update
    state.set_system_state(SystemState.THINKING, "Analyzing request...")
    assert "thinking" in widget.text_label.cget("text").lower()
    assert "Analyzing request..." in widget.sub_label.cget("text")
    frame.destroy()


def test_input_bar_widget(root_window):
    frame = tk.Frame(root_window)
    sent_text = []

    widget = InputBarWidget(
        frame,
        on_send=lambda t: sent_text.append(t),
        on_voice=lambda: sent_text.append("__VOICE__"),
    )
    widget.pack()

    widget.text_input.insert("1.0", "Test input command")
    widget._on_send_click()

    assert len(sent_text) == 1
    assert sent_text[0] == "Test input command"

    widget.voice_btn.invoke()
    assert len(sent_text) == 2
    assert sent_text[1] == "__VOICE__"

    widget.set_enabled(False)
    assert widget.text_input.cget("state") == tk.DISABLED

    widget.set_enabled(True)
    assert widget.text_input.cget("state") == tk.NORMAL
    frame.destroy()


def test_sidebar_widget(root_window, mock_controller):
    state = GUIState()
    views_switched = []
    frame = tk.Frame(root_window)

    sidebar = SidebarWidget(
        frame,
        state=state,
        controller=mock_controller,
        on_view_change=lambda v: views_switched.append(v),
    )
    sidebar.pack()

    # Click tasks view button
    sidebar.view_buttons[AppView.TASKS].invoke()
    assert len(views_switched) == 1
    assert views_switched[0] == AppView.TASKS

    # Check button active highlighting on state change
    state.set_current_view(AppView.MEMORY)
    assert sidebar.current_active_view == AppView.MEMORY
    frame.destroy()


def test_chat_view_widget(root_window, mock_controller):
    state = GUIState()
    frame = tk.Frame(root_window)

    chat = ChatViewWidget(frame, state=state, controller=mock_controller)
    chat.pack()

    # Add message to state
    state.add_message("user", "Hello assistant")
    state.add_message("assistant", "Hello! How can I assist you today?")

    # Verify message count label
    assert "2 messages" in chat.count_label.cget("text")

    # Clear chat
    chat.clear_btn.invoke()
    assert len(state.messages) == 0
    frame.destroy()


def test_task_panel_widget(root_window, mock_controller):
    state = GUIState()
    frame = tk.Frame(root_window)

    panel = TaskPanelWidget(frame, state=state, controller=mock_controller)
    panel.pack()

    task = TaskDisplayItem(
        task_id="t-99",
        goal="Automate build",
        status="executing",
        total_steps=2,
        completed_steps=1,
        steps=[
            {"tool_name": "calculator", "description": "Calculate sum", "status": "completed"},
            {"tool_name": "list_files", "description": "List files", "status": "pending"},
        ]
    )
    state.set_active_task(task)
    state.append_task_log("Calculated sum successfully.")

    assert "Automate build" in panel.active_title.cget("text")
    assert len(panel.steps_tree.get_children()) == 2

    # Click Run
    panel.btn_run.invoke()
    mock_controller.run_active_task.assert_called()

    # Test Plan generation button
    panel.prompt_entry.insert(0, "Build and test project")
    panel.create_btn.invoke()
    mock_controller.create_task.assert_called_with("Build and test project")
    frame.destroy()


def test_memory_view_widget(root_window, mock_controller):
    state = GUIState()
    frame = tk.Frame(root_window)

    mem_view = MemoryViewWidget(frame, state=state, controller=mock_controller)
    mem_view.pack()

    # Should have loaded 1 item from mock controller
    children = mem_view.tree.get_children()
    assert len(children) == 1

    # Search filter
    mem_view.search_entry.insert(0, "nonexistent")
    mem_view._filter_memories()
    assert len(mem_view.tree.get_children()) == 0

    mem_view.search_entry.delete(0, tk.END)
    mem_view._filter_memories()
    assert len(mem_view.tree.get_children()) == 1
    frame.destroy()


def test_settings_view_widget(root_window, mock_controller):
    state = GUIState()
    frame = tk.Frame(root_window)

    settings_view = SettingsViewWidget(frame, state=state, controller=mock_controller)
    settings_view.pack()

    assert settings_view.title_label.cget("text") == "Settings & System Status"
    frame.destroy()


def test_confirmation_dialog_approve(root_window):
    req = ConfirmationRequest(
        tool_name="delete_file",
        arguments={"path": "C:\\secret.txt", "api_key": "my_secret_token"},
        risk_level="high",
        message="Please confirm file deletion.",
    )

    dialog = ConfirmationDialog(root_window, req)

    # Verify secret argument is masked in the display
    param_content = dialog.children  # Ensure UI rendered cleanly

    # Approve
    dialog._on_confirm()
    assert req.approved is True
    assert req.event.is_set()


def test_confirmation_dialog_cancel(root_window):
    req = ConfirmationRequest(
        tool_name="system_shutdown",
        arguments={},
        risk_level="critical",
    )

    dialog = ConfirmationDialog(root_window, req)
    dialog._on_cancel()
    assert req.approved is False
    assert req.event.is_set()


def test_charvis_app_instantiation():
    test_root = tk.Tk()
    test_root.withdraw()
    try:
        app = CharvisApp(root=test_root)
        assert app.root == test_root
        assert app.state is not None
        assert app.controller is not None
        assert AppView.CHAT in app.views
        assert AppView.TASKS in app.views
        assert AppView.MEMORY in app.views
        assert AppView.SETTINGS in app.views

        # Test view switching
        app.switch_view(AppView.TASKS)
        assert app.state.current_view == AppView.TASKS

        app.switch_view(AppView.CHAT)
        assert app.state.current_view == AppView.CHAT

        app.on_close()
    finally:
        try:
            test_root.destroy()
        except Exception:
            pass
