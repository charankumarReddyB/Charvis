"""
Desktop and region screenshot capture engine using Pillow ImageGrab.
Phase 11: Screenshot & OCR.
"""

from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Callable, Optional, Tuple

from PIL import Image, ImageGrab

from vision.models import (
    NoDisplayAvailableError,
    ScreenshotError,
    ScreenshotMetadata,
    ScreenshotPermissionError,
    VisionSecurityError,
)
from vision.security import (
    validate_monitor_index,
    validate_region_coordinates,
    validate_screenshot_save_path,
)

logger = logging.getLogger(__name__)


def get_screen_dimensions() -> Tuple[int, int]:
    """
    Query Windows system metrics for the primary screen resolution.
    Returns (width, height). Returns (1920, 1080) default fallback on error.
    """
    try:
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        if w > 0 and h > 0:
            return w, h
    except Exception as exc:
        logger.debug("Failed to query screen metrics via ctypes: %s", exc)
    return 1920, 1080


def get_monitor_count() -> int:
    """
    Query the number of display monitors on the desktop.
    """
    try:
        user32 = ctypes.windll.user32
        count = user32.GetSystemMetrics(80)  # SM_CMONITORS
        return max(1, count)
    except Exception:
        return 1


class ScreenshotEngine:
    """
    Captures desktop screenshots strictly in-memory using Pillow ImageGrab.
    Provides region capture, monitor validation, and explicit saving to sandbox.
    """

    def __init__(
        self,
        grabber: Optional[Callable[..., Image.Image]] = None,
        max_region_area: int = 33_177_600,
    ) -> None:
        """
        Initialize the screenshot engine.

        :param grabber: Optional callable to replace ImageGrab.grab (useful for testing/mocking).
        :param max_region_area: Maximum allowed region pixel area.
        """
        self._grabber = grabber or ImageGrab.grab
        self._max_region_area = max_region_area
        self._last_screenshot: Optional[Image.Image] = None
        self._last_metadata: Optional[ScreenshotMetadata] = None

    @property
    def last_screenshot(self) -> Optional[Image.Image]:
        """Return the most recently captured in-memory screenshot, if any."""
        return self._last_screenshot

    @property
    def last_metadata(self) -> Optional[ScreenshotMetadata]:
        """Return metadata for the most recently captured screenshot."""
        return self._last_metadata

    def clear_cache(self) -> None:
        """Clear cached in-memory screenshot."""
        self._last_screenshot = None
        self._last_metadata = None

    def capture_primary(self) -> Tuple[Image.Image, ScreenshotMetadata]:
        """
        Capture the entire primary display screen.
        The image is stored in memory and returned along with structured metadata.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            img = self._grabber()
        except OSError as exc:
            msg = str(exc).lower()
            if "screen grab failed" in msg or "permission" in msg:
                raise ScreenshotPermissionError(
                    "Failed to capture screen. The desktop may be locked, in a secure session, "
                    "or lacking display capture permissions."
                ) from exc
            raise ScreenshotError(f"Desktop screenshot capture failed: {exc}") from exc
        except Exception as exc:
            raise ScreenshotError(f"Unexpected screenshot capture failure: {exc}") from exc

        if img is None:
            raise NoDisplayAvailableError("Screenshot capture returned an empty image.")

        w, h = img.size
        metadata = ScreenshotMetadata(
            width=w,
            height=h,
            monitor=0,
            timestamp=timestamp,
        )
        self._last_screenshot = img
        self._last_metadata = metadata
        logger.info("Captured primary screen in-memory: %dx%d px", w, h)
        return img, metadata

    def capture_monitor(self, monitor: int) -> Tuple[Image.Image, ScreenshotMetadata]:
        """
        Capture a specific display monitor.
        Monitor 0 indicates primary monitor.
        """
        available = get_monitor_count()
        validate_monitor_index(monitor, available)

        # Monitor 0 is primary display
        if monitor == 0:
            return self.capture_primary()

        # Multi-monitor support via all_screens grab if available
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            img = self._grabber(all_screens=True)
        except OSError as exc:
            raise ScreenshotPermissionError(
                f"Failed to capture monitor {monitor}: display access error: {exc}"
            ) from exc
        except Exception as exc:
            raise ScreenshotError(f"Failed to capture monitor {monitor}: {exc}") from exc

        w, h = img.size
        metadata = ScreenshotMetadata(
            width=w,
            height=h,
            monitor=monitor,
            timestamp=timestamp,
        )
        self._last_screenshot = img
        self._last_metadata = metadata
        logger.info("Captured monitor %d in-memory: %dx%d px", monitor, w, h)
        return img, metadata

    def capture_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> Tuple[Image.Image, ScreenshotMetadata]:
        """
        Capture a bounded rectangular region of the desktop.

        :param x: Left coordinate (origin: top-left 0,0)
        :param y: Top coordinate
        :param width: Region width in pixels
        :param height: Region height in pixels
        """
        screen_w, screen_h = get_screen_dimensions()
        validate_region_coordinates(
            x=x,
            y=y,
            width=width,
            height=height,
            screen_width=screen_w,
            screen_height=screen_h,
            max_area=self._max_region_area,
        )

        bbox = (x, y, x + width, y + height)
        timestamp = datetime.now(timezone.utc).isoformat()

        try:
            img = self._grabber(bbox=bbox)
        except OSError as exc:
            msg = str(exc).lower()
            if "screen grab failed" in msg:
                raise ScreenshotPermissionError(
                    "Failed to capture region: desktop is locked or display capture is unavailable."
                ) from exc
            raise ScreenshotError(f"Failed to capture region {bbox}: {exc}") from exc
        except Exception as exc:
            raise ScreenshotError(f"Region screenshot capture failed: {exc}") from exc

        if img is None:
            raise ScreenshotError(f"Region capture returned empty image for {bbox}")

        w, h = img.size
        metadata = ScreenshotMetadata(
            width=w,
            height=h,
            monitor=0,
            timestamp=timestamp,
        )
        self._last_screenshot = img
        self._last_metadata = metadata
        logger.info("Captured region bbox=%s in-memory: %dx%d px", bbox, w, h)
        return img, metadata

    def save_last_screenshot(
        self,
        filename: str,
        sandbox_root: Path,
        overwrite: bool = False,
    ) -> Path:
        """
        Explicitly save the currently captured in-memory screenshot to a file.
        Enforces strict sandbox root validation and overwrite protection.
        """
        if self._last_screenshot is None:
            # If no screenshot exists in memory, capture one now
            self.capture_primary()

        dest_path = validate_screenshot_save_path(filename, sandbox_root)

        if dest_path.exists() and not overwrite:
            raise VisionSecurityError(
                f"File '{dest_path.name}' already exists in workspace. Overwrite not confirmed."
            )

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._last_screenshot.save(str(dest_path))
        except Exception as exc:
            raise ScreenshotError(f"Failed to save screenshot to '{dest_path}': {exc}") from exc

        logger.info("Saved screenshot to '%s'", dest_path)
        return dest_path
