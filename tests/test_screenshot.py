"""
Unit tests for CHARVIS Screenshot Engine.
Phase 11: Screenshot & OCR.
"""

from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image
import pytest

from vision.models import (
    NoDisplayAvailableError,
    ScreenshotError,
    ScreenshotPermissionError,
    VisionSecurityError,
)
from vision.screenshot import ScreenshotEngine


def create_test_image(width: int = 1920, height: int = 1080, color: str = "white") -> Image.Image:
    """Helper to create a solid PIL test image."""
    return Image.new("RGB", (width, height), color=color)


class TestScreenshotEngine:
    """Tests for in-memory screenshot capture, region capture, and saving."""

    def test_capture_primary_in_memory(self):
        fake_img = create_test_image(1920, 1080)
        mock_grabber = MagicMock(return_value=fake_img)
        engine = ScreenshotEngine(grabber=mock_grabber)

        img, meta = engine.capture_primary()

        assert img is fake_img
        assert meta.width == 1920
        assert meta.height == 1080
        assert meta.monitor == 0
        assert engine.last_screenshot is fake_img
        mock_grabber.assert_called_once()

    def test_capture_does_not_create_disk_files(self, tmp_path: Path):
        fake_img = create_test_image(800, 600)
        engine = ScreenshotEngine(grabber=lambda **k: fake_img)

        # Record directory contents before
        files_before = list(tmp_path.glob("*"))
        engine.capture_primary()
        files_after = list(tmp_path.glob("*"))

        assert files_before == files_after

    def test_capture_monitor_primary(self):
        fake_img = create_test_image(1920, 1080)
        mock_grabber = MagicMock(return_value=fake_img)
        engine = ScreenshotEngine(grabber=mock_grabber)

        img, meta = engine.capture_monitor(0)
        assert meta.monitor == 0
        assert img.size == (1920, 1080)

    def test_capture_monitor_invalid_index(self):
        fake_img = create_test_image(1920, 1080)
        engine = ScreenshotEngine(grabber=lambda **k: fake_img)

        with pytest.raises(VisionSecurityError):
            engine.capture_monitor(-1)

    def test_capture_region_valid(self):
        fake_img = create_test_image(300, 200)
        mock_grabber = MagicMock(return_value=fake_img)
        engine = ScreenshotEngine(grabber=mock_grabber)

        img, meta = engine.capture_region(x=50, y=50, width=300, height=200)
        assert meta.width == 300
        assert meta.height == 200
        mock_grabber.assert_called_once_with(bbox=(50, 50, 350, 250))

    def test_capture_region_negative_coords(self):
        engine = ScreenshotEngine(grabber=lambda **k: create_test_image(100, 100))
        with pytest.raises(VisionSecurityError):
            engine.capture_region(x=-10, y=0, width=100, height=100)

    def test_save_screenshot_to_sandbox(self, tmp_path: Path):
        fake_img = create_test_image(640, 480, color="blue")
        engine = ScreenshotEngine(grabber=lambda **k: fake_img)

        engine.capture_primary()
        saved_path = engine.save_last_screenshot("test_screen.png", tmp_path)

        assert saved_path.exists()
        assert saved_path.name == "test_screen.png"
        assert saved_path.parent == tmp_path

        # Verify saved file is a valid image
        loaded = Image.open(saved_path)
        assert loaded.size == (640, 480)

    def test_save_screenshot_overwrite_protection(self, tmp_path: Path):
        fake_img = create_test_image(100, 100)
        engine = ScreenshotEngine(grabber=lambda **k: fake_img)

        engine.capture_primary()
        engine.save_last_screenshot("protected.png", tmp_path)

        # Overwrite without flag raises VisionSecurityError
        with pytest.raises(VisionSecurityError, match="already exists"):
            engine.save_last_screenshot("protected.png", tmp_path, overwrite=False)

        # Overwrite with flag succeeds
        overwritten = engine.save_last_screenshot("protected.png", tmp_path, overwrite=True)
        assert overwritten.exists()

    def test_screen_grab_permission_error(self):
        def failing_grab(**kwargs):
            raise OSError("screen grab failed")

        engine = ScreenshotEngine(grabber=failing_grab)
        with pytest.raises(ScreenshotPermissionError, match="permission"):
            engine.capture_primary()

    def test_empty_image_error(self):
        engine = ScreenshotEngine(grabber=lambda **k: None)
        with pytest.raises(NoDisplayAvailableError):
            engine.capture_primary()

    def test_clear_cache(self):
        fake_img = create_test_image(100, 100)
        engine = ScreenshotEngine(grabber=lambda **k: fake_img)

        engine.capture_primary()
        assert engine.last_screenshot is not None

        engine.clear_cache()
        assert engine.last_screenshot is None
        assert engine.last_metadata is None
