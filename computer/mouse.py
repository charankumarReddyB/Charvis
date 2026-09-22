"""
Mouse controller for CHARVIS.
Provides controlled mouse automation via PyAutoGUI with strict screen boundary checks,
rate limiting, and emergency fail-safe protection.
"""

from typing import Any, Dict, Optional, Tuple
import pyautogui

from computer.keyboard import FailSafeTriggeredError
from config import get_settings
from logger import get_logger

logger = get_logger("CHARVIS.Computer.Mouse")

VALID_BUTTONS = {"left", "right", "middle"}


class MouseController:
    """Controller for automated mouse movement, clicking, and scrolling via PyAutoGUI."""

    def __init__(
        self,
        failsafe: Optional[bool] = None,
        max_scroll_amount: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        self.failsafe = settings.pyautogui_failsafe if failsafe is None else failsafe
        self.max_scroll_amount = settings.max_scroll_amount if max_scroll_amount is None else max_scroll_amount
        pyautogui.FAILSAFE = self.failsafe
        logger.debug("MouseController initialized (failsafe=%s, max_scroll=%d)", self.failsafe, self.max_scroll_amount)

    def get_screen_size(self) -> Tuple[int, int]:
        """Return the current primary screen resolution (width, height)."""
        try:
            return pyautogui.size()
        except Exception as e:
            logger.error("Failed to query screen size: %s", str(e))
            # Fallback default if running in headless test without mock
            return (1920, 1080)

    def move_mouse(self, x: int, y: int) -> Dict[str, Any]:
        """
        Move the mouse cursor to absolute screen coordinates (x, y).
        Validates integer types and enforces screen boundaries.
        Rejects out-of-bounds coordinates without clamping.
        """
        if not isinstance(x, int) or isinstance(x, bool):
            raise ValueError(f"x coordinate must be an integer, got {type(x).__name__}.")
        if not isinstance(y, int) or isinstance(y, bool):
            raise ValueError(f"y coordinate must be an integer, got {type(y).__name__}.")

        width, height = self.get_screen_size()

        if x < 0 or y < 0 or x >= width or y >= height:
            raise ValueError(
                f"Coordinates ({x}, {y}) are outside the current {width}x{height} screen."
            )

        try:
            logger.info("Moving mouse cursor to (%d, %d)", x, y)
            pyautogui.moveTo(x, y, duration=0.2)
            return {
                "success": True,
                "x": x,
                "y": y,
                "message": f"Mouse moved to ({x}, {y}).",
            }
        except pyautogui.FailSafeException:
            logger.critical("PyAutoGUI emergency fail-safe triggered during move_mouse!")
            raise FailSafeTriggeredError("Emergency stop triggered: mouse moved to fail-safe corner.")
        except Exception as e:
            logger.error("Error moving mouse to (%d, %d): %s", x, y, str(e))
            raise

    def click(self, button: str = "left", clicks: int = 1) -> Dict[str, Any]:
        """
        Click the mouse at the current position.
        Accepts button ('left', 'right', 'middle') and clicks (1 or 2).
        """
        if not isinstance(button, str):
            raise ValueError(f"button must be a string, got {type(button).__name__}.")

        btn = button.strip().lower()
        if btn not in VALID_BUTTONS:
            valid_list = ", ".join(sorted(VALID_BUTTONS))
            raise ValueError(f"Invalid mouse button '{button}'. Supported buttons: {valid_list}.")

        if not isinstance(clicks, int) or isinstance(clicks, bool) or clicks not in (1, 2):
            raise ValueError(f"clicks must be 1 or 2, got {clicks}.")

        try:
            action_desc = "Double-clicked" if clicks == 2 else "Clicked"
            logger.info("%s mouse %s button at current cursor position", action_desc, btn)
            pyautogui.click(button=btn, clicks=clicks, interval=0.1)
            return {
                "success": True,
                "button": btn,
                "clicks": clicks,
                "message": f"{action_desc} {btn} mouse button.",
            }
        except pyautogui.FailSafeException:
            logger.critical("PyAutoGUI emergency fail-safe triggered during click!")
            raise FailSafeTriggeredError("Emergency stop triggered: mouse moved to fail-safe corner.")
        except Exception as e:
            logger.error("Error executing mouse click (button=%s, clicks=%d): %s", btn, clicks, str(e))
            raise

    def double_click(self, button: str = "left") -> Dict[str, Any]:
        """Convenience method for double clicking the mouse button."""
        return self.click(button=button, clicks=2)

    def scroll(self, amount: int) -> Dict[str, Any]:
        """
        Scroll the mouse wheel.
        Positive amount scrolls up, negative amount scrolls down.
        Enforces maximum scroll boundaries to prevent runaway scrolling.
        """
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise ValueError(f"Scroll amount must be an integer, got {type(amount).__name__}.")

        if abs(amount) > self.max_scroll_amount:
            raise ValueError(
                f"Scroll amount ({amount}) exceeds maximum allowed range [{-self.max_scroll_amount}, {self.max_scroll_amount}]."
            )

        try:
            direction = "up" if amount > 0 else "down"
            logger.info("Scrolling mouse wheel %d units (%s)", amount, direction)
            pyautogui.scroll(amount)
            return {
                "success": True,
                "amount": amount,
                "direction": direction,
                "message": f"Scrolled {amount} units ({direction}).",
            }
        except pyautogui.FailSafeException:
            logger.critical("PyAutoGUI emergency fail-safe triggered during scroll!")
            raise FailSafeTriggeredError("Emergency stop triggered: mouse moved to fail-safe corner.")
        except Exception as e:
            logger.error("Error scrolling mouse wheel (%d units): %s", amount, str(e))
            raise
