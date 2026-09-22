"""
Unit tests for CHARVIS Mouse Controller and Mouse Tools.
All tests use mocking to prevent physical mouse movement or clicking during test execution.
"""

from unittest.mock import MagicMock, patch
import pytest
import pyautogui

from computer.keyboard import FailSafeTriggeredError
from computer.mouse import MouseController
from core.safety import RiskLevel
from tools.mouse import ClickTool, DoubleClickTool, MoveMouseTool, ScrollTool


def test_mouse_get_screen_size():
    """Verify screen resolution discovery."""
    controller = MouseController()
    with patch("pyautogui.size", return_value=(2560, 1440)):
        size = controller.get_screen_size()
        assert size == (2560, 1440)


def test_move_mouse_valid():
    """Verify valid in-bounds mouse movement."""
    controller = MouseController()
    with patch("pyautogui.size", return_value=(1920, 1080)):
        with patch("pyautogui.moveTo") as mock_move:
            res = controller.move_mouse(500, 300)
            assert res["success"] is True
            assert res["x"] == 500
            assert res["y"] == 300
            mock_move.assert_called_once_with(500, 300, duration=0.2)


def test_move_mouse_boundary_rejection():
    """Verify rejection of out-of-bounds coordinates with descriptive message."""
    controller = MouseController()
    with patch("pyautogui.size", return_value=(1920, 1080)):
        # Negative X
        with pytest.raises(ValueError, match="Coordinates \\(-10, 500\\) are outside the current 1920x1080 screen"):
            controller.move_mouse(-10, 500)

        # Negative Y
        with pytest.raises(ValueError, match="Coordinates \\(500, -20\\) are outside the current 1920x1080 screen"):
            controller.move_mouse(500, -20)

        # X too large
        with pytest.raises(ValueError, match="Coordinates \\(1920, 500\\) are outside the current 1920x1080 screen"):
            controller.move_mouse(1920, 500)

        # Y too large
        with pytest.raises(ValueError, match="Coordinates \\(500, 1080\\) are outside the current 1920x1080 screen"):
            controller.move_mouse(500, 1080)

        # Excessive coordinates
        with pytest.raises(ValueError, match="Coordinates \\(5000, 300\\) are outside the current 1920x1080 screen"):
            controller.move_mouse(5000, 300)


def test_move_mouse_type_validation():
    """Verify non-integer coordinates are rejected."""
    controller = MouseController()
    with pytest.raises(ValueError, match="x coordinate must be an integer"):
        controller.move_mouse("500", 300)  # type: ignore

    with pytest.raises(ValueError, match="y coordinate must be an integer"):
        controller.move_mouse(500, "300")  # type: ignore

    with pytest.raises(ValueError, match="x coordinate must be an integer"):
        controller.move_mouse(True, 300)  # type: ignore


def test_click_valid():
    """Verify valid click button and clicks options."""
    controller = MouseController()
    with patch("pyautogui.click") as mock_click:
        # Default left click
        res = controller.click()
        assert res["success"] is True
        assert res["button"] == "left"
        assert res["clicks"] == 1
        mock_click.assert_called_with(button="left", clicks=1, interval=0.1)

        # Right click
        res_right = controller.click(button="right")
        assert res_right["button"] == "right"
        mock_click.assert_called_with(button="right", clicks=1, interval=0.1)

        # Middle click
        res_mid = controller.click(button="middle")
        assert res_mid["button"] == "middle"


def test_click_validation():
    """Verify invalid button names and click counts are rejected."""
    controller = MouseController()

    with pytest.raises(ValueError, match="Invalid mouse button 'wheel'"):
        controller.click(button="wheel")

    with pytest.raises(ValueError, match="clicks must be 1 or 2"):
        controller.click(clicks=0)

    with pytest.raises(ValueError, match="clicks must be 1 or 2"):
        controller.click(clicks=3)


