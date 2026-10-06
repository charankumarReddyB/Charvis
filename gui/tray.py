"""
System Tray Integration for CHARVIS (Phase 18).
Provides a background tray icon connecting strictly to the authoritative runtime
via RuntimeClient/RuntimeController, displaying visual state indicators,
sanitized tooltips, and non-blocking desktop interaction controls.
"""

from enum import Enum
import threading
import time
from typing import Any, Callable, Dict, Optional

from PIL import Image, ImageDraw
import pystray

from activation.manager import ActivationManager
from activation.models import ActivationState
from core.notifications import NotificationType, get_notification_service
from logger import get_logger
from runtime.client import RuntimeClient
from runtime.controller import RuntimeController
from runtime.state import RuntimeState

logger = get_logger("CHARVIS.GUI.Tray")


class TrayStatus(str, Enum):
    """Visual states represented in the system tray."""
    READY = "Ready"
    LISTENING = "Listening"
    PROCESSING = "Processing"
    SPEAKING = "Speaking"
    PAUSED = "Paused"
    ERROR = "Error"
    OFFLINE = "Offline"


def create_tray_icon_image(status: TrayStatus, size: int = 64) -> Image.Image:
    """
    Dynamically generate a distinct, high-contrast 64x64 tray icon image
    for the specified operational status without relying on external file assets.
    """
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Base circle color by state
    colors = {
        TrayStatus.READY: ((10, 132, 255), (0, 210, 255)),       # Cyan/Blue
        TrayStatus.LISTENING: ((48, 209, 88), (140, 255, 170)),  # Green
        TrayStatus.PROCESSING: ((255, 159, 10), (255, 214, 10)), # Amber
        TrayStatus.SPEAKING: ((88, 101, 242), (150, 160, 255)),   # Purple/Blue
        TrayStatus.PAUSED: ((142, 142, 147), (174, 174, 178)),   # Grey
        TrayStatus.ERROR: ((255, 69, 58), (255, 105, 97)),       # Red
        TrayStatus.OFFLINE: ((72, 72, 74), (99, 99, 102)),       # Dark Slate
    }
    primary_color, secondary_color = colors.get(status, colors[TrayStatus.READY])

    margin = 4
    # Draw background circle
    draw.ellipse([margin, margin, size - margin, size - margin], fill=primary_color, outline=secondary_color, width=3)

    center = size // 2
    # Draw distinct glyph depending on status (avoiding color-only distinction)
    if status == TrayStatus.READY:
        # 'C' glyph for CHARVIS
        draw.arc([center - 14, center - 14, center + 14, center + 14], start=45, end=315, fill="white", width=4)
    elif status == TrayStatus.LISTENING:
        # Microphone pill
        draw.rounded_rectangle([center - 6, center - 14, center + 6, center + 6], radius=5, fill="white")
        draw.line([center, center + 6, center, center + 14], fill="white", width=3)
        draw.line([center - 8, center + 14, center + 8, center + 14], fill="white", width=3)
    elif status == TrayStatus.PROCESSING:
        # Triangular play/processing indicator
        points = [(center - 8, center - 12), (center + 12, center), (center - 8, center + 12)]
        draw.polygon(points, fill="white")
    elif status == TrayStatus.SPEAKING:
        # Speaker wave glyph
        draw.polygon([(center - 10, center - 6), (center - 4, center - 6), (center + 2, center - 12), (center + 2, center + 12), (center - 4, center + 6), (center - 10, center + 6)], fill="white")
        draw.arc([center + 2, center - 8, center + 12, center + 8], start=-45, end=45, fill="white", width=2)
    elif status == TrayStatus.PAUSED:
        # Two vertical bars
        draw.rectangle([center - 9, center - 12, center - 3, center + 12], fill="white")
        draw.rectangle([center + 3, center - 12, center + 9, center + 12], fill="white")
    elif status == TrayStatus.ERROR:
        # Exclamation mark
        draw.rectangle([center - 3, center - 14, center + 3, center + 4], fill="white")
        draw.ellipse([center - 3, center + 8, center + 3, center + 14], fill="white")
    else: # OFFLINE
        # Slash / cross
        draw.line([center - 10, center - 10, center + 10, center + 10], fill="white", width=4)

    return image


