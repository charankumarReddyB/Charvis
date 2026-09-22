"""
CHARVIS Vision Tools.
Phase 11: Screenshot & OCR.
Phase 12: Vision / Screen Understanding.

Provides 12 dedicated perception-only vision tools:
- Desktop screen capture (in-memory)
- Monitor and bounded region capture
- Explicit sandboxed screenshot saving
- Local OCR text extraction
- Bounded region text extraction
- On-screen text search (Phase 11)
- Full screen structured visual analysis (Phase 12)
- Bounded screen region visual analysis (Phase 12)
- Visual UI element search (Phase 12)
- Screen content summary description (Phase 12)
- Structured detected UI elements retrieval (Phase 12)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import get_settings
from core.safety import RiskLevel
from logger import get_logger
from tools.base import BaseTool
from tools.schemas import ToolParameter, ToolSchema
from vision.models import (
    MalformedVisionOutputError,
    NoDisplayAvailableError,
    OCRError,
    OCRResult,
    OCRTextBlock,
    ScreenDescription,
    ScreenElement,
    ScreenshotError,
    ScreenshotPermissionError,
    TesseractNotFoundError,
    VisionCloudDisabledError,
    VisionError,
    VisionModelError,
    VisionProviderUnavailableError,
    VisionSecurityError,
    VisionTimeoutError,
)
from vision.ocr import BaseOCRProvider, get_ocr_provider
from vision.screenshot import ScreenshotEngine
from vision.analyzer import VisionAnalyzer, get_vision_analyzer, set_vision_analyzer

logger = get_logger(__name__)

# Global shared engine instances
_ACTIVE_SCREENSHOT_ENGINE: Optional[ScreenshotEngine] = None
_ACTIVE_OCR_PROVIDER: Optional[BaseOCRProvider] = None


def get_screenshot_engine() -> ScreenshotEngine:
    """Retrieve or create the active singleton ScreenshotEngine instance."""
    global _ACTIVE_SCREENSHOT_ENGINE
    if _ACTIVE_SCREENSHOT_ENGINE is None:
        settings = get_settings()
        _ACTIVE_SCREENSHOT_ENGINE = ScreenshotEngine(
            max_region_area=settings.max_region_area,
        )
    return _ACTIVE_SCREENSHOT_ENGINE


def set_screenshot_engine(engine: Optional[ScreenshotEngine]) -> None:
    """Explicitly configure the active ScreenshotEngine (useful for testing/mocking)."""
    global _ACTIVE_SCREENSHOT_ENGINE
    _ACTIVE_SCREENSHOT_ENGINE = engine


def get_ocr_engine() -> BaseOCRProvider:
    """Retrieve or create the active singleton OCR provider instance."""
    global _ACTIVE_OCR_PROVIDER
    if _ACTIVE_OCR_PROVIDER is None:
        settings = get_settings()
        _ACTIVE_OCR_PROVIDER = get_ocr_provider(
            provider_type=settings.ocr_provider_type,
            tesseract_cmd=settings.tesseract_cmd,
            confidence_threshold=settings.ocr_confidence_threshold,
        )
    return _ACTIVE_OCR_PROVIDER


def set_ocr_engine(provider: Optional[BaseOCRProvider]) -> None:
    """Explicitly configure the active OCR provider (useful for testing/mocking)."""
    global _ACTIVE_OCR_PROVIDER
    _ACTIVE_OCR_PROVIDER = provider


# ---------------------------------------------------------------------------
# 1. capture_screenshot
# ---------------------------------------------------------------------------

class CaptureScreenshotTool(BaseTool):
    """Tool to capture the current primary desktop screen into memory."""

    def __init__(self, engine: Optional[ScreenshotEngine] = None) -> None:
        self._engine = engine

    @property
    def name(self) -> str:
        return "capture_screenshot"

    @property
    def description(self) -> str:
        return (
            "Capture the current primary desktop screen into memory. "
            "Returns screen dimensions, timestamp, and metadata. "
            "Does NOT save the screenshot to disk unless explicitly requested."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        engine = self._engine or get_screenshot_engine()
        try:
            _, meta = engine.capture_primary()
            return {
                "success": True,
                "metadata": meta.to_dict(),
                "message": (
                    f"Captured primary desktop ({meta.width}x{meta.height} px) into memory. "
                    "Image is held in memory and not saved to disk."
                ),
            }
        except ScreenshotPermissionError as err:
            return {"success": False, "error": f"Screen capture permission denied: {err}"}
        except NoDisplayAvailableError as err:
            return {"success": False, "error": f"No display available: {err}"}
        except VisionError as err:
            return {"success": False, "error": f"Screenshot error: {err}"}
        except Exception as err:
            return {"success": False, "error": f"Failed to capture screenshot: {err}"}


# ---------------------------------------------------------------------------
# 2. capture_screen
# ---------------------------------------------------------------------------

class CaptureScreenTool(BaseTool):
    """Tool to capture a selected display monitor into memory."""

    def __init__(self, engine: Optional[ScreenshotEngine] = None) -> None:
        self._engine = engine

    @property
    def name(self) -> str:
        return "capture_screen"

    @property
    def description(self) -> str:
        return (
            "Capture a specific display monitor by index into memory. "
            "Monitor 0 is the primary monitor. Validates monitor availability."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="monitor",
                    param_type="integer",
                    description="Monitor index to capture (0 for primary display).",
                    required=True,
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        monitor = kwargs.get("monitor")
        if monitor is None or not isinstance(monitor, int):
            return {"success": False, "error": "Parameter 'monitor' must be an integer."}

        engine = self._engine or get_screenshot_engine()
        try:
            _, meta = engine.capture_monitor(monitor)
            return {
                "success": True,
                "metadata": meta.to_dict(),
                "message": (
                    f"Captured monitor {monitor} ({meta.width}x{meta.height} px) into memory."
                ),
            }
        except VisionSecurityError as err:
            return {"success": False, "error": f"Invalid monitor parameter: {err}"}
        except ScreenshotPermissionError as err:
            return {"success": False, "error": f"Screen capture permission denied: {err}"}
        except VisionError as err:
            return {"success": False, "error": f"Screenshot error: {err}"}
        except Exception as err:
            return {"success": False, "error": f"Failed to capture monitor {monitor}: {err}"}


# ---------------------------------------------------------------------------
# 3. capture_region
# ---------------------------------------------------------------------------

class CaptureRegionTool(BaseTool):
    """Tool to capture a bounded rectangular region of the desktop."""

    def __init__(self, engine: Optional[ScreenshotEngine] = None) -> None:
        self._engine = engine

    @property
    def name(self) -> str:
        return "capture_region"

    @property
    def description(self) -> str:
        return (
            "Capture a bounded rectangular desktop region (x, y, width, height) into memory. "
            "Strictly validates coordinates against desktop bounds and area limits."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="x",
                    param_type="integer",
                    description="Left coordinate (x >= 0, origin top-left).",
                    required=True,
                ),
                ToolParameter(
                    name="y",
                    param_type="integer",
                    description="Top coordinate (y >= 0, origin top-left).",
                    required=True,
                ),
                ToolParameter(
                    name="width",
                    param_type="integer",
                    description="Region width in pixels (width > 0).",
                    required=True,
                ),
                ToolParameter(
                    name="height",
                    param_type="integer",
                    description="Region height in pixels (height > 0).",
                    required=True,
                ),
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        x = kwargs.get("x")
        y = kwargs.get("y")
        width = kwargs.get("width")
        height = kwargs.get("height")

        for name, val in [("x", x), ("y", y), ("width", width), ("height", height)]:
            if val is None or not isinstance(val, int):
                return {"success": False, "error": f"Parameter '{name}' must be an integer."}

        engine = self._engine or get_screenshot_engine()
        try:
            _, meta = engine.capture_region(x=x, y=y, width=width, height=height)
            return {
                "success": True,
                "metadata": meta.to_dict(),
                "region": {"x": x, "y": y, "width": width, "height": height},
                "message": (
                    f"Captured region ({x}, {y}, {width}x{height} px) into memory."
                ),
            }
        except VisionSecurityError as err:
            return {"success": False, "error": f"Invalid region coordinates: {err}"}
        except ScreenshotPermissionError as err:
            return {"success": False, "error": f"Screen capture permission denied: {err}"}
        except VisionError as err:
            return {"success": False, "error": f"Region capture error: {err}"}
        except Exception as err:
            return {"success": False, "error": f"Failed to capture region: {err}"}


# ---------------------------------------------------------------------------
# 4. save_screenshot
# ---------------------------------------------------------------------------

class SaveScreenshotTool(BaseTool):
    """Tool to explicitly save the active in-memory screenshot to the sandbox."""

    def __init__(
        self,
        engine: Optional[ScreenshotEngine] = None,
        sandbox_root: Optional[Any] = None,
    ) -> None:
        self._engine = engine
        self._sandbox_root = sandbox_root

    @property
    def name(self) -> str:
        return "save_screenshot"

    @property
    def description(self) -> str:
        return (
            "Save the current in-memory screenshot to a file inside the allowed workspace sandbox. "
            "Rejects path traversal, absolute paths outside the sandbox, and unauthorized overwrites."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="filename",
                    param_type="string",
                    description="Filename for the saved screenshot (e.g. 'desktop_capture.png').",
                    required=True,
                ),
                ToolParameter(
                    name="overwrite",
                    param_type="boolean",
                    description="Whether to overwrite if file already exists in workspace (default false).",
                    required=False,
                ),
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        filename = kwargs.get("filename")
        overwrite = bool(kwargs.get("overwrite", False))

        if not filename or not isinstance(filename, str):
            return {"success": False, "error": "Parameter 'filename' must be a non-empty string."}

        engine = self._engine or get_screenshot_engine()
        sandbox_root = self._sandbox_root or get_settings().filesystem_workspace

        try:
            dest_path = engine.save_last_screenshot(
                filename=filename,
                sandbox_root=sandbox_root,
                overwrite=overwrite,
            )
            return {
                "success": True,
                "saved_path": str(dest_path),
                "filename": dest_path.name,
                "message": f"Screenshot successfully saved to sandbox: {dest_path.name}",
            }
        except VisionSecurityError as err:
            return {"success": False, "error": f"Security validation failed: {err}"}
        except VisionError as err:
            return {"success": False, "error": f"Screenshot save error: {err}"}
        except Exception as err:
            return {"success": False, "error": f"Failed to save screenshot: {err}"}


# ---------------------------------------------------------------------------
# 5. read_screen_text
# ---------------------------------------------------------------------------

class ReadScreenTextTool(BaseTool):
    """Tool to capture the primary screen and extract text using local OCR."""

    def __init__(
        self,
        engine: Optional[ScreenshotEngine] = None,
        ocr: Optional[BaseOCRProvider] = None,
    ) -> None:
        self._engine = engine
        self._ocr = ocr

    @property
    def name(self) -> str:
        return "read_screen_text"

    @property
    def description(self) -> str:
        return (
            "Capture the primary desktop screen and extract visible text using local OCR. "
            "Returns extracted text, block count, and bounding box coordinates."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="max_length",
                    param_type="integer",
                    description="Maximum characters of extracted text to return (optional).",
                    required=False,
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        max_length = kwargs.get("max_length")
        settings = get_settings()
        limit = max_length if isinstance(max_length, int) and max_length > 0 else settings.max_ocr_text_length

        engine = self._engine or get_screenshot_engine()
        ocr = self._ocr or get_ocr_engine()

        try:
            img, meta = engine.capture_primary()
            res: OCRResult = ocr.extract_text(img, max_length=limit)
            return {
                "success": True,
                "full_text": res.full_text,
                "block_count": len(res.blocks),
                "image_width": res.image_width,
                "image_height": res.image_height,
                "blocks": [b.to_dict() for b in res.blocks[:100]],
            }
        except ScreenshotPermissionError as err:
            return {"success": False, "error": f"Screen capture permission denied: {err}"}
        except TesseractNotFoundError as err:
            return {"success": False, "error": f"OCR engine unavailable: {err}"}
        except VisionError as err:
            return {"success": False, "error": f"Vision error: {err}"}
        except Exception as err:
            return {"success": False, "error": f"Failed to read screen text: {err}"}


# ---------------------------------------------------------------------------
# 6. read_region_text
# ---------------------------------------------------------------------------

class ReadRegionTextTool(BaseTool):
    """Tool to capture a bounded screen region and extract text using local OCR."""

    def __init__(
        self,
        engine: Optional[ScreenshotEngine] = None,
        ocr: Optional[BaseOCRProvider] = None,
    ) -> None:
        self._engine = engine
        self._ocr = ocr

    @property
    def name(self) -> str:
        return "read_region_text"

    @property
    def description(self) -> str:
        return (
            "Capture a bounded rectangular region (x, y, width, height) and extract text using local OCR. "
            "Returns extracted text and bounding boxes relative to desktop origin."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="x",
                    param_type="integer",
                    description="Region left coordinate (x >= 0).",
                    required=True,
                ),
                ToolParameter(
                    name="y",
                    param_type="integer",
                    description="Region top coordinate (y >= 0).",
                    required=True,
                ),
                ToolParameter(
                    name="width",
                    param_type="integer",
                    description="Region width in pixels.",
                    required=True,
                ),
                ToolParameter(
                    name="height",
                    param_type="integer",
                    description="Region height in pixels.",
                    required=True,
                ),
                ToolParameter(
                    name="max_length",
                    param_type="integer",
                    description="Maximum characters of extracted text to return (optional).",
                    required=False,
                ),
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        x = kwargs.get("x")
        y = kwargs.get("y")
        width = kwargs.get("width")
        height = kwargs.get("height")
        max_length = kwargs.get("max_length")

        for name, val in [("x", x), ("y", y), ("width", width), ("height", height)]:
            if val is None or not isinstance(val, int):
                return {"success": False, "error": f"Parameter '{name}' must be an integer."}

        settings = get_settings()
        limit = max_length if isinstance(max_length, int) and max_length > 0 else settings.max_ocr_text_length

        engine = self._engine or get_screenshot_engine()
        ocr = self._ocr or get_ocr_engine()

        try:
            img, meta = engine.capture_region(x=x, y=y, width=width, height=height)
            res: OCRResult = ocr.extract_text(img, max_length=limit)

            # Adjust bounding box coordinates to be relative to screen origin (offset by x, y)
            adjusted_blocks = []
            for b in res.blocks:
                adjusted_blocks.append(
                    OCRTextBlock(
                        text=b.text,
                        confidence=b.confidence,
                        x=b.x + x,
                        y=b.y + y,
                        width=b.width,
                        height=b.height,
                    ).to_dict()
                )

            return {
                "success": True,
                "region": {"x": x, "y": y, "width": width, "height": height},
                "full_text": res.full_text,
                "block_count": len(adjusted_blocks),
                "blocks": adjusted_blocks[:100],
            }
        except VisionSecurityError as err:
            return {"success": False, "error": f"Invalid region coordinates: {err}"}
        except ScreenshotPermissionError as err:
            return {"success": False, "error": f"Screen capture permission denied: {err}"}
        except TesseractNotFoundError as err:
            return {"success": False, "error": f"OCR engine unavailable: {err}"}
        except VisionError as err:
            return {"success": False, "error": f"Vision error: {err}"}
        except Exception as err:
            return {"success": False, "error": f"Failed to read region text: {err}"}


# ---------------------------------------------------------------------------
# 7. find_text_on_screen
# ---------------------------------------------------------------------------

class FindTextOnScreenTool(BaseTool):
    """
    Tool to capture the screen, perform OCR, and find coordinates of specified text.
    Perception ONLY: returns bounding boxes and does NOT perform any click or key action.
    """

    def __init__(
        self,
        engine: Optional[ScreenshotEngine] = None,
        ocr: Optional[BaseOCRProvider] = None,
    ) -> None:
        self._engine = engine
        self._ocr = ocr

    @property
    def name(self) -> str:
        return "find_text_on_screen"

    @property
    def description(self) -> str:
        return (
            "Capture the current screen, perform local OCR, and search for the specified target text. "
            "Returns matching bounding boxes (x, y, width, height). "
            "This tool is perception only: it finds coordinates and does NOT click or interact."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="text",
                    param_type="string",
                    description="Text string to locate on the screen.",
                    required=True,
                ),
                ToolParameter(
                    name="case_sensitive",
                    param_type="boolean",
                    description="Whether to perform case-sensitive search (default false).",
                    required=False,
                ),
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        query = kwargs.get("text")
        case_sensitive = bool(kwargs.get("case_sensitive", False))

        if not query or not isinstance(query, str) or not query.strip():
            return {"success": False, "error": "Parameter 'text' must be a non-empty string."}

        target = query.strip()
        search_target = target if case_sensitive else target.lower()

        engine = self._engine or get_screenshot_engine()
        ocr = self._ocr or get_ocr_engine()

        try:
            img, meta = engine.capture_primary()
            res: OCRResult = ocr.extract_text(img)

            # Match across blocks
            matches: List[Dict[str, Any]] = []

            # 1. Single word exact or substring match in blocks
            for block in res.blocks:
                candidate = block.text if case_sensitive else block.text.lower()
                if search_target == candidate or search_target in candidate:
                    matches.append(block.to_dict())

            # 2. Multi-word phrase match across consecutive blocks
            query_words = search_target.split()
            if len(query_words) > 1 and len(res.blocks) >= len(query_words):
                for idx in range(len(res.blocks) - len(query_words) + 1):
                    sub_blocks = res.blocks[idx : idx + len(query_words)]
                    sub_text = " ".join(
                        b.text if case_sensitive else b.text.lower() for b in sub_blocks
                    )
                    if search_target in sub_text:
                        # Combined bounding box
                        min_x = min(b.x for b in sub_blocks)
                        min_y = min(b.y for b in sub_blocks)
                        max_x = max(b.x + b.width for b in sub_blocks)
                        max_y = max(b.y + b.height for b in sub_blocks)
                        avg_conf = sum(b.confidence for b in sub_blocks) / len(sub_words := sub_blocks)

                        combined_block = {
                            "text": " ".join(b.text for b in sub_blocks),
                            "confidence": round(avg_conf, 2),
                            "x": min_x,
                            "y": min_y,
                            "width": max_x - min_x,
                            "height": max_y - min_y,
                        }
                        if combined_block not in matches:
                            matches.append(combined_block)

            found = len(matches) > 0
            if found:
                first = matches[0]
                message = (
                    f"Found '{query}' on screen at x={first['x']}, y={first['y']} "
                    f"(width={first['width']}, height={first['height']}). "
                    f"Total matches: {len(matches)}."
                )
            else:
                message = f"Text '{query}' was not found on the screen."

            return {
                "success": True,
                "found": found,
                "query": query,
                "match_count": len(matches),
                "matches": matches,
                "message": message,
            }
        except ScreenshotPermissionError as err:
            return {"success": False, "error": f"Screen capture permission denied: {err}"}
        except TesseractNotFoundError as err:
            return {"success": False, "error": f"OCR engine unavailable: {err}"}
        except VisionError as err:
            return {"success": False, "error": f"Vision error: {err}"}
        except Exception as err:
            return {"success": False, "error": f"Failed to find text on screen: {err}"}


# ---------------------------------------------------------------------------
# 8. analyze_screen (Phase 12)
# ---------------------------------------------------------------------------

class AnalyzeScreenTool(BaseTool):
    """Tool to capture primary display and return structured visual screen understanding."""

    def __init__(self, analyzer: Optional[VisionAnalyzer] = None) -> None:
        self._analyzer = analyzer

    @property
    def name(self) -> str:
        return "analyze_screen"

    @property
    def description(self) -> str:
        return (
            "Capture the primary screen and produce a structured visual description including "
            "detected application, window title, and visual UI elements (buttons, inputs, text). "
            "Perception only: does NOT click or interact."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="context",
                    param_type="string",
                    description="Optional context or query to focus visual analysis.",
                    required=False,
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        context = kwargs.get("context")
        analyzer = self._analyzer or get_vision_analyzer()
        try:
            desc = analyzer.analyze_full_screen(context=context)
            return {
                "success": True,
                "description": desc.to_dict(),
                "summary": desc.summary,
                "application": desc.application,
                "element_count": len(desc.elements),
            }
        except ScreenshotPermissionError as err:
            return {"success": False, "error": f"Screen capture permission denied: {err}"}
        except VisionCloudDisabledError as err:
            return {"success": False, "error": f"Cloud vision disabled: {err}"}
        except VisionError as err:
            return {"success": False, "error": f"Vision analysis error: {err}"}
        except Exception as err:
            return {"success": False, "error": f"Failed to analyze screen: {err}"}


# ---------------------------------------------------------------------------
# 9. analyze_screen_region (Phase 12)
# ---------------------------------------------------------------------------

class AnalyzeScreenRegionTool(BaseTool):
    """Tool to analyze a bounded rectangular screen region and return structured UI elements."""

    def __init__(self, analyzer: Optional[VisionAnalyzer] = None) -> None:
        self._analyzer = analyzer

    @property
    def name(self) -> str:
        return "analyze_screen_region"

    @property
    def description(self) -> str:
        return (
            "Analyze a bounded rectangular region of the screen (x, y, width, height) "
            "and produce structured visual understanding with screen-relative coordinates. "
            "Perception only: does NOT click or interact."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="x",
                    param_type="integer",
                    description="Region left coordinate (x >= 0).",
                    required=True,
                ),
                ToolParameter(
                    name="y",
                    param_type="integer",
                    description="Region top coordinate (y >= 0).",
                    required=True,
                ),
                ToolParameter(
                    name="width",
                    param_type="integer",
                    description="Region width in pixels (width > 0).",
                    required=True,
                ),
                ToolParameter(
                    name="height",
                    param_type="integer",
                    description="Region height in pixels (height > 0).",
                    required=True,
                ),
                ToolParameter(
                    name="context",
                    param_type="string",
                    description="Optional context or query to focus region analysis.",
                    required=False,
                ),
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        x = kwargs.get("x")
        y = kwargs.get("y")
        width = kwargs.get("width")
        height = kwargs.get("height")
        context = kwargs.get("context")

        for name, val in [("x", x), ("y", y), ("width", width), ("height", height)]:
            if val is None or not isinstance(val, int):
                return {"success": False, "error": f"Parameter '{name}' must be an integer."}

        analyzer = self._analyzer or get_vision_analyzer()
        try:
            desc = analyzer.analyze_region(
                x=x,
                y=y,
                width=width,
                height=height,
                context=context,
            )
            return {
                "success": True,
                "region": {"x": x, "y": y, "width": width, "height": height},
                "description": desc.to_dict(),
                "summary": desc.summary,
                "element_count": len(desc.elements),
            }
        except VisionSecurityError as err:
            return {"success": False, "error": f"Invalid region coordinates: {err}"}
        except ScreenshotPermissionError as err:
            return {"success": False, "error": f"Screen capture permission denied: {err}"}
        except VisionCloudDisabledError as err:
            return {"success": False, "error": f"Cloud vision disabled: {err}"}
        except VisionError as err:
            return {"success": False, "error": f"Region vision error: {err}"}
        except Exception as err:
            return {"success": False, "error": f"Failed to analyze screen region: {err}"}


# ---------------------------------------------------------------------------
# 10. find_visual_element (Phase 12)
# ---------------------------------------------------------------------------

class FindVisualElementTool(BaseTool):
    """Tool to search the screen for a specific visual UI element (button, input, window, etc.)."""

    def __init__(self, analyzer: Optional[VisionAnalyzer] = None) -> None:
        self._analyzer = analyzer

    @property
    def name(self) -> str:
        return "find_visual_element"

    @property
    def description(self) -> str:
        return (
            "Analyze the screen and search for a requested visual element (e.g., 'Settings button', "
            "'search box', 'Notepad window'). Returns element type, label, confidence, and bounding box. "
            "Perception only: does NOT click, type, or interact."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="description",
                    param_type="string",
                    description="Description or label of the visual UI element to locate.",
                    required=True,
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        query = kwargs.get("description")
        if not query or not isinstance(query, str) or not query.strip():
            return {"success": False, "error": "Parameter 'description' must be a non-empty string."}

        analyzer = self._analyzer or get_vision_analyzer()
        try:
            return analyzer.find_element(description=query)
        except ScreenshotPermissionError as err:
            return {"success": False, "error": f"Screen capture permission denied: {err}"}
        except VisionCloudDisabledError as err:
            return {"success": False, "error": f"Cloud vision disabled: {err}"}
        except VisionError as err:
            return {"success": False, "error": f"Vision error: {err}"}
        except Exception as err:
            return {"success": False, "error": f"Failed to find visual element: {err}"}


# ---------------------------------------------------------------------------
# 11. describe_screen (Phase 12)
# ---------------------------------------------------------------------------

class DescribeScreenTool(BaseTool):
    """Tool to return a human-readable summary of the current desktop display."""

    def __init__(self, analyzer: Optional[VisionAnalyzer] = None) -> None:
        self._analyzer = analyzer

    @property
    def name(self) -> str:
        return "describe_screen"

    @property
    def description(self) -> str:
        return (
            "Return a concise, human-readable summary of the current screen based on "
            "structured visual understanding and detected UI layout. "
            "Perception only: does NOT click or interact."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="context",
                    param_type="string",
                    description="Optional context or focus for the screen summary.",
                    required=False,
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        context = kwargs.get("context")
        analyzer = self._analyzer or get_vision_analyzer()
        try:
            summary = analyzer.describe_screen(context=context)
            return {
                "success": True,
                "summary": summary,
            }
        except ScreenshotPermissionError as err:
            return {"success": False, "error": f"Screen capture permission denied: {err}"}
        except VisionCloudDisabledError as err:
            return {"success": False, "error": f"Cloud vision disabled: {err}"}
        except VisionError as err:
            return {"success": False, "error": f"Vision error: {err}"}
        except Exception as err:
            return {"success": False, "error": f"Failed to describe screen: {err}"}


# ---------------------------------------------------------------------------
# 12. get_screen_elements (Phase 12)
# ---------------------------------------------------------------------------

class GetScreenElementsTool(BaseTool):
    """Tool to return structured detected UI elements from the primary screen."""

    def __init__(self, analyzer: Optional[VisionAnalyzer] = None) -> None:
        self._analyzer = analyzer

    @property
    def name(self) -> str:
        return "get_screen_elements"

    @property
    def description(self) -> str:
        return (
            "Return structured list of detected UI elements (buttons, inputs, windows, icons) "
            "on the primary screen with bounding boxes and confidence scores. Perception only."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        analyzer = self._analyzer or get_vision_analyzer()
        try:
            elements = analyzer.get_screen_elements()
            return {
                "success": True,
                "element_count": len(elements),
                "elements": elements,
            }
        except ScreenshotPermissionError as err:
            return {"success": False, "error": f"Screen capture permission denied: {err}"}
        except VisionCloudDisabledError as err:
            return {"success": False, "error": f"Cloud vision disabled: {err}"}
        except VisionError as err:
            return {"success": False, "error": f"Vision error: {err}"}
        except Exception as err:
            return {"success": False, "error": f"Failed to get screen elements: {err}"}

