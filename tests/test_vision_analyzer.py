"""
Unit tests for CHARVIS VisionAnalyzer orchestrator.
Phase 12: Vision / Screen Understanding.
"""

from unittest.mock import MagicMock
from PIL import Image
import pytest

from vision.analyzer import VisionAnalyzer
from vision.models import (
    OCRResult,
    OCRTextBlock,
    ScreenDescription,
    ScreenElement,
)
from vision.ocr import MockOCRProvider
from vision.providers import MockVisionProvider
from vision.screenshot import ScreenshotEngine


@pytest.fixture
def fake_desktop_image() -> Image.Image:
    return Image.new("RGB", (1920, 1080), color="white")


@pytest.fixture
def sample_screen_description() -> ScreenDescription:
    return ScreenDescription(
        screen_width=1920,
        screen_height=1080,
        application="Notepad",
        title="Untitled - Notepad",
        elements=[
            ScreenElement(
                element_type="window",
                label="Notepad Window",
                text="Untitled - Notepad",
                confidence=0.98,
                x=0,
                y=0,
                width=1920,
                height=1080,
            ),
            ScreenElement(
                element_type="button",
                label="Settings",
                text="Settings",
                confidence=0.95,
                x=1800,
                y=20,
                width=40,
                height=40,
            ),
            ScreenElement(
                element_type="button",
                label="Save",
                text="Save",
                confidence=0.92,
                x=100,
                y=60,
                width=50,
                height=25,
            ),
            ScreenElement(
                element_type="input",
                label="Find",
                text="Search text",
                confidence=0.88,
                x=200,
                y=60,
                width=150,
                height=25,
            ),
        ],
        summary="Notepad application with Settings button, Save button, and Find input.",
        confidence=0.95,
    )


@pytest.fixture
def mock_analyzer(
    fake_desktop_image: Image.Image,
    sample_screen_description: ScreenDescription,
) -> VisionAnalyzer:
    mock_screenshot = ScreenshotEngine(grabber=lambda **k: fake_desktop_image)
    mock_ocr = MockOCRProvider(default_text="Notepad Save Find Settings")
    mock_provider = MockVisionProvider(default_description=sample_screen_description)

    return VisionAnalyzer(
        screenshot_engine=mock_screenshot,
        ocr_provider=mock_ocr,
        vision_provider=mock_provider,
    )


class TestVisionAnalyzerFullScreen:
    """Tests for full screen analysis."""

    def test_analyze_full_screen(self, mock_analyzer: VisionAnalyzer):
        desc = mock_analyzer.analyze_full_screen(context="what application is open")

        assert desc.application == "Notepad"
        assert desc.screen_width == 1920
        assert desc.screen_height == 1080
        assert len(desc.elements) == 4
        assert mock_analyzer.last_description is desc

    def test_describe_screen(self, mock_analyzer: VisionAnalyzer):
        summary = mock_analyzer.describe_screen()
        assert "Notepad" in summary
        assert "Settings" in summary

    def test_get_screen_elements(self, mock_analyzer: VisionAnalyzer):
        elements = mock_analyzer.get_screen_elements()
        assert len(elements) == 4
        labels = [e["label"] for e in elements]
        assert "Settings" in labels
        assert "Save" in labels

    def test_clear_cache(self, mock_analyzer: VisionAnalyzer):
        mock_analyzer.analyze_full_screen()
        assert mock_analyzer.last_description is not None
        mock_analyzer.clear_cache()
        assert mock_analyzer.last_description is None


class TestVisionAnalyzerRegion:
    """Tests for bounded region visual analysis."""

    def test_analyze_region_offsets_coordinates(self, mock_analyzer: VisionAnalyzer):
        # Region starting at x=100, y=50
        desc = mock_analyzer.analyze_region(x=100, y=50, width=500, height=400)

        assert desc.screen_width == 500
        assert desc.screen_height == 400

        # Elements should be offset by x=100, y=50
        # In sample_screen_description, Save was at x=100, y=60
        save_elem = [e for e in desc.elements if e.label == "Save"][0]
        assert save_elem.x == 100 + 100  # 200
        assert save_elem.y == 60 + 50    # 110


class TestVisionAnalyzerFindElement:
    """Tests for find_element query resolution (Perception Only)."""

    def test_find_element_by_label(self, mock_analyzer: VisionAnalyzer):
        res = mock_analyzer.find_element("Settings")
        assert res["success"] is True
        assert res["found"] is True
        assert res["match_count"] >= 1
        first = res["matches"][0]
        assert first["label"] == "Settings"
        assert first["element_type"] == "button"
        assert first["x"] == 1800
        assert first["y"] == 20

    def test_find_element_by_type(self, mock_analyzer: VisionAnalyzer):
        res = mock_analyzer.find_element("button")
        assert res["success"] is True
        assert res["found"] is True
        assert res["match_count"] == 2  # Settings and Save

    def test_find_element_not_found(self, mock_analyzer: VisionAnalyzer):
        res = mock_analyzer.find_element("NonExistentCalculatorWidget")
        assert res["success"] is True
        assert res["found"] is False
        assert res["match_count"] == 0
        assert "not detected" in res["message"]

    def test_find_element_empty_query(self, mock_analyzer: VisionAnalyzer):
        res = mock_analyzer.find_element("   ")
        assert res["success"] is False
        assert "empty" in res["error"]

    def test_find_element_is_perception_only(self, mock_analyzer: VisionAnalyzer):
        """Verify find_element locates coordinates and does not interact."""
        res = mock_analyzer.find_element("Save")
        assert res["found"] is True
        # Verify returned data contains only perception metadata
        match = res["matches"][0]
        assert "x" in match
        assert "y" in match
        assert "width" in match
        assert "height" in match
        assert "confidence" in match