def test_double_click():
    """Verify double_click invokes click with clicks=2."""
    controller = MouseController()
    with patch("pyautogui.click") as mock_click:
        res = controller.double_click(button="left")
        assert res["success"] is True
        assert res["clicks"] == 2
        mock_click.assert_called_once_with(button="left", clicks=2, interval=0.1)


def test_scroll_valid():
    """Verify mouse scroll with positive and negative amounts."""
    controller = MouseController(max_scroll_amount=100)
    with patch("pyautogui.scroll") as mock_scroll:
        # Scroll up
        res_up = controller.scroll(5)
        assert res_up["success"] is True
        assert res_up["direction"] == "up"
        assert res_up["amount"] == 5
        mock_scroll.assert_called_with(5)

        # Scroll down
        res_down = controller.scroll(-10)
        assert res_down["direction"] == "down"
        assert res_down["amount"] == -10
        mock_scroll.assert_called_with(-10)


def test_scroll_boundary_validation():
    """Verify excessive scroll amounts are blocked."""
    controller = MouseController(max_scroll_amount=100)

    with pytest.raises(ValueError, match="Scroll amount \\(150\\) exceeds maximum allowed range"):
        controller.scroll(150)

    with pytest.raises(ValueError, match="Scroll amount \\(-101\\) exceeds maximum allowed range"):
        controller.scroll(-101)


def test_mouse_failsafe_handling():
    """Verify PyAutoGUI FailSafeException is caught and mapped to FailSafeTriggeredError."""
    controller = MouseController()
    with patch("pyautogui.size", return_value=(1920, 1080)):
        with patch("pyautogui.moveTo", side_effect=pyautogui.FailSafeException()):
            with pytest.raises(FailSafeTriggeredError, match="Emergency stop triggered"):
                controller.move_mouse(100, 100)

        with patch("pyautogui.click", side_effect=pyautogui.FailSafeException()):
            with pytest.raises(FailSafeTriggeredError, match="Emergency stop triggered"):
                controller.click()

        with patch("pyautogui.scroll", side_effect=pyautogui.FailSafeException()):
            with pytest.raises(FailSafeTriggeredError, match="Emergency stop triggered"):
                controller.scroll(5)


def test_move_mouse_tool_metadata_and_execution():
    """Verify MoveMouseTool metadata, risk level, and execution."""
    mock_controller = MagicMock(spec=MouseController)
    mock_controller.move_mouse.return_value = {"success": True, "x": 400, "y": 200, "message": "Moved to (400, 200)"}

    tool = MoveMouseTool(controller=mock_controller)
    assert tool.name == "move_mouse"
    assert tool.risk_level == RiskLevel.SAFE

    res = tool.execute(x=400, y=200)
    assert res["success"] is True
    mock_controller.move_mouse.assert_called_once_with(x=400, y=200)


def test_click_and_double_click_tools():
    """Verify ClickTool and DoubleClickTool execution."""
    mock_controller = MagicMock(spec=MouseController)
    mock_controller.click.return_value = {"success": True, "button": "left", "clicks": 1}
    mock_controller.double_click.return_value = {"success": True, "button": "left", "clicks": 2}

    click_tool = ClickTool(controller=mock_controller)
    assert click_tool.risk_level == RiskLevel.SAFE
    res_click = click_tool.execute(button="left", clicks=1)
    assert res_click["success"] is True

    dc_tool = DoubleClickTool(controller=mock_controller)
    assert dc_tool.risk_level == RiskLevel.SAFE
    res_dc = dc_tool.execute(button="left")
    assert res_dc["success"] is True


def test_scroll_tool():
    """Verify ScrollTool execution and fail-safe handling."""
    mock_controller = MagicMock(spec=MouseController)
    mock_controller.scroll.side_effect = FailSafeTriggeredError("Corner touched")

    scroll_tool = ScrollTool(controller=mock_controller)
    assert scroll_tool.risk_level == RiskLevel.SAFE
    res = scroll_tool.execute(amount=5)
    assert res["success"] is False
    assert res["error"] == "emergency_stop"
    assert "Corner touched" in res["message"]
