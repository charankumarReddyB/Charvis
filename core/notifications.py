"""
Desktop notification management for CHARVIS (Phase 18).
Delivers minimal, non-intrusive notifications with strict secret redaction
and anti-spam debouncing.
"""

from enum import Enum
import re
import threading
import time
from typing import Any, Callable, Dict, Optional

from logger import SensitiveDataFilter, get_logger

logger = get_logger("CHARVIS.Notifications")


class NotificationType(str, Enum):
    """Classification of system notifications."""
    READY = "READY"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    PAUSED = "PAUSED"
    INFO = "INFO"
    ERROR = "ERROR"


class NotificationService:
    """
    Sanitized and rate-limited Windows desktop notification provider.
    Never exposes credentials, API keys, or raw system passwords.
    """

    def __init__(
        self,
        debounce_interval: float = 2.0,
        enabled: bool = True,
        min_interval_seconds: Optional[float] = None,
    ) -> None:
        self.debounce_interval = min_interval_seconds if min_interval_seconds is not None else debounce_interval
        self.enabled = enabled
        self._last_sent: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._data_filter = SensitiveDataFilter()
        self._notifier_backend: Optional[Callable[[str, str], None]] = None

    def set_backend(self, backend: Optional[Callable[[str, str], None]]) -> None:
        """Configure custom or UI notification delivery backend (e.g., tray icon notify)."""
        with self._lock:
            self._notifier_backend = backend

    def _sanitize(self, text: str) -> str:
        """Strip sensitive credentials, keys, and tokens from notification text."""
        sanitized = text
        for pattern, replacement in self._data_filter.PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    def notify(
        self,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
        force: bool = False,
    ) -> bool:
        """
        Deliver a sanitized notification if not within the debounce window.

        Args:
            title: Notification heading
            message: Body message (will be sanitized for secrets)
            notification_type: Notification category
            force: If True, bypass debounce check

        Returns:
            bool: True if notification was emitted; False if debounced or suppressed.
        """
        if not self.enabled:
            return False

        clean_title = self._sanitize(title)
        clean_message = self._sanitize(message)

        now = time.time()
        key = f"{clean_title}:{notification_type.value}"

        with self._lock:
            if not force:
                last_time = self._last_sent.get(key, 0.0)
                if (now - last_time) < self.debounce_interval:
                    logger.debug("Notification suppressed by debounce: %s", key)
                    return False
            self._last_sent[key] = now

        logger.info("[%s] %s: %s", notification_type.value, clean_title, clean_message)

        with self._lock:
            backend = self._notifier_backend

        if backend is not None:
            try:
                backend(clean_title, clean_message)
            except Exception as e:
                logger.debug("Backend notification error: %s", e)

        return True


# Global default instance
_default_service: Optional[NotificationService] = None
_service_lock = threading.Lock()


def get_notification_service() -> NotificationService:
    """Retrieve or initialize the global NotificationService singleton."""
    global _default_service
    with _service_lock:
        if _default_service is None:
            _default_service = NotificationService()
        return _default_service
