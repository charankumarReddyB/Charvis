"""
Unit tests for System Tray Integration (Phase 18).
Tests tray lifecycle, menu generation, status reflection, and action dispatch.
"""

from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from activation.manager import ActivationManager
from activation.models import ActivationSession, ActivationSource, ActivationState
from gui.tray import SystemTrayManager, TrayStatus, create_tray_icon_image
from runtime.client import RuntimeClient
from runtime.controller import RuntimeController


def test_create_tray_icon_image():
    """Verify tray icon generator creates valid distinct RGBA images for all states."""
    for status in TrayStatus:
        img = create_tray_icon_image(status, size=32)
        assert isinstance(img, Image.Image)
        assert img.size == (32, 32)
        assert img.mode == "RGBA"


def test_system_tray_manager_initialization():
    """Verify initial properties and default status."""
    tray = SystemTrayManager()
    assert tray.current_status == TrayStatus.READY
    assert tray._icon is None
    assert tray._can_pause() is True
    assert tray._can_resume() is False


def test_tray_status_update_and_tooltip():
    """Verify set_status updates internal state and icon properties."""
    mock_icon = MagicMock()
    tray = SystemTrayManager()
    tray._icon = mock_icon

    tray.set_status(TrayStatus.LISTENING, "Listening for speech...")
    assert tray.current_status == TrayStatus.LISTENING
    assert "Listening for speech..." in mock_icon.title
    assert "CHARVIS" in mock_icon.title
    assert mock_icon.icon is not None

    tray.set_status(TrayStatus.PAUSED)
    assert tray.current_status == TrayStatus.PAUSED
    assert tray._can_pause() is False
    assert tray._can_resume() is True


def test_tray_menu_structure():
    """Verify tray menu contains the required 8 menu items."""
    tray = SystemTrayManager()
    menu = tray._build_menu()
    items = list(menu.items)

    item_texts = [getattr(it, "text", "") for it in items]
    assert "Open CHARVIS" in item_texts
    assert "Voice Mode" in item_texts
    assert "Wake Word" in item_texts
    assert "Pause CHARVIS" in item_texts
    assert "Resume CHARVIS" in item_texts
    assert "Runtime Status" in item_texts
    assert "Settings / Diagnosis" in item_texts
    assert "Exit CHARVIS" in item_texts


def test_tray_action_open_gui():
    """Verify Open CHARVIS invokes registered callback."""
    open_called = []
    tray = SystemTrayManager(on_open_gui=lambda: open_called.append(True))
    tray._action_open_gui()
    assert open_called == [True]


def test_tray_action_pause_and_resume():
    """Verify Pause and Resume trigger IPC requests and status change."""
    mock_client = MagicMock(spec=RuntimeClient)
    tray = SystemTrayManager(runtime_client=mock_client)

    tray._action_pause()
    mock_client.send_request.assert_called_with("pause")
    assert tray.current_status == TrayStatus.PAUSED

    tray._action_resume()
    mock_client.send_request.assert_called_with("resume")
    assert tray.current_status == TrayStatus.READY


def test_tray_action_exit():
    """Verify Exit CHARVIS requests runtime shutdown and triggers exit callback."""
    mock_client = MagicMock(spec=RuntimeClient)
    exit_called = []
    tray = SystemTrayManager(
        runtime_client=mock_client,
        on_exit=lambda: exit_called.append(True),
    )

    tray._action_exit()
    mock_client.send_request.assert_called_with("shutdown")
    assert exit_called == [True]
    assert tray._icon is None


def test_tray_reflects_activation_state_changes():
    """Verify tray automatically transitions visual status upon activation events."""
    mock_activation = MagicMock(spec=ActivationManager)
    listeners = []
    mock_activation.add_listener.side_effect = lambda fn: listeners.append(fn)

    tray = SystemTrayManager(activation_manager=mock_activation)
    assert len(listeners) == 1
    on_change = listeners[0]

    session = ActivationSession(
        session_id="test-1",
        source=ActivationSource.VOICE_BUTTON,
        state=ActivationState.LISTENING,
    )
    on_change(session)
    assert tray.current_status == TrayStatus.LISTENING

    session.transition_to(ActivationState.PROCESSING)
    on_change(session)
    assert tray.current_status == TrayStatus.PROCESSING

    session.transition_to(ActivationState.COMPLETED)
    on_change(session)
    assert tray.current_status == TrayStatus.READY

    err_session = ActivationSession(
        session_id="test-err",
        source=ActivationSource.VOICE_BUTTON,
        state=ActivationState.ERROR,
        error_message="Microphone busy",
    )
    on_change(err_session)
    assert tray.current_status == TrayStatus.ERROR


@patch("pystray.Icon")
def test_tray_start_and_stop_lifecycle(mock_pystray_icon_cls):
    """Verify tray start and stop lifecycle runs thread and cleans up."""
    mock_icon_instance = MagicMock()
    mock_pystray_icon_cls.return_value = mock_icon_instance

    tray = SystemTrayManager()
    tray.start()
    assert tray._icon is not None
    assert tray._thread is not None

    tray.stop()
    assert tray._icon is None
    mock_icon_instance.stop.assert_called()
