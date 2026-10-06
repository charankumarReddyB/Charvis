"""
Safe Windows Global Hotkey Integration for CHARVIS (Phase 18).
Uses the native Windows RegisterHotKey API via ctypes to listen strictly
for Ctrl + Alt + Space without capturing arbitrary keystrokes or using keyloggers.
"""

import ctypes
from ctypes import wintypes
import threading
import time
from typing import Callable, Optional

from logger import get_logger

logger = get_logger("CHARVIS.Activation.Hotkey")

# Windows API constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
VK_SPACE = 0x0020
WM_HOTKEY = 0x0312
HOTKEY_ID = 101
HOTKEY_COMBINATION = "Ctrl+Alt+Space"


class GlobalHotkeyManager:
    """
    Manages safe, OS-level global hotkey registration for activation.
    Strictly listens only for Ctrl + Alt + Space. Never logs or monitors arbitrary keys.
    """

    def __init__(
        self,
        on_trigger: Optional[Callable[[], None]] = None,
        on_triggered: Optional[Callable[[], None]] = None,
        enabled: bool = False,
    ) -> None:
        self.on_trigger = on_triggered or on_trigger
        self.enabled = enabled
        self.combination = HOTKEY_COMBINATION
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_registered = False
        self._lock = threading.Lock()

    @property
    def is_enabled(self) -> bool:
        return self.enabled

    @property
    def is_registered(self) -> bool:
        return self._is_registered

    @property
    def is_running(self) -> bool:
        """Return True if the hotkey listener thread is active."""
        return self._thread is not None and self._thread.is_alive()

    def _dispatch_trigger(self) -> None:
        self.trigger_manually()

    def start(self) -> bool:
        """
        Start the background Windows message loop to listen for Ctrl + Alt + Space.
        Returns True if listener started, False if disabled or already running.
        """
        with self._lock:
            if not self.enabled:
                logger.info("Global hotkey activation is disabled by default.")
                return False

            if self.is_running:
                return True

            try:
                user32 = ctypes.windll.user32
                reg_ok = user32.RegisterHotKey(
                    None,
                    HOTKEY_ID,
                    MOD_CONTROL | MOD_ALT,
                    VK_SPACE,
                )
                if not reg_ok:
                    logger.warning("Failed to register Windows hotkey Ctrl+Alt+Space.")
                    return False
                self._is_registered = True
            except Exception as e:
                logger.warning("Error registering hotkey: %s", e)
                return False

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._hotkey_loop,
                name="CHARVIS-GlobalHotkey",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self) -> None:
        """Unregister the hotkey and cleanly shut down the message loop."""
        with self._lock:
            self._stop_event.set()

        if self._thread and self._thread.is_alive():
            # Post a dummy WM_NULL or quit message to wake up GetMessage
            try:
                user32 = ctypes.windll.user32
                thread_id = ctypes.c_ulong(self._thread.ident) if self._thread.ident else 0
                if thread_id:
                    user32.PostThreadMessageW(thread_id, 0x0012, 0, 0)  # WM_QUIT
            except Exception as e:
                logger.debug("Notice while stopping hotkey thread: %s", e)
            self._thread.join(timeout=1.0)

        self._thread = None
        if self._is_registered:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
            except Exception:
                pass
            self._is_registered = False
        logger.info("Global hotkey manager stopped cleanly.")

    def trigger_manually(self) -> None:
        """Simulate hotkey activation without pressing physical keys."""
        logger.info("Manual hotkey activation triggered.")
        if self.on_trigger:
            try:
                self.on_trigger()
            except Exception as e:
                logger.error("Error in hotkey activation callback: %s", e)

    def _hotkey_loop(self) -> None:
        """Windows message pump listening strictly for WM_HOTKEY events."""
        user32 = ctypes.windll.user32
        msg = wintypes.MSG()
        try:
            while not self._stop_event.is_set():
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret <= 0:
                    break

                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    logger.info("Global activation hotkey (Ctrl + Alt + Space) detected!")
                    self.trigger_manually()

                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as e:
            logger.debug("Notice in hotkey message loop: %s", e)
