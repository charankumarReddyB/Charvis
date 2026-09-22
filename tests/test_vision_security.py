"""
Unit tests for CHARVIS Vision Security and Validation.
Phase 11: Screenshot & OCR.
"""

from pathlib import Path
import pytest

from vision.models import (
    MalformedVisionOutputError,
    VisionCloudDisabledError,
    VisionSecurityError,
)
from vision.security import (
    check_cloud_vision_allowed,
    sanitize_ocr_text_for_logging,
    validate_monitor_index,
    validate_region_coordinates,
    validate_screen_description,
    validate_screen_element,
    validate_screenshot_save_path,
)


class TestVisionSecurityCoordinates:
    """Tests for coordinate and region boundary validation."""

    def test_valid_region_passes(self):
        x, y, w, h = validate_region_coordinates(
            x=100, y=200, width=500, height=400,
            screen_width=1920, screen_height=1080,
        )
        assert (x, y, w, h) == (100, 200, 500, 400)

    def test_negative_coordinates_rejected(self):
        with pytest.raises(VisionSecurityError, match="negative"):
            validate_region_coordinates(x=-10, y=50, width=100, height=100, screen_width=1920, screen_height=1080)

        with pytest.raises(VisionSecurityError, match="negative"):
            validate_region_coordinates(x=50, y=-5, width=100, height=100, screen_width=1920, screen_height=1080)

    def test_zero_dimensions_rejected(self):
        with pytest.raises(VisionSecurityError, match="strictly positive"):
            validate_region_coordinates(x=0, y=0, width=0, height=100, screen_width=1920, screen_height=1080)

        with pytest.raises(VisionSecurityError, match="strictly positive"):
            validate_region_coordinates(x=0, y=0, width=100, height=0, screen_width=1920, screen_height=1080)

    def test_negative_dimensions_rejected(self):
        with pytest.raises(VisionSecurityError, match="strictly positive"):
            validate_region_coordinates(x=0, y=0, width=-50, height=100, screen_width=1920, screen_height=1080)

    def test_non_integer_rejected(self):
        with pytest.raises(VisionSecurityError, match="integers"):
            validate_region_coordinates(x="10", y=0, width=100, height=100, screen_width=1920, screen_height=1080)  # type: ignore

    def test_out_of_bounds_width_rejected(self):
        with pytest.raises(VisionSecurityError, match="exceeds screen width"):
            validate_region_coordinates(x=1500, y=0, width=500, height=200, screen_width=1920, screen_height=1080)

    def test_out_of_bounds_height_rejected(self):
        with pytest.raises(VisionSecurityError, match="exceeds screen height"):
            validate_region_coordinates(x=0, y=1000, width=500, height=200, screen_width=1920, screen_height=1080)

    def test_oversized_region_area_rejected(self):
        with pytest.raises(VisionSecurityError, match="exceeds maximum allowed"):
            validate_region_coordinates(x=0, y=0, width=2000, height=2000, screen_width=4000, screen_height=4000, max_area=1_000_000)


class TestVisionSecurityMonitors:
    """Tests for display monitor index validation."""

    def test_valid_monitor_passes(self):
        assert validate_monitor_index(0, available_monitors=2) == 0
        assert validate_monitor_index(1, available_monitors=2) == 1

    def test_negative_monitor_rejected(self):
        with pytest.raises(VisionSecurityError, match="negative"):
            validate_monitor_index(-1, available_monitors=2)

    def test_out_of_range_monitor_rejected(self):
        with pytest.raises(VisionSecurityError, match="out of range"):
            validate_monitor_index(2, available_monitors=2)

    def test_non_integer_monitor_rejected(self):
        with pytest.raises(VisionSecurityError, match="integer"):
            validate_monitor_index("primary", available_monitors=2)  # type: ignore


