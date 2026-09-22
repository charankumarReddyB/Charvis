"""
Unit tests for CHARVIS OCR Provider Layer.
Phase 11: Screenshot & OCR.
"""

from unittest.mock import MagicMock, patch
from PIL import Image
import pytest

from vision.models import (
    OCRError,
    OCRResult,
    OCRTextBlock,
    TesseractNotFoundError,
)
from vision.ocr import (
    BaseOCRProvider,
    MockOCRProvider,
    TesseractOCRProvider,
    get_ocr_provider,
)


def create_blank_image(width: int = 400, height: int = 200) -> Image.Image:
    return Image.new("RGB", (width, height), color="white")


class TestOCRModels:
    """Tests for OCRTextBlock and OCRResult data models."""

    def test_ocr_text_block_to_dict(self):
        block = OCRTextBlock(
            text="Hello",
            confidence=98.543,
            x=10,
            y=20,
            width=50,
            height=15,
        )
        d = block.to_dict()
        assert d["text"] == "Hello"
        assert d["confidence"] == 98.54
        assert d["x"] == 10
        assert d["y"] == 20
        assert d["width"] == 50
        assert d["height"] == 15

    def test_ocr_result_to_dict(self):
        blocks = [
            OCRTextBlock("CHARVIS", 99.0, 10, 10, 80, 20),
            OCRTextBlock("TEST", 95.5, 100, 10, 50, 20),
        ]
        result = OCRResult(
            full_text="CHARVIS TEST",
            blocks=blocks,
            image_width=800,
            image_height=600,
        )
        d = result.to_dict()
        assert d["full_text"] == "CHARVIS TEST"
        assert d["block_count"] == 2
        assert len(d["blocks"]) == 2
        assert d["image_width"] == 800
        assert d["image_height"] == 600


class TestMockOCRProvider:
    """Tests for the deterministic MockOCRProvider."""

    def test_default_mock_response(self):
        provider = MockOCRProvider()
        assert provider.is_available() is True

        img = create_blank_image(600, 300)
        res = provider.extract_text(img)

        assert res.full_text == "CHARVIS TEST 123"
        assert len(res.blocks) == 3
        assert res.blocks[0].text == "CHARVIS"
        assert res.blocks[1].text == "TEST"
        assert res.blocks[2].text == "123"
        assert res.image_width == 600
        assert res.image_height == 300

    def test_custom_mock_text(self):
        provider = MockOCRProvider()
        provider.set_mock_response(
            text="Start Button Here",
            confidence=88.0,
        )
        img = create_blank_image()
        res = provider.extract_text(img)

        assert res.full_text == "Start Button Here"
        assert len(res.blocks) == 3
        assert res.blocks[0].confidence == 88.0

    def test_text_length_limit(self):
        long_text = "Word " * 200
        provider = MockOCRProvider(default_text=long_text)
        img = create_blank_image()
        res = provider.extract_text(img, max_length=50)

        assert len(res.full_text) <= 75  # includes '... [truncated]' suffix
        assert "[truncated]" in res.full_text

    def test_mock_unavailable_raises(self):
        provider = MockOCRProvider(available=False)
        assert provider.is_available() is False
        img = create_blank_image()

        with pytest.raises(TesseractNotFoundError):
            provider.extract_text(img)


class TestTesseractOCRProvider:
    """Tests for TesseractOCRProvider."""

    def test_unavailable_tesseract_raises_cleanly(self):
        with patch("pytesseract.get_tesseract_version", side_effect=Exception("Not found")):
            provider = TesseractOCRProvider()
            assert provider.is_available() is False

            img = create_blank_image()
            with pytest.raises(TesseractNotFoundError, match="Tesseract OCR is not installed"):
                provider.extract_text(img)

    def test_tesseract_output_parsing(self):
        mock_data = {
            "text": ["", "Login", "", "Password"],
            "conf": ["-1", "95", "-1", "90"],
            "left": [0, 100, 0, 100],
            "top": [0, 50, 0, 90],
            "width": [0, 60, 0, 80],
            "height": [0, 20, 0, 20],
        }

        with patch("pytesseract.get_tesseract_version", return_value="5.4.0"), \
             patch("pytesseract.image_to_data", return_value=mock_data):
            provider = TesseractOCRProvider()
            assert provider.is_available() is True

            img = create_blank_image(800, 600)
            res = provider.extract_text(img)

            assert res.full_text == "Login Password"
            assert len(res.blocks) == 2
            assert res.blocks[0].text == "Login"
            assert res.blocks[0].confidence == 95.0
            assert res.blocks[0].x == 100
            assert res.blocks[1].text == "Password"
            assert res.blocks[1].confidence == 90.0

    def test_none_image_raises_ocr_error(self):
        with patch("pytesseract.get_tesseract_version", return_value="5.4.0"):
            provider = TesseractOCRProvider()
            with pytest.raises(OCRError, match="None image"):
                provider.extract_text(None)  # type: ignore


class TestOCRProviderFactory:
    """Tests for get_ocr_provider factory."""

    def test_factory_returns_mock(self):
        prov = get_ocr_provider("mock", default_text="Test Mock")
        assert isinstance(prov, MockOCRProvider)
        assert prov.extract_text(create_blank_image()).full_text == "Test Mock"

    def test_factory_returns_tesseract(self):
        prov = get_ocr_provider("tesseract")
        assert isinstance(prov, TesseractOCRProvider)
