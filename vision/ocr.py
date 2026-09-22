"""
OCR provider abstraction and implementations for CHARVIS.
Phase 11: Screenshot & OCR.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import os
from pathlib import Path
import shutil
from typing import List, Optional

from PIL import Image
import pytesseract
from pytesseract import Output

from vision.models import (
    OCRError,
    OCRResult,
    OCRTextBlock,
    TesseractNotFoundError,
)

logger = logging.getLogger(__name__)

# Common Windows install paths for Tesseract
COMMON_TESSERACT_WINDOWS_PATHS = [
    Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
    Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
    Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe")),
    Path(os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe")),
]


class BaseOCRProvider(ABC):
    """Abstract base class for OCR engines in CHARVIS."""

    @abstractmethod
    def extract_text(
        self,
        image: Image.Image,
        max_length: Optional[int] = None,
    ) -> OCRResult:
        """
        Extract text and bounding boxes from an in-memory image.

        :param image: Pillow Image object.
        :param max_length: Maximum characters of full text to return.
        :return: Structured OCRResult.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the OCR engine binary and runtime dependencies are available."""
        pass


class TesseractOCRProvider(BaseOCRProvider):
    """Local Tesseract OCR provider using pytesseract."""

    def __init__(
        self,
        tesseract_cmd: Optional[str] = None,
        confidence_threshold: float = 0.0,
    ) -> None:
        self._confidence_threshold = confidence_threshold
        self._configured_cmd = tesseract_cmd
        self._setup_tesseract_path()

    def _setup_tesseract_path(self) -> None:
        """Resolve and configure tesseract executable path."""
        if self._configured_cmd and os.path.isfile(self._configured_cmd):
            pytesseract.pytesseract.tesseract_cmd = self._configured_cmd
            return

        # Check if tesseract is in PATH
        if shutil.which("tesseract"):
            return

        # Check common Windows installation locations
        for common_path in COMMON_TESSERACT_WINDOWS_PATHS:
            if common_path.is_file():
                pytesseract.pytesseract.tesseract_cmd = str(common_path)
                logger.info("Found Tesseract OCR at: %s", common_path)
                return

    def is_available(self) -> bool:
        """Check if Tesseract binary can be executed successfully."""
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def extract_text(
        self,
        image: Image.Image,
        max_length: Optional[int] = None,
    ) -> OCRResult:
        """
        Extract text, confidence, and bounding boxes using local Tesseract.
        """
        if not self.is_available():
            raise TesseractNotFoundError(
                "Tesseract OCR is not installed or not found in system PATH. "
                "Please install Tesseract OCR from https://github.com/UB-Mannheim/tesseract/wiki "
                "or configure 'TESSERACT_CMD' in your .env file."
            )

        if image is None:
            raise OCRError("Cannot perform OCR on a None image.")

        img_w, img_h = image.size

        try:
            data = pytesseract.image_to_data(image, output_type=Output.DICT)
        except Exception as exc:
            raise OCRError(f"Tesseract OCR execution failed: {exc}") from exc

        blocks: List[OCRTextBlock] = []
        words: List[str] = []

        n_boxes = len(data.get("text", []))
        for i in range(n_boxes):
            word = str(data["text"][i]).strip()
            conf_val = data["conf"][i]

            try:
                conf = float(conf_val)
            except (ValueError, TypeError):
                conf = -1.0

            # Ignore empty strings and negative confidence
            if word and conf >= self._confidence_threshold:
                x = int(data["left"][i])
                y = int(data["top"][i])
                w = int(data["width"][i])
                h = int(data["height"][i])

                blocks.append(
                    OCRTextBlock(
                        text=word,
                        confidence=conf,
                        x=x,
                        y=y,
                        width=w,
                        height=h,
                    )
                )
                words.append(word)

        full_text = " ".join(words)
        if max_length is not None and max_length > 0 and len(full_text) > max_length:
            full_text = full_text[:max_length] + "... [truncated]"

        return OCRResult(
            full_text=full_text,
            blocks=blocks,
            image_width=img_w,
            image_height=img_h,
        )


class MockOCRProvider(BaseOCRProvider):
    """
    Deterministic in-memory OCR provider for unit tests and offline environments.
    """

    def __init__(
        self,
        default_text: str = "CHARVIS TEST 123",
        default_confidence: float = 95.0,
        blocks: Optional[List[OCRTextBlock]] = None,
        available: bool = True,
    ) -> None:
        self._default_text = default_text
        self._default_confidence = default_confidence
        self._blocks = blocks
        self._available = available
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def set_available(self, available: bool) -> None:
        self._available = available

    def set_mock_response(
        self,
        text: str,
        confidence: float = 95.0,
        blocks: Optional[List[OCRTextBlock]] = None,
    ) -> None:
        self._default_text = text
        self._default_confidence = confidence
        self._blocks = blocks

    def is_available(self) -> bool:
        return self._available

    def extract_text(
        self,
        image: Image.Image,
        max_length: Optional[int] = None,
    ) -> OCRResult:
        self._call_count += 1
        if not self._available:
            raise TesseractNotFoundError("Mock Tesseract is configured as unavailable.")

        img_w = image.size[0] if image else 1920
        img_h = image.size[1] if image else 1080

        full_text = self._default_text
        if max_length is not None and max_length > 0 and len(full_text) > max_length:
            full_text = full_text[:max_length] + "... [truncated]"

        if self._blocks is not None:
            blocks = list(self._blocks)
        else:
            # Generate sample blocks from whitespace-delimited words
            blocks = []
            words = self._default_text.split()
            x_offset = 100
            for idx, word in enumerate(words):
                w = max(10, len(word) * 12)
                blocks.append(
                    OCRTextBlock(
                        text=word,
                        confidence=self._default_confidence,
                        x=x_offset,
                        y=150,
                        width=w,
                        height=24,
                    )
                )
                x_offset += w + 15

        return OCRResult(
            full_text=full_text,
            blocks=blocks,
            image_width=img_w,
            image_height=img_h,
        )


def get_ocr_provider(provider_type: str = "tesseract", **kwargs) -> BaseOCRProvider:
    """
    Factory function returning the configured OCR provider.
    """
    p_type = provider_type.lower().strip()
    if p_type == "mock":
        return MockOCRProvider(**kwargs)
    return TesseractOCRProvider(**kwargs)
