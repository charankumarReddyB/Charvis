"""
Unit tests for Desktop GUI and System Tray Integration (Phase 18).
Ensures closing the GUI window minimizes/hides to tray without terminating the runtime,
re-opening from tray restores GUI, and explicit Exit terminates the application cleanly.
"""

import tkinter as tk
from unittest.mock import MagicMock
import pytest

from gui.app import CharvisApp
from gui.tray import SystemTrayManager


@pytest.fixture(scope="module")
def root_window():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_gui_window_close_minimizes_to_tray(root_window):
    """Verify on_close withdraws window instead of destroying it when tray is attached."""
    mock_tray = MagicMock(spec=SystemTrayManager)
    app = CharvisApp(root=root_window, tray_manager=mock_tray, minimize_to_tray=True)

    with MagicMock() as mock_withdraw:
        root_window.withdraw = mock_withdraw
        app.on_close()
        mock_withdraw.assert_called_once()


def test_gui_restore_from_tray(root_window):
    """Verify show() un-minimizes and focuses the window."""
    mock_tray = MagicMock(spec=SystemTrayManager)
    app = CharvisApp(root=root_window, tray_manager=mock_tray, minimize_to_tray=True)

    with MagicMock() as mock_deiconify, MagicMock() as mock_lift:
        root_window.deiconify = mock_deiconify
        root_window.lift = mock_lift
        app.show()
        mock_deiconify.assert_called_once()
        mock_lift.assert_called_once()


def test_explicit_exit_app_shuts_down_cleanly(root_window):
    """Verify exit_app() stops tray and shuts down controller."""
    mock_tray = MagicMock(spec=SystemTrayManager)
    app = CharvisApp(root=root_window, tray_manager=mock_tray, minimize_to_tray=True)

    app.controller = MagicMock()
    app.exit_app()

    mock_tray.stop.assert_called_once()
    app.controller.shutdown.assert_called_once()
