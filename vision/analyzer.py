"""
High-level Vision Analyzer coordinating screenshots, OCR, and visual understanding.
Phase 12: Vision / Screen Understanding.

Perception-only orchestrator:
- Captures desktop screenshots via ScreenshotEngine.
- Extracts text & bounding boxes via BaseOCRProvider.
- Produces structured ScreenDescription via BaseVisionProvider.
- Provides search for visual elements, region analysis, and screen descriptions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from PIL import Image

from config import get_settings
from vision.models import (
    OCRResult,
    ScreenDescription,
    ScreenElement,
    VisionError,
)
from vision.ocr import BaseOCRProvider, get_ocr_provider
from vision.providers import BaseVisionProvider, get_vision_provider
from vision.screenshot import ScreenshotEngine, get_screen_dimensions
from vision.security import validate_region_coordinates

logger = logging.getLogger(__name__)

# Global singleton analyzer instance
_ACTIVE_VISION_ANALYZER: Optional[VisionAnalyzer] = None


class VisionAnalyzer:
    """
    Central visual perception engine.
    Orchestrates screenshot capture, local OCR, and vision provider inference.
    Strictly perception-only: never performs mouse, keyboard, or window actions.
    """

    def __init__(
        self,
        screenshot_engine: Optional[ScreenshotEngine] = None,
        ocr_provider: Optional[BaseOCRProvider] = None,
        vision_provider: Optional[BaseVisionProvider] = None,
    ) -> None:
        self._screenshot_engine = screenshot_engine
        self._ocr_provider = ocr_provider
        self._vision_provider = vision_provider
        self._last_description: Optional[ScreenDescription] = None

    @property
    def screenshot_engine(self) -> ScreenshotEngine:
        if self._screenshot_engine is None:
            from tools.vision import get_screenshot_engine
            self._screenshot_engine = get_screenshot_engine()
        return self._screenshot_engine

    @property
    def ocr_provider(self) -> BaseOCRProvider:
        if self._ocr_provider is None:
            from tools.vision import get_ocr_engine
            self._ocr_provider = get_ocr_engine()
        return self._ocr_provider

    @property
    def vision_provider(self) -> BaseVisionProvider:
        if self._vision_provider is None:
            self._vision_provider = get_vision_provider()
        return self._vision_provider

    @property
    def last_description(self) -> Optional[ScreenDescription]:
        """Return the most recently computed screen description, if any."""
        return self._last_description

    def clear_cache(self) -> None:
        """Clear cached visual understanding."""
        self._last_description = None

    def analyze_full_screen(self, context: Optional[str] = None) -> ScreenDescription:
        """
        Capture primary display, extract OCR blocks, and produce structured ScreenDescription.
        """
        # 1. Capture primary screen in-memory
        image, _ = self.screenshot_engine.capture_primary()

        # 2. Extract OCR text and bounding boxes locally
        ocr_result: Optional[OCRResult] = None
        try:
            if self.ocr_provider.is_available():
                ocr_result = self.ocr_provider.extract_text(image)
        except Exception as ocr_exc:
            logger.warning("OCR extraction encountered error during vision analysis: %s", ocr_exc)

        # 3. Analyze through configured vision provider
        description = self.vision_provider.analyze(
            image=image,
            context=context,
            ocr_result=ocr_result,
        )
        self._last_description = description
        return description

    def analyze_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        context: Optional[str] = None,
    ) -> ScreenDescription:
        """
        Capture a bounded region, run OCR, and produce structured ScreenDescription with screen-relative coordinates.
        """
        screen_w, screen_h = get_screen_dimensions()
        settings = get_settings()

        # Validate coordinates using Phase 11 validator
        vx, vy, vw, vh = validate_region_coordinates(
            x=x,
            y=y,
            width=width,
            height=height,
            screen_width=screen_w,
            screen_height=screen_h,
            max_area=settings.max_region_area,
        )

        # Capture region image in-memory
        region_img, _ = self.screenshot_engine.capture_region(x=vx, y=vy, width=vw, height=vh)

        # Local OCR for region
        ocr_result: Optional[OCRResult] = None
        try:
            if self.ocr_provider.is_available():
                ocr_result = self.ocr_provider.extract_text(region_img)
        except Exception as ocr_exc:
            logger.warning("Region OCR encountered error during vision analysis: %s", ocr_exc)

        # Analyze region
        desc = self.vision_provider.analyze(
            image=region_img,
            context=context,
            ocr_result=ocr_result,
        )

        # Adjust detected elements coordinates from region-relative to screen-relative (offset by vx, vy)
        adjusted_elements: List[ScreenElement] = []
        for elem in desc.elements:
            adjusted_elements.append(
                ScreenElement(
                    element_type=elem.element_type,
                    label=elem.label,
                    text=elem.text,
                    confidence=elem.confidence,
                    x=elem.x + vx,
                    y=elem.y + vy,
                    width=elem.width,
                    height=elem.height,
                )
            )

        region_description = ScreenDescription(
            screen_width=vw,
            screen_height=vh,
            application=desc.application,
            title=desc.title,
            elements=adjusted_elements,
            summary=desc.summary,
            confidence=desc.confidence,
        )
        self._last_description = region_description
        return region_description

    def find_element(self, description: str) -> Dict[str, Any]:
        """
        Locate visual UI elements matching a natural language description or label.
        Returns matched elements with coordinates and confidence. Perception only.
        """
        query = description.strip()
        if not query:
            return {
                "success": False,
                "found": False,
                "error": "Query description cannot be empty.",
            }

        # Analyze fresh screen
        screen_desc = self.analyze_full_screen(context=query)

        query_lower = query.lower()
        matches: List[Dict[str, Any]] = []

        # 1. First pass: exact or substring match in element label or text
        for el in screen_desc.elements:
            el_dict = el.to_dict()
            label_lower = el.label.lower()
            text_lower = el.text.lower()
            type_lower = el.element_type.lower()

            if query_lower in label_lower or query_lower in text_lower or query_lower == type_lower:
                matches.append(el_dict)

        # 2. Second pass: individual word matching if multi-word query didn't find exact matches
        if not matches:
            query_words = [w for w in query_lower.split() if len(w) > 2]
            for el in screen_desc.elements:
                el_dict = el.to_dict()
                label_lower = el.label.lower()
                text_lower = el.text.lower()
                type_lower = el.element_type.lower()

                if any(w in label_lower or w in text_lower or w == type_lower for w in query_words):
                    if el_dict not in matches:
                        matches.append(el_dict)

        found = len(matches) > 0
        if found:
            first = matches[0]
            msg = (
                f"Found visual element matching '{query}': type '{first['element_type']}', "
                f"label '{first['label']}' at x={first['x']}, y={first['y']} "
                f"(width={first['width']}, height={first['height']}, confidence={first['confidence']}). "
                f"Total matches: {len(matches)}."
            )
        else:
            msg = f"Visual element matching '{query}' was not detected on screen."

        return {
            "success": True,
            "found": found,
            "query": query,
            "match_count": len(matches),
            "matches": matches,
            "message": msg,
        }

    def describe_screen(self, context: Optional[str] = None) -> str:
        """
        Return human-readable summary of current visual screen contents.
        """
        desc = self.analyze_full_screen(context=context)
        return desc.summary

    def get_screen_elements(self) -> List[Dict[str, Any]]:
        """
        Return structured detected UI elements from the active screen.
        """
        desc = self.analyze_full_screen()
        return [el.to_dict() for el in desc.elements]


def get_vision_analyzer() -> VisionAnalyzer:
    """Retrieve or initialize the active singleton VisionAnalyzer instance."""
    global _ACTIVE_VISION_ANALYZER
    if _ACTIVE_VISION_ANALYZER is None:
        _ACTIVE_VISION_ANALYZER = VisionAnalyzer()
    return _ACTIVE_VISION_ANALYZER


def set_vision_analyzer(analyzer: Optional[VisionAnalyzer]) -> None:
    """Explicitly configure the active VisionAnalyzer (useful for testing/mocking)."""
    global _ACTIVE_VISION_ANALYZER
    _ACTIVE_VISION_ANALYZER = analyzer