class TestVisionSecuritySavePath:
    """Tests for screenshot filename and sandbox path validation."""

    def test_valid_filename_saved_in_sandbox(self, tmp_path: Path):
        sandbox = tmp_path / "workspace"
        sandbox.mkdir()
        result = validate_screenshot_save_path("capture1.png", sandbox)
        assert result == sandbox / "capture1.png"

    def test_default_png_extension_added_if_omitted(self, tmp_path: Path):
        sandbox = tmp_path / "workspace"
        sandbox.mkdir()
        result = validate_screenshot_save_path("my_capture", sandbox)
        assert result.suffix == ".png"

    def test_allowed_extensions_pass(self, tmp_path: Path):
        sandbox = tmp_path / "workspace"
        sandbox.mkdir()
        jpg_path = validate_screenshot_save_path("pic.jpg", sandbox)
        assert jpg_path.suffix == ".jpg"
        jpeg_path = validate_screenshot_save_path("pic.jpeg", sandbox)
        assert jpeg_path.suffix == ".jpeg"

    def test_disallowed_extension_rejected(self, tmp_path: Path):
        sandbox = tmp_path / "workspace"
        sandbox.mkdir()
        with pytest.raises(VisionSecurityError, match="Invalid screenshot file extension"):
            validate_screenshot_save_path("evil.exe", sandbox)

    def test_path_traversal_rejected(self, tmp_path: Path):
        sandbox = tmp_path / "workspace"
        sandbox.mkdir()
        with pytest.raises(VisionSecurityError, match="Path traversal"):
            validate_screenshot_save_path("../escape.png", sandbox)

        with pytest.raises(VisionSecurityError, match="Path traversal"):
            validate_screenshot_save_path("sub/../../escape.png", sandbox)

    def test_absolute_path_outside_sandbox_rejected(self, tmp_path: Path):
        sandbox = tmp_path / "workspace"
        sandbox.mkdir()
        with pytest.raises(VisionSecurityError, match="outside sandbox"):
            validate_screenshot_save_path("C:/Windows/System32/hacked.png", sandbox)

    def test_empty_filename_rejected(self, tmp_path: Path):
        sandbox = tmp_path / "workspace"
        sandbox.mkdir()
        with pytest.raises(VisionSecurityError, match="cannot be empty"):
            validate_screenshot_save_path("", sandbox)


class TestVisionSecuritySanitization:
    """Tests for diagnostic OCR text redaction."""

    def test_sk_api_key_redacted(self):
        text = "My secret OpenAI key is sk-1234567890abcdef1234567890abcdef."
        sanitized = sanitize_ocr_text_for_logging(text)
        assert "sk-1234567890" not in sanitized
        assert "sk-***REDACTED***" in sanitized

    def test_credit_card_redacted(self):
        text = "Card number 4111 2222 3333 4444 expires 12/28"
        sanitized = sanitize_ocr_text_for_logging(text)
        assert "4111 2222 3333 4444" not in sanitized
        assert "***CARD-REDACTED***" in sanitized

    def test_password_redacted(self):
        text = "Login with password: SuperSecretPassword123"
        sanitized = sanitize_ocr_text_for_logging(text)
        assert "SuperSecretPassword123" not in sanitized
        assert "password=***REDACTED***" in sanitized


class TestVisionCloudSecurity:
    """Tests for cloud vision permission checks and boundaries."""

    def test_cloud_vision_disabled_by_default_raises_error(self):
        from config import Settings
        settings = Settings(vision_cloud_enabled=False)
        with pytest.raises(VisionCloudDisabledError, match="Cloud vision is disabled by default"):
            check_cloud_vision_allowed(settings)

    def test_cloud_vision_enabled_passes(self):
        from config import Settings
        settings = Settings(vision_cloud_enabled=True)
        # Should not raise
        check_cloud_vision_allowed(settings)


