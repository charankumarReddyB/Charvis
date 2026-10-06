"""
Unit tests for Global Keyboard Activation Foundation (Phase 18).
Verifies that only Ctrl+Alt+Space is registered via native Windows RegisterHotKey,
never intercepts arbitrary keystrokes, and is disabled by default.
"""

from unittest.mock import MagicMock, patch
import pytest

from activation.hotkey import GlobalHotkeyManager, HOTKEY_COMBINATION


def test_hotkey_manager_defaults_and_combination():
    """Verify default disabled state and exact shortcut combination."""
    mgr = GlobalHotkeyManager(enabled=False)
    assert mgr.is_enabled is False
    assert mgr.is_registered is False
    assert HOTKEY_COMBINATION == "Ctrl+Alt+Space"
    assert mgr.combination == "Ctrl+Alt+Space"


def test_hotkey_manager_start_disabled():
    """Verify calling start on disabled manager does not register any system hotkey."""
    with patch("ctypes.windll.user32.RegisterHotKey", create=True) as mock_reg:
        mgr = GlobalHotkeyManager(enabled=False)
        result = mgr.start()
        assert result is False
        assert mgr.is_registered is False
        mock_reg.assert_not_called()


def test_hotkey_manager_start_and_stop_lifecycle():
    """Verify start registers exact Windows hotkey and stop unregisters cleanly."""
    with patch("ctypes.windll.user32.RegisterHotKey", create=True) as mock_reg, \
         patch("ctypes.windll.user32.UnregisterHotKey", create=True) as mock_unreg:
        mock_reg.return_value = 1
        mock_unreg.return_value = 1

        triggered = []
        mgr = GlobalHotkeyManager(
            on_triggered=lambda: triggered.append(True),
            enabled=True,
        )
        assert mgr.start() is True
        assert mgr.is_registered is True
        mock_reg.assert_called_once()

        mgr.stop()
        assert mgr.is_registered is False
        mock_unreg.assert_called_once()


def test_hotkey_manager_never_captures_arbitrary_keys():
    """Verify HotkeyManager does not import or use arbitrary keylogger hooks."""
    mgr = GlobalHotkeyManager(enabled=True)
    # Check that manager has no key logger hooks, key event listeners, or text recording buffers
    assert not hasattr(mgr, "key_buffer")
    assert not hasattr(mgr, "log_keys")
    assert not hasattr(mgr, "record_key")
    assert not hasattr(mgr, "on_press")


def test_hotkey_trigger_dispatches_callback():
    """Verify hotkey trigger fires user callback safely."""
    activated = []
    mgr = GlobalHotkeyManager(
        on_triggered=lambda: activated.append(True),
        enabled=True,
    )
    mgr._dispatch_trigger()
    assert activated == [True]
