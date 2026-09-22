"""
Unit tests for CHARVIS Vision Providers (Mock, Local Heuristics, and Cloud).
Phase 12: Vision / Screen Understanding.
"""

from unittest.mock import MagicMock, patch
from PIL import Image
import pytest

from config import Settings
from vision.models import (
    OCRResult,
    OCRTextBlock,
    ScreenDescription,
    ScreenElement,
    VisionCloudDisabledError,
    VisionModelError,
    VisionProviderUnavailableError,
    VisionTimeoutError,
)
from vision.providers import (
    LocalHeuristicVisionProvider,
    MockVisionProvider,
    OpenAIVisionProvider,
    get_vision_provider,
)


@pytest.fixture
def sample_image() -> Image.Image:
    return Image.new("RGB", (1280, 720), color="white")


@pytest.fixture
def notepad_ocr_result() -> OCRResult:
    return OCRResult(
        full_text="Untitled - Notepad File Edit View Help Save Cancel",
        blocks=[
            OCRTextBlock("Untitled", 95.0, 50, 10, 80, 20),
            OCRTextBlock("-", 90.0, 135, 10, 10, 20),
            OCRTextBlock("Notepad", 98.0, 150, 10, 70, 20),
            OCRTextBlock("File", 90.0, 50, 40, 30, 18),
            OCRTextBlock("Edit", 90.0, 90, 40, 30, 18),
            OCRTextBlock("Save", 96.0, 100, 200, 50, 25),
            OCRTextBlock("Cancel", 94.0, 160, 200, 60, 25),
        ],
        image_width=1280,
        image_height=720,
    )


class TestMockVisionProvider:
    """Tests for MockVisionProvider."""

    def test_default_response(self, sample_image: Image.Image):
        provider = MockVisionProvider()
        desc = provider.analyze(sample_image)

        assert desc.screen_width == 1280
        assert desc.screen_height == 720
        assert desc.application == "MockApp"
        assert provider.call_count == 1
        assert provider.last_image is sample_image

    def test_custom_response(self, sample_image: Image.Image):
        custom = ScreenDescription(
            screen_width=1280,
            screen_height=720,
            application="CustomApp",
            title="Custom Title",
            summary="Custom summary.",
            confidence=0.99,
        )
        provider = MockVisionProvider(default_description=custom)
        res = provider.analyze(sample_image)
        assert res.application == "CustomApp"
        assert res.confidence == 0.99

    def test_simulated_error(self, sample_image: Image.Image):
        provider = MockVisionProvider()
        provider.set_error(VisionModelError("Simulated provider crash"))

        with pytest.raises(VisionModelError, match="Simulated provider crash"):
            provider.analyze(sample_image)

    def test_unavailable_provider(self, sample_image: Image.Image):
        provider = MockVisionProvider(available=False)
        with pytest.raises(VisionProviderUnavailableError):
            provider.analyze(sample_image)


class TestLocalHeuristicVisionProvider:
    """Tests for LocalHeuristicVisionProvider (100% private, zero network)."""

    def test_application_and_button_detection(
        self, sample_image: Image.Image, notepad_ocr_result: OCRResult
    ):
        settings = Settings(vision_cloud_enabled=False)
        provider = LocalHeuristicVisionProvider(settings=settings)

        desc = provider.analyze(
            image=sample_image,
            context="check notepad",
            ocr_result=notepad_ocr_result,
        )

        assert desc.screen_width == 1280
        assert desc.screen_height == 720
        assert desc.application == "Notepad"
        assert "Notepad" in desc.title
        assert len(desc.elements) > 0

        # Check detected buttons
        buttons = [e for e in desc.elements if e.element_type == "button"]
        button_labels = {b.label.lower() for b in buttons}
        assert "save" in button_labels
        assert "cancel" in button_labels

        # Check window element
        windows = [e for e in desc.elements if e.element_type == "window"]
        assert len(windows) >= 1

        # Check summary contains active app
        assert "Notepad" in desc.summary

    def test_none_image_rejected(self):
        provider = LocalHeuristicVisionProvider()
        with pytest.raises(VisionModelError, match="Cannot analyze a None image"):
            provider.analyze(image=None)  # type: ignore

    def test_empty_ocr_blocks_fallback(self, sample_image: Image.Image):
        provider = LocalHeuristicVisionProvider()
        desc = provider.analyze(
            image=sample_image,
            ocr_result=OCRResult(full_text="", blocks=[]),
        )
        assert desc.application == "unknown"
        assert desc.screen_width == 1280


class TestOpenAIVisionProviderSecurity:
    """Tests for OpenAIVisionProvider cloud permission and security rules."""

    def test_cloud_vision_disabled_blocks_transmission(self, sample_image: Image.Image):
        settings = Settings(vision_cloud_enabled=False, openai_api_key="sk-test1234567890abcdef")
        provider = OpenAIVisionProvider(settings=settings)

        assert provider.is_available() is False
        with pytest.raises(VisionCloudDisabledError, match="Cloud vision is disabled by default"):
            provider.analyze(sample_image)

    def test_missing_api_key_blocks_transmission(self, sample_image: Image.Image):
        settings = Settings(vision_cloud_enabled=True, openai_api_key=None)
        provider = OpenAIVisionProvider(settings=settings)

        with pytest.raises(VisionProviderUnavailableError, match="OPENAI_API_KEY is not configured"):
            provider.analyze(sample_image)

    def test_successful_mocked_cloud_call(self, sample_image: Image.Image):
        settings = Settings(
            vision_cloud_enabled=True,
            openai_api_key="sk-test1234567890abcdef12345678",
        )
        import json

        mock_payload = {
            "screen_width": 1280,
            "screen_height": 720,
            "application": "Edge",
            "title": "Welcome to Edge",
            "elements": [
                {"element_type": "button", "label": "Search", "confidence": 0.95, "x": 100, "y": 100, "width": 50, "height": 30}
            ],
            "summary": "Edge browser window.",
            "confidence": 0.92,
        }

        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps(mock_payload)
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion

        provider = OpenAIVisionProvider(settings=settings, client=mock_client)
        assert provider.is_available() is True

        desc = provider.analyze(sample_image)
        assert desc.application == "Edge"
        assert len(desc.elements) == 1
        assert desc.elements[0].label == "Search"


class TestVisionProviderFactory:
    """Tests for get_vision_provider factory function."""

    def test_factory_mock(self):
        p = get_vision_provider("mock")
        assert isinstance(p, MockVisionProvider)

    def test_factory_local(self):
        p = get_vision_provider("local")
        assert isinstance(p, LocalHeuristicVisionProvider)

    def test_factory_openai(self):
        p = get_vision_provider("openai")
        assert isinstance(p, OpenAIVisionProvider)
