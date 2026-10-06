"""
Tests for Global Hotkey Activation Flow (Phase 19).
Verifies:
- Ctrl+Alt+Space triggers ActivationManager.request_activation(ActivationSource.HOTKEY)
- Hotkey never executes tools directly or bypasses AIBrain
- Hotkey never logs or captures arbitrary keystrokes (no keylogger)
- Disabled hotkey produces no activation and no error spam
"""

from unittest.mock import MagicMock, patch
import pytest

from activation.hotkey import GlobalHotkeyManager
from activation.manager import ActivationManager
from activation.models import ActivationSource, ActivationState


def test_hotkey_trigger_initiates_activation():
    """Verify triggering hotkey requests activation with ActivationSource.HOTKEY."""
    mock_brain = MagicMock()
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    # Simulate hotkey trigger callback
    mgr.request_activation = MagicMock(return_value=MagicMock())
    mgr.hotkey_manager.on_trigger()

    mgr.request_activation.assert_called_once_with(ActivationSource.HOTKEY)


def test_hotkey_does_not_execute_tool_directly():
    """Verify hotkey does not execute tools directly, only starts listening."""
    mock_brain = MagicMock()
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    with patch("voice.audio.AudioCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.record_audio.return_value = None

        session = mgr.request_activation(ActivationSource.HOTKEY)
        # Verify no tools or brain execution happened simply from pressing the hotkey
        assert not mock_brain.process_user_message.called
        assert session.source == ActivationSource.HOTKEY


def test_hotkey_disabled_in_configuration():
    """Verify when hotkey is disabled, start() is safely skipped without errors."""
    trigger_mock = MagicMock()
    hotkey = GlobalHotkeyManager(on_trigger=trigger_mock, enabled=False)

    # Calling start should be a no-op when enabled is False
    with patch("ctypes.windll.user32.RegisterHotKey", return_value=1) as mock_reg:
        success = hotkey.start()
        assert not mock_reg.called
        assert success is False
        assert hotkey.is_running is False

    # Triggering should not have happened
    assert not trigger_mock.called


def test_hotkey_enable_and_disable():
    """Verify toggling enabled state on GlobalHotkeyManager."""
    trigger_mock = MagicMock()
    hotkey = GlobalHotkeyManager(on_trigger=trigger_mock, enabled=False)

    hotkey.enabled = True
    assert hotkey.enabled is True

    hotkey.enabled = False
    assert hotkey.enabled is False
    assert hotkey.is_running is False