class SystemTrayManager:
    """
    Manages the Windows system tray icon and menu lifecycle.
    Bridges user interaction with the authoritative Background Runtime and ActivationManager.
    """

    def __init__(
        self,
        runtime_client: Optional[RuntimeClient] = None,
        runtime_controller: Optional[RuntimeController] = None,
        activation_manager: Optional[ActivationManager] = None,
        on_open_gui: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
    ) -> None:
        self.client = runtime_client
        self.controller = runtime_controller
        self.activation = activation_manager
        self.on_open_gui = on_open_gui
        self.on_exit_callback = on_exit

        self._status: TrayStatus = TrayStatus.READY
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._notification_service = get_notification_service()

        # Connect notification service to tray notifications
        self._notification_service.set_backend(self._tray_notify)

        # Listen to activation events if manager provided
        if self.activation:
            self.activation.add_listener(self._on_activation_change)

    @property
    def current_status(self) -> TrayStatus:
        return self._status

    def _tray_notify(self, title: str, message: str) -> None:
        """Forward notification to pystray icon if running."""
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception as e:
                logger.debug("pystray notify error: %s", e)

    def _on_activation_change(self, session: Any) -> None:
        """Handle activation state transitions and update icon/tooltip immediately."""
        state = session.state
        if state == ActivationState.LISTENING:
            self.set_status(TrayStatus.LISTENING, "Listening for speech...")
        elif state == ActivationState.PROCESSING:
            self.set_status(TrayStatus.PROCESSING, "Processing command...")
        elif state == ActivationState.SPEAKING:
            self.set_status(TrayStatus.SPEAKING, "Speaking response...")
        elif state in (ActivationState.COMPLETED, ActivationState.INACTIVE, ActivationState.CANCELLED):
            self.set_status(TrayStatus.READY)
        elif state == ActivationState.ERROR:
            self.set_status(TrayStatus.ERROR, session.error_message or "Error")

    def set_status(self, status: TrayStatus, details: str = "") -> None:
        """Update the visual icon and tooltip text."""
        with self._lock:
            self._status = status
            tooltip = f"CHARVIS — {status.value}"
            if details:
                tooltip = f"{tooltip} ({details})"

            if self._icon:
                try:
                    self._icon.icon = create_tray_icon_image(status)
                    self._icon.title = tooltip
                except Exception as e:
                    logger.debug("Error updating tray icon: %s", e)

    def _build_menu(self) -> pystray.Menu:
        """Construct the context menu conforming to Phase 18 specifications."""
        return pystray.Menu(
            pystray.MenuItem("Open CHARVIS", self._action_open_gui, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Voice Mode", self._action_voice_mode),
            pystray.MenuItem(
                "Wake Word",
                self._action_toggle_wake_word,
                checked=lambda item: self._is_wake_word_active(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Pause CHARVIS",
                self._action_pause,
                enabled=lambda item: self._can_pause(),
            ),
            pystray.MenuItem(
                "Resume CHARVIS",
                self._action_resume,
                enabled=lambda item: self._can_resume(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Runtime Status", self._action_status),
            pystray.MenuItem("Settings / Diagnosis", self._action_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit CHARVIS", self._action_exit),
        )

    # --- Menu Actions ---
    def _action_open_gui(self, icon: Any = None, item: Any = None) -> None:
        logger.info("Tray action: Open CHARVIS")
        if self.on_open_gui:
            try:
                self.on_open_gui()
            except Exception as e:
                logger.error("Error opening GUI: %s", e)

    def _action_voice_mode(self, icon: Any = None, item: Any = None) -> None:
        logger.info("Tray action: Voice Mode")
        if self.activation:
            from activation.models import ActivationSource
            self.activation.request_activation(ActivationSource.TRAY)
        elif self.client:
            try:
                self.client.send_request("voice_start")
            except Exception as e:
                logger.error("Failed to start voice mode via IPC: %s", e)

    def _action_toggle_wake_word(self, icon: Any = None, item: Any = None) -> None:
        logger.info("Tray action: Toggle Wake Word")
        if self.activation:
            if self.activation.is_wake_word_running():
                self.activation.disable_wake_word()
            else:
                self.activation.enable_wake_word()
        elif self.client:
            try:
                is_active = self._is_wake_word_active()
                op = "voice_stop" if is_active else "voice_start"
                self.client.send_request(op)
            except Exception as e:
                logger.error("Failed to toggle wake word via IPC: %s", e)

    def _is_wake_word_active(self) -> bool:
        if self.activation:
            return self.activation.is_wake_word_running()
        if self.controller and hasattr(self.controller, "wake_word_engine"):
            return bool(self.controller.wake_word_engine and self.controller.wake_word_engine.is_running)
        return False

    def _can_pause(self) -> bool:
        return self._status != TrayStatus.PAUSED and self._status != TrayStatus.OFFLINE

    def _can_resume(self) -> bool:
        return self._status == TrayStatus.PAUSED

    def _action_pause(self, icon: Any = None, item: Any = None) -> None:
        logger.info("Tray action: Pause CHARVIS")
        if self.client:
            try:
                self.client.send_request("pause")
            except Exception as e:
                logger.error("Failed to pause runtime via IPC: %s", e)
        elif self.controller:
            try:
                self.controller.pause()
            except Exception as e:
                logger.error("Failed to pause controller: %s", e)
        self.set_status(TrayStatus.PAUSED)
        self._notification_service.notify("CHARVIS", "CHARVIS is paused.", NotificationType.PAUSED)

    def _action_resume(self, icon: Any = None, item: Any = None) -> None:
        logger.info("Tray action: Resume CHARVIS")
        if self.client:
            try:
                self.client.send_request("resume")
            except Exception as e:
                logger.error("Failed to resume runtime via IPC: %s", e)
        elif self.controller:
            try:
                self.controller.resume()
            except Exception as e:
                logger.error("Failed to resume controller: %s", e)
        self.set_status(TrayStatus.READY)
        self._notification_service.notify("CHARVIS", "CHARVIS is ready.", NotificationType.READY)

    def _action_status(self, icon: Any = None, item: Any = None) -> None:
        logger.info("Tray action: Runtime Status")
        status_text = f"Status: {self._status.value}"
        if self.client:
            try:
                data = self.client.send_request("status")
                uptime = data.get("uptime", 0.0)
                status_text = f"State: {data.get('state')} | Uptime: {uptime:.1f}s | Version: {data.get('version')}"
            except Exception as e:
                status_text = f"Status check error: {e}"
        elif self.controller:
            try:
                st = self.controller.get_status()
                status_text = f"State: {st.state} | Uptime: {st.uptime:.1f}s | Version: {st.version}"
            except Exception as e:
                status_text = f"Status check error: {e}"
        self._notification_service.notify("CHARVIS Runtime", status_text, NotificationType.INFO, force=True)

    def _action_settings(self, icon: Any = None, item: Any = None) -> None:
        logger.info("Tray action: Settings / Diagnosis")
        if self.on_open_gui:
            self.on_open_gui()

    def _action_exit(self, icon: Any = None, item: Any = None) -> None:
        logger.info("Tray action: Exit CHARVIS requested by user.")
        # 1. Stop background runtime if connected
        if self.client:
            try:
                self.client.send_request("shutdown")
            except Exception as e:
                logger.debug("Notice on shutdown IPC request: %s", e)
        elif self.controller:
            try:
                self.controller.stop()
            except Exception as e:
                logger.debug("Notice on controller stop: %s", e)

        # 2. Stop tray icon
        self.stop()

        # 3. Invoke optional exit callback (e.g. GUI root.destroy)
        if self.on_exit_callback:
            try:
                self.on_exit_callback()
            except Exception as e:
                logger.error("Error in exit callback: %s", e)

    # --- Lifecycle ---
    def start(self) -> None:
        """Start the system tray icon on a background thread."""
        with self._lock:
            if self._icon is not None:
                return

            self._stop_event.clear()
            initial_image = create_tray_icon_image(self._status)
            self._icon = pystray.Icon(
                name="CHARVIS",
                icon=initial_image,
                title=f"CHARVIS — {self._status.value}",
                menu=self._build_menu(),
            )

            self._thread = threading.Thread(
                target=self._run_icon_loop,
                name="CHARVIS-TrayIcon",
                daemon=True,
            )
            self._thread.start()
            logger.info("SystemTrayManager started.")

    def _run_icon_loop(self) -> None:
        """Run pystray event loop."""
        try:
            if self._icon:
                self._icon.run()
        except Exception as e:
            logger.error("Error in pystray loop: %s", e)

    def stop(self) -> None:
        """Cleanly remove the system tray icon."""
        with self._lock:
            self._stop_event.set()
            if self._icon:
                try:
                    self._icon.stop()
                except Exception as e:
                    logger.debug("Notice stopping pystray icon: %s", e)
                self._icon = None
            logger.info("SystemTrayManager stopped cleanly.")
