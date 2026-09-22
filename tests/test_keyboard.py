"""
Unit tests for CHARVIS Keyboard Controller, Key Normalization, and Keyboard Tools.
All tests use mocking to prevent any physical typing or keystrokes during test execution.
"""

from unittest.mock import MagicMock, patch
import pytest
import pyautogui

from computer.keyboard import (
    BLOCKED_HOTKEYS,
    ComputerSafetyError,
    FailSafeTriggeredError,
    KeyboardController,
    is_high_risk_hotkey,
    normalize_key,
    parse_hotkey_sequence,
)
from core.safety import RiskLevel
from tools.keyboard import HotkeyTool, PressKeyTool, TypeTextTool


def test_normalize_key_valid():
    """Verify common variations and case differences resolve to canonical PyAutoGUI keys."""
    assert normalize_key("Enter") == "enter"
    assert normalize_key("RETURN") == "enter"
    assert normalize_key("enter") == "enter"
    assert normalize_key("Esc") == "escape"
    assert normalize_key("ESCAPE") == "escape"
    assert normalize_key("back") == "backspace"
    assert normalize_key("del") == "delete"
    assert normalize_key("spacebar") == "space"
    assert normalize_key("pgup") == "pageup"
    assert normalize_key("pgdn") == "pagedown"
    assert normalize_key("win") == "winleft"
    assert normalize_key("windows") == "winleft"
    assert normalize_key("ctrl") == "ctrl"
    assert normalize_key("control") == "ctrl"
    assert normalize_key("Alt") == "alt"
    assert normalize_key("Shift") == "shift"
    assert normalize_key("F5") == "f5"
    assert normalize_key("F12") == "f12"
    assert normalize_key("A") == "a"
    assert normalize_key("z") == "z"
    assert normalize_key("5") == "5"


def test_normalize_key_invalid():
    """Verify invalid or arbitrary key names raise ValueError."""
    with pytest.raises(ValueError, match="Unrecognized or invalid keyboard key"):
        normalize_key("unknown_key_xyz")

    with pytest.raises(ValueError, match="Unrecognized or invalid keyboard key"):
        normalize_key("malicious_code()")

    with pytest.raises(ValueError, match="cannot be empty"):
        normalize_key("")

    with pytest.raises(ValueError, match="Key must be a string"):
        normalize_key(123)  # type: ignore


def test_parse_hotkey_sequence_valid():
    """Verify string and list hotkey combinations are parsed and normalized."""
    assert parse_hotkey_sequence("ctrl+c") == ["ctrl", "c"]
    assert parse_hotkey_sequence("Ctrl+Shift+S") == ["ctrl", "shift", "s"]
    assert parse_hotkey_sequence(["alt", "tab"]) == ["alt", "tab"]
    assert parse_hotkey_sequence("Win+D") == ["winleft", "d"]


def test_parse_hotkey_sequence_blocked():
    """Verify security attention sequences like Ctrl+Alt+Del are strictly blocked."""
    with pytest.raises(ComputerSafetyError, match="strictly prohibited by CHARVIS safety policy"):
        parse_hotkey_sequence("ctrl+alt+del")

    with pytest.raises(ComputerSafetyError, match="strictly prohibited by CHARVIS safety policy"):
        parse_hotkey_sequence(["ctrl", "alt", "delete"])


def test_is_high_risk_hotkey():
    """Verify destructive/locking shortcuts are identified as high-risk."""
    assert is_high_risk_hotkey(["alt", "f4"]) is True
    assert is_high_risk_hotkey(["winleft", "l"]) is True
    assert is_high_risk_hotkey(["ctrl", "c"]) is False
    assert is_high_risk_hotkey(["ctrl", "v"]) is False


def test_keyboard_controller_type_text():
    """Verify KeyboardController.type_text invokes pyautogui.write."""
    controller = KeyboardController(failsafe=True, max_type_length=500)

    with patch("pyautogui.write") as mock_write:
        res = controller.type_text("Hello CHARVIS")
        assert res["success"] is True
        assert res["typed_length"] == 13
        mock_write.assert_called_once_with("Hello CHARVIS", interval=0.01)


def test_keyboard_controller_type_text_validation():
    """Verify input validation rules for type_text."""
    controller = KeyboardController(failsafe=True, max_type_length=100)

    # Empty text
    with pytest.raises(ValueError, match="text cannot be empty"):
        controller.type_text("")

    # Non-string text
    with pytest.raises(ValueError, match="text must be a string"):
        controller.type_text(12345)  # type: ignore

    # Excessively long text
    long_text = "A" * 101
    with pytest.raises(ValueError, match="exceeds maximum allowed limit"):
        controller.type_text(long_text)