class TestScreenUnderstandingValidation:
    """Tests for raw vision model output parsing, schema validation, and bounds enforcement."""

    def test_valid_screen_element_passes(self):
        elem = validate_screen_element(
            elem_dict={
                "element_type": "button",
                "label": "Click Me",
                "text": "Click",
                "confidence": 0.95,
                "x": 100,
                "y": 150,
                "width": 60,
                "height": 30,
            },
            max_width=1920,
            max_height=1080,
        )
        assert elem.element_type == "button"
        assert elem.label == "Click Me"
        assert elem.confidence == 0.95
        assert elem.x == 100
        assert elem.y == 150
        assert elem.width == 60
        assert elem.height == 30

    def test_unknown_element_type_falls_back_to_unknown(self):
        elem = validate_screen_element(
            elem_dict={
                "element_type": "alien_spaceship_widget",
                "label": "Test",
                "confidence": 0.5,
                "x": 10,
                "y": 10,
                "width": 50,
                "height": 20,
            },
            max_width=1920,
            max_height=1080,
        )
        assert elem.element_type == "unknown"

    def test_negative_coordinates_rejected(self):
        with pytest.raises(MalformedVisionOutputError, match="negative"):
            validate_screen_element(
                elem_dict={"x": -5, "y": 10, "width": 50, "height": 20},
                max_width=1920,
                max_height=1080,
            )

    def test_zero_dimensions_rejected(self):
        with pytest.raises(MalformedVisionOutputError, match="strictly positive"):
            validate_screen_element(
                elem_dict={"x": 10, "y": 10, "width": 0, "height": 20},
                max_width=1920,
                max_height=1080,
            )

    def test_out_of_bounds_origin_rejected(self):
        with pytest.raises(MalformedVisionOutputError, match="exceeds screen dimensions"):
            validate_screen_element(
                elem_dict={"x": 2000, "y": 10, "width": 50, "height": 20},
                max_width=1920,
                max_height=1080,
            )

    def test_confidence_normalization(self):
        # Passed as percentage 0..100
        elem = validate_screen_element(
            elem_dict={"x": 0, "y": 0, "width": 10, "height": 10, "confidence": 95.0},
            max_width=1920,
            max_height=1080,
        )
        assert elem.confidence == 0.95

    def test_label_length_clamping(self):
        long_label = "A" * 300
        elem = validate_screen_element(
            elem_dict={"x": 0, "y": 0, "width": 10, "height": 10, "label": long_label},
            max_width=1920,
            max_height=1080,
            max_label_len=50,
        )
        assert len(elem.label) == 50

    def test_validate_screen_description_valid_dict(self):
        payload = {
            "screen_width": 1920,
            "screen_height": 1080,
            "application": "Notepad",
            "title": "Untitled",
            "summary": "Notepad window active.",
            "confidence": 0.88,
            "elements": [
                {"element_type": "button", "label": "Save", "confidence": 0.9, "x": 10, "y": 10, "width": 40, "height": 20},
                {"element_type": "text", "label": "File", "confidence": 0.85, "x": 50, "y": 10, "width": 30, "height": 20},
            ],
        }
        desc = validate_screen_description(payload, max_width=1920, max_height=1080)
        assert desc.screen_width == 1920
        assert desc.application == "Notepad"
        assert len(desc.elements) == 2
        assert desc.summary == "Notepad window active."

    def test_validate_screen_description_valid_json_string(self):
        import json
        payload = json.dumps({
            "screen_width": 1280,
            "screen_height": 720,
            "application": "Chrome",
            "elements": [],
            "summary": "Chrome browser.",
            "confidence": 0.9,
        })
        desc = validate_screen_description(payload, max_width=1280, max_height=720)
        assert desc.application == "Chrome"
        assert desc.screen_width == 1280

    def test_validate_screen_description_caps_elements(self):
        raw_elements = [
            {"element_type": "text", "label": f"Word_{i}", "confidence": float(i) / 100.0, "x": 0, "y": 0, "width": 10, "height": 10}
            for i in range(50)
        ]
        payload = {
            "elements": raw_elements,
            "summary": "Lots of elements",
        }
        desc = validate_screen_description(payload, max_width=1920, max_height=1080, max_elements=10)
        assert len(desc.elements) == 10
        # Check sorted by confidence descending
        assert desc.elements[0].confidence >= desc.elements[-1].confidence

    def test_validate_screen_description_invalid_json_rejected(self):
        with pytest.raises(MalformedVisionOutputError, match="Failed to parse vision model JSON"):
            validate_screen_description("NOT VALID JSON", max_width=1920, max_height=1080)

    def test_validate_screen_description_invalid_type_rejected(self):
        with pytest.raises(MalformedVisionOutputError, match="JSON object/dictionary"):
            validate_screen_description([1, 2, 3], max_width=1920, max_height=1080)

