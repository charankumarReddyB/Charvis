"""
Keyboard controller for CHARVIS.
Provides controlled keyboard automation via PyAutoGUI with strict key normalization,
input size bounds, and emergency fail-safe protection.
"""

from typing import Any, Dict, List, Optional, Set, Union
import pyautogui

from config import get_settings
from logger import get_logger

logger = get_logger("CHARVIS.Computer.Keyboard")


class ComputerSafetyError(Exception):
    """Raised when an operation violates computer automation safety boundaries."""
    pass


class FailSafeTriggeredError(Exception):
    """Raised when PyAutoGUI emergency fail-safe corner abort is activated."""
    pass


# Normalized key aliases mapping common user/LLM variations to PyAutoGUI key names
KEY_ALIASES: Dict[str, str] = {
    "return": "enter",
    "enter": "enter",
    "esc": "escape",
    "escape": "escape",
    "del": "delete",
    "delete": "delete",
    "back": "backspace",
    "backspace": "backspace",
    "space": "space",
    "spacebar": "space",
    "pgup": "pageup",
    "pageup": "pageup",
    "page_up": "pageup",
    "pgdn": "pagedown",
    "pagedown": "pagedown",
    "page_down": "pagedown",
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "win": "winleft",
    "windows": "winleft",
    "winleft": "winleft",
    "winright": "winright",
    "cmd": "winleft",
    "command": "winleft",
    "super": "winleft",
    "meta": "winleft",
    "tab": "tab",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "home": "home",
    "end": "end",
    "insert": "insert",
    "ins": "insert",
    "capslock": "capslock",
    "caps_lock": "capslock",
    "numlock": "numlock",
    "scrolllock": "scrolllock",
    "printscreen": "printscreen",
    "prtscn": "printscreen",
    "pause": "pause",
}

# Whitelist of allowed individual keyboard keys
VALID_KEYS: Set[str] = set(KEY_ALIASES.values()).union({
    # Alphanumeric
    *(chr(i) for i in range(ord("a"), ord("z") + 1)),
    *(str(i) for i in range(10)),
    # Function keys F1 through F12 (and up to F24)
    *(f"f{i}" for i in range(1, 25)),
    # Common punctuation and symbols
    "-", "=", "[", "]", "\\", ";", "'", ",", ".", "/", "`",
})

# Hotkeys that are strictly prohibited by CHARVIS safety policy
BLOCKED_HOTKEYS: Set[frozenset] = {
    frozenset({"ctrl", "alt", "delete"}),
    frozenset({"ctrl", "alt", "del"}),
}

# High-risk hotkeys that close windows or lock the system
HIGH_RISK_HOTKEYS: Set[frozenset] = {
    frozenset({"alt", "f4"}),
    frozenset({"winleft", "l"}),
    frozenset({"win", "l"}),
}


def normalize_key(key: str) -> str:
    """
    Normalize and validate a single keyboard key.
    Resolves case differences and common aliases (e.g., 'Enter', 'RETURN' -> 'enter').
    Raises ValueError if key is invalid or unrecognized.
    """
    if not isinstance(key, str):
        raise ValueError(f"Key must be a string, got {type(key).__name__}.")

    k = key.strip().lower()
    if not k:
        raise ValueError("Key name cannot be empty.")

    normalized = KEY_ALIASES.get(k, k)
    if normalized not in VALID_KEYS and normalized not in pyautogui.KEYBOARD_KEYS:
        raise ValueError(f"Unrecognized or invalid keyboard key: '{key}'.")

    return normalized


def parse_hotkey_sequence(keys: Union[List[str], str]) -> List[str]:
    """
    Parse a hotkey combination into a normalized list of validated keys.
    Accepts either a list (['ctrl', 'c']) or a string ('ctrl+c', 'Ctrl+Alt+T').
    """
    if isinstance(keys, str):
        raw_keys = [part.strip() for part in keys.split("+") if part.strip()]
    elif isinstance(keys, (list, tuple)):
        raw_keys = [str(k).strip() for k in keys if str(k).strip()]
    else:
        raise ValueError(f"Hotkey arguments must be a string or list of strings, got {type(keys).__name__}.")

    if not raw_keys:
        raise ValueError("Hotkey sequence cannot be empty.")

    if len(raw_keys) > 5:
        raise ValueError(f"Hotkey sequence exceeds maximum limit of 5 keys (got {len(raw_keys)}).")

    normalized = [normalize_key(k) for k in raw_keys]
    key_set = frozenset(normalized)

    # Check for blocked combinations
    if key_set in BLOCKED_HOTKEYS:
        raise ComputerSafetyError(
            f"Hotkey sequence '{'+'.join(raw_keys)}' is strictly prohibited by CHARVIS safety policy."
        )

    return normalized


