"""
Data models and custom exception hierarchy for CHARVIS Vision and OCR.
Phase 11: Screenshot & OCR.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class VisionError(Exception):
    """Base exception for all CHARVIS vision subsystem errors."""
    pass


class ScreenshotError(VisionError):
    """Raised when desktop or region screenshot capture fails."""
    pass


class ScreenshotPermissionError(ScreenshotError):
    """Raised when the process lacks permission or session access to capture the display."""
    pass


class NoDisplayAvailableError(ScreenshotError):
    """Raised when no desktop display or active monitor is detected."""
    pass


class OCRError(VisionError):
    """Base exception for OCR recognition and processing failures."""
    pass


class TesseractNotFoundError(OCRError):
    """Raised when the local Tesseract OCR executable is not found or not installed."""
    pass


class VisionSecurityError(VisionError):
    """Raised when a screenshot or OCR request violates coordinate, sandbox, or size limits."""
    pass


class VisionCloudDisabledError(VisionSecurityError):
    """Raised when an attempt is made to transmit screenshots to a cloud API while cloud vision is disabled."""
    pass


class VisionModelError(VisionError):
    """Base exception for vision model inference or execution failures."""
    pass


class VisionTimeoutError(VisionModelError):
    """Raised when a vision provider model request times out."""
    pass


class MalformedVisionOutputError(VisionModelError):
    """Raised when vision provider returns invalid, unparseable, or schema-violating data."""
    pass


class VisionProviderUnavailableError(VisionModelError):
    """Raised when the requested vision provider backend is not installed, configured, or reachable."""
    pass


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class OCRTextBlock:
    """Represents a single word or recognized text element with bounding box and confidence."""
    text: str
    confidence: float  # Normalized 0.0 to 100.0
    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert block to dictionary."""
        return {
            "text": self.text,
            "confidence": round(self.confidence, 2),
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class OCRResult:
    """Structured representation of OCR recognition output."""
    full_text: str
    blocks: List[OCRTextBlock] = field(default_factory=list)
    image_width: int = 0
    image_height: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert OCR result to dictionary."""
        return {
            "full_text": self.full_text,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "block_count": len(self.blocks),
            "blocks": [b.to_dict() for b in self.blocks],
        }


@dataclass
class ScreenshotMetadata:
    """Metadata describing an in-memory or saved screenshot."""
    width: int
    height: int
    monitor: int
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Screen Understanding Models (Phase 12)
# ---------------------------------------------------------------------------

SUPPORTED_ELEMENT_TYPES = {
    "window",
    "button",
    "text",
    "input",
    "checkbox",
    "radio",
    "dropdown",
    "menu",
    "icon",
    "image",
    "dialog",
    "tab",
    "link",
    "unknown",
}


@dataclass
class ScreenElement:
    """Represents a structured visual UI element detected on screen."""
    element_type: str = "unknown"
    label: str = ""
    text: str = ""
    confidence: float = 0.0  # 0.0 to 1.0
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert screen element to dictionary."""
        return {
            "element_type": self.element_type,
            "label": self.label,
            "text": self.text,
            "confidence": round(float(self.confidence), 3),
            "x": int(self.x),
            "y": int(self.y),
            "width": int(self.width),
            "height": int(self.height),
        }


@dataclass
class ScreenDescription:
    """Structured representation of an analyzed screen or bounded region."""
    screen_width: int
    screen_height: int
    application: str = "unknown"
    title: str = ""
    elements: List[ScreenElement] = field(default_factory=list)
    summary: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert screen description to dictionary."""
        return {
            "screen_width": int(self.screen_width),
            "screen_height": int(self.screen_height),
            "application": self.application or "unknown",
            "title": self.title or "",
            "element_count": len(self.elements),
            "elements": [el.to_dict() for el in self.elements],
            "summary": self.summary or "",
            "confidence": round(float(self.confidence), 3),
        }

