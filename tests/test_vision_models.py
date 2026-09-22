"""
Unit tests for CHARVIS Vision Models and Exception Hierarchy.
Phase 12: Vision / Screen Understanding.
"""

import pytest

from vision.models import (
    MalformedVisionOutputError,
    NoDisplayAvailableError,
    OCRError,
    OCRResult,
    OCRTextBlock,
    SUPPORTED_ELEMENT_TYPES,
    ScreenDescription,
    ScreenElement,
    ScreenshotError,
    ScreenshotMetadata,
    ScreenshotPermissionError,
    TesseractNotFoundError,
    VisionCloudDisabledError,
    VisionError,
    VisionModelError,
    VisionProviderUnavailableError,
    VisionSecurityError,
    VisionTimeoutError,
)


class TestVisionExceptions:
    """Verify custom exception inheritance and hierarchy."""

    def test_base_inheritance(self):
        assert issubclass(ScreenshotError, VisionError)
        assert issubclass(ScreenshotPermissionError, ScreenshotError)
        assert issubclass(NoDisplayAvailableError, ScreenshotError)
        assert issubclass(OCRError, VisionError)
        assert issubclass(TesseractNotFoundError, OCRError)
        assert issubclass(VisionSecurityError, VisionError)
        assert issubclass(VisionCloudDisabledError, VisionSecurityError)
        assert issubclass(VisionModelError, VisionError)
        assert issubclass(VisionTimeoutError, VisionModelError)
        assert issubclass(MalformedVisionOutputError, VisionModelError)
        assert issubclass(VisionProviderUnavailableError, VisionModelError)


class TestSupportedElementTypes:
    """Verify supported element types set."""

    def test_essential_types_present(self):
        essential = {
            "window", "button", "text", "input", "checkbox",
            "radio", "dropdown", "menu", "icon", "image",
            "dialog", "tab", "link", "unknown",
        }
        assert essential.issubset(SUPPORTED_ELEMENT_TYPES)


class TestScreenElementModel:
    """Verify ScreenElement dataclass and serialization."""

    def test_screen_element_creation_and_to_dict(self):
        elem = ScreenElement(
            element_type="button",
            label="Save Document",
            text="Save",
            confidence=0.9234,
            x=150,
            y=250,
            width=85,
            height=32,
        )

        d = elem.to_dict()
        assert d["element_type"] == "button"
        assert d["label"] == "Save Document"
        assert d["text"] == "Save"
        assert d["confidence"] == 0.923
        assert d["x"] == 150
        assert d["y"] == 250
        assert d["width"] == 85
        assert d["height"] == 32

    def test_default_screen_element(self):
        elem = ScreenElement()
        assert elem.element_type == "unknown"
        assert elem.label == ""
        assert elem.text == ""
        assert elem.confidence == 0.0
        assert elem.x == 0
        assert elem.y == 0
        assert elem.width == 0
        assert elem.height == 0


class TestScreenDescriptionModel:
    """Verify ScreenDescription dataclass and serialization."""

    def test_screen_description_creation_and_to_dict(self):
        elem1 = ScreenElement(
            element_type="button",
            label="OK",
            text="OK",
            confidence=0.95,
            x=100,
            y=200,
            width=50,
            height=25,
        )
        elem2 = ScreenElement(
            element_type="input",
            label="Search",
            text="",
            confidence=0.80,
            x=160,
            y=200,
            width=120,
            height=25,
        )

        desc = ScreenDescription(
            screen_width=1920,
            screen_height=1080,
            application="Notepad",
            title="Untitled - Notepad",
            elements=[elem1, elem2],
            summary="Notepad window with OK button and Search input.",
            confidence=0.88,
        )

        d = desc.to_dict()
        assert d["screen_width"] == 1920
        assert d["screen_height"] == 1080
        assert d["application"] == "Notepad"
        assert d["title"] == "Untitled - Notepad"
        assert d["element_count"] == 2
        assert len(d["elements"]) == 2
        assert d["elements"][0]["label"] == "OK"
        assert d["elements"][1]["element_type"] == "input"
        assert d["summary"] == "Notepad window with OK button and Search input."
        assert d["confidence"] == 0.88

    def test_screen_description_defaults(self):
        desc = ScreenDescription(
            screen_width=1280,
            screen_height=720,
        )
        d = desc.to_dict()
        assert d["application"] == "unknown"
        assert d["title"] == ""
        assert d["element_count"] == 0
        assert d["elements"] == []
        assert d["summary"] == ""
        assert d["confidence"] == 0.0