def is_high_risk_hotkey(normalized_keys: List[str]) -> bool:
    """Return True if the hotkey combination is classified as HIGH_RISK (e.g. Alt+F4, Win+L)."""
    return frozenset(normalized_keys) in HIGH_RISK_HOTKEYS


class KeyboardController:
    """Controller for automated keyboard input via PyAutoGUI."""

    def __init__(
        self,
        failsafe: Optional[bool] = None,
        max_type_length: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        self.failsafe = settings.pyautogui_failsafe if failsafe is None else failsafe
        self.max_type_length = settings.max_type_length if max_type_length is None else max_type_length
        pyautogui.FAILSAFE = self.failsafe
        logger.debug("KeyboardController initialized (failsafe=%s, max_type_len=%d)", self.failsafe, self.max_type_length)

    def type_text(self, text: str) -> Dict[str, Any]:
        """
        Type text into the currently active desktop window.
        Enforces string validation, length bounds, and fail-safe handling.
        """
        if not isinstance(text, str):
            raise ValueError(f"text must be a string, got {type(text).__name__}.")

        if not text:
            raise ValueError("text cannot be empty.")

        if len(text) > self.max_type_length:
            raise ValueError(
                f"text length ({len(text)}) exceeds maximum allowed limit of {self.max_type_length} characters."
            )

        try:
            logger.info("Typing text (%d characters) into active window", len(text))
            pyautogui.write(text, interval=0.01)
            return {
                "success": True,
                "typed_length": len(text),
                "message": f"Successfully typed {len(text)} characters.",
            }
        except pyautogui.FailSafeException:
            logger.critical("PyAutoGUI emergency fail-safe triggered during type_text!")
            raise FailSafeTriggeredError("Emergency stop triggered: mouse moved to fail-safe corner.")
        except Exception as e:
            logger.error("Error during type_text execution: %s", str(e))
            raise

    def press_key(self, key: str, presses: int = 1) -> Dict[str, Any]:
        """
        Press a validated keyboard key.
        Supports key normalization and repetition bounds.
        """
        norm_key = normalize_key(key)
        if not isinstance(presses, int) or presses < 1 or presses > 10:
            raise ValueError(f"presses must be an integer between 1 and 10, got {presses}.")

        try:
            logger.info("Pressing key '%s' (%d time(s))", norm_key, presses)
            pyautogui.press(norm_key, presses=presses, interval=0.05)
            return {
                "success": True,
                "key": norm_key,
                "presses": presses,
                "message": f"Pressed '{norm_key}' {presses} time(s).",
            }
        except pyautogui.FailSafeException:
            logger.critical("PyAutoGUI emergency fail-safe triggered during press_key!")
            raise FailSafeTriggeredError("Emergency stop triggered: mouse moved to fail-safe corner.")
        except Exception as e:
            logger.error("Error during press_key execution: %s", str(e))
            raise

    def hotkey(self, keys: Union[List[str], str]) -> Dict[str, Any]:
        """
        Execute a validated hotkey combination (e.g. 'ctrl+c', ['alt', 'tab']).
        """
        norm_keys = parse_hotkey_sequence(keys)

        try:
            logger.info("Executing hotkey combination: %s", "+".join(norm_keys))
            pyautogui.hotkey(*norm_keys)
            return {
                "success": True,
                "hotkey": "+".join(norm_keys),
                "message": f"Executed hotkey: {'+'.join(norm_keys)}.",
            }
        except pyautogui.FailSafeException:
            logger.critical("PyAutoGUI emergency fail-safe triggered during hotkey!")
            raise FailSafeTriggeredError("Emergency stop triggered: mouse moved to fail-safe corner.")
        except Exception as e:
            logger.error("Error during hotkey execution: %s", str(e))
            raise