def test_keyboard_controller_press_key():
    """Verify KeyboardController.press_key normalizes and presses key."""
    controller = KeyboardController()

    with patch("pyautogui.press") as mock_press:
        res = controller.press_key("Return", presses=2)
        assert res["success"] is True
        assert res["key"] == "enter"
        assert res["presses"] == 2
        mock_press.assert_called_once_with("enter", presses=2, interval=0.05)


def test_keyboard_controller_press_key_invalid_presses():
    """Verify repetition limits on press_key."""
    controller = KeyboardController()

    with pytest.raises(ValueError, match="presses must be an integer between 1 and 10"):
        controller.press_key("enter", presses=0)

    with pytest.raises(ValueError, match="presses must be an integer between 1 and 10"):
        controller.press_key("enter", presses=11)


def test_keyboard_controller_hotkey():
    """Verify KeyboardController.hotkey executes normalized hotkey."""
    controller = KeyboardController()

    with patch("pyautogui.hotkey") as mock_hotkey:
        res = controller.hotkey("ctrl+v")
        assert res["success"] is True
        assert res["hotkey"] == "ctrl+v"
        mock_hotkey.assert_called_once_with("ctrl", "v")


def test_keyboard_failsafe_handling():
    """Verify PyAutoGUI FailSafeException is caught and mapped to FailSafeTriggeredError."""
    controller = KeyboardController()

    with patch("pyautogui.write", side_effect=pyautogui.FailSafeException()):
        with pytest.raises(FailSafeTriggeredError, match="Emergency stop triggered"):
            controller.type_text("Test failsafe")

    with patch("pyautogui.press", side_effect=pyautogui.FailSafeException()):
        with pytest.raises(FailSafeTriggeredError, match="Emergency stop triggered"):
            controller.press_key("enter")

    with patch("pyautogui.hotkey", side_effect=pyautogui.FailSafeException()):
        with pytest.raises(FailSafeTriggeredError, match="Emergency stop triggered"):
            controller.hotkey("ctrl+c")


def test_type_text_tool_metadata_and_execution():
    """Verify TypeTextTool schema, confirmation prompt, and execution."""
    mock_controller = MagicMock(spec=KeyboardController)
    mock_controller.type_text.return_value = {"success": True, "typed_length": 5, "message": "Typed 5 characters"}

    tool = TypeTextTool(controller=mock_controller)
    assert tool.name == "type_text"
    assert tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED

    # Confirmation prompt preview
    notice = tool.get_confirmation_message({"text": "Hello World"})
    assert "Will type 11 character(s)" in notice
    assert "'Hello World'" in notice

    # Execution
    result = tool.execute(text="Hello")
    assert result["success"] is True
    mock_controller.type_text.assert_called_once_with("Hello")


def test_type_text_tool_failsafe_emergency_stop():
    """Verify TypeTextTool returns controlled error dict when fail-safe triggers."""
    mock_controller = MagicMock(spec=KeyboardController)
    mock_controller.type_text.side_effect = FailSafeTriggeredError("Emergency corner reached")

    tool = TypeTextTool(controller=mock_controller)
    res = tool.execute(text="test")
    assert res["success"] is False
    assert res["error"] == "emergency_stop"
    assert "Emergency corner reached" in res["message"]


def test_press_key_tool_metadata_and_execution():
    """Verify PressKeyTool schema and execution."""
    mock_controller = MagicMock(spec=KeyboardController)
    mock_controller.press_key.return_value = {"success": True, "key": "tab", "presses": 1}

    tool = PressKeyTool(controller=mock_controller)
    assert tool.name == "press_key"
    assert tool.risk_level == RiskLevel.SAFE

    res = tool.execute(key="Tab")
    assert res["success"] is True
    mock_controller.press_key.assert_called_once_with(key="Tab", presses=1)


def test_hotkey_tool_metadata_and_safety_rejection():
    """Verify HotkeyTool confirmation message, risk level, and policy blocking."""
    mock_controller = MagicMock(spec=KeyboardController)
    tool = HotkeyTool(controller=mock_controller)

    assert tool.name == "hotkey"
    assert tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED

    # High-risk notice
    notice_f4 = tool.get_confirmation_message({"key_combination": "alt+f4"})
    assert "HIGH RISK SHORTCUT" in notice_f4

    # Standard notice
    notice_copy = tool.get_confirmation_message({"key_combination": "ctrl+c"})
    assert "Will execute keyboard shortcut: 'ctrl+c'" in notice_copy

    # Prohibited shortcut blocked at execution
    mock_controller.hotkey.side_effect = ComputerSafetyError("Shortcut prohibited")
    res = tool.execute(key_combination="ctrl+alt+del")
    assert res["success"] is False
    assert res["error"] == "blocked_by_safety_policy"
    assert "Shortcut prohibited" in res["message"]
