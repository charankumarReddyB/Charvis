"""
CHARVIS Vision Subsystem.
Phase 11: Screenshot & OCR.
Phase 12: Vision / Screen Understanding.
"""

from vision.analyzer import (
    VisionAnalyzer,
    get_vision_analyzer,
    set_vision_analyzer,
)
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
from vision.ocr import (
    BaseOCRProvider,
    MockOCRProvider,
    TesseractOCRProvider,
    get_ocr_provider,
)
from vision.providers import (
    BaseVisionProvider,
    LocalHeuristicVisionProvider,
    MockVisionProvider,
    OpenAIVisionProvider,
    get_vision_provider,
)
from vision.screenshot import ScreenshotEngine, get_monitor_count, get_screen_dimensions
from vision.security import (
    check_cloud_vision_allowed,
    sanitize_ocr_text_for_logging,
    validate_monitor_index,
    validate_region_coordinates,
    validate_screen_description,
    validate_screen_element,
    validate_screenshot_save_path,
)

__all__ = [
    "BaseOCRProvider",
    "BaseVisionProvider",
    "LocalHeuristicVisionProvider",
    "MalformedVisionOutputError",
    "MockOCRProvider",
    "MockVisionProvider",
    "NoDisplayAvailableError",
    "OCRError",
    "OCRResult",
    "OCRTextBlock",
    "OpenAIVisionProvider",
    "SUPPORTED_ELEMENT_TYPES",
    "ScreenDescription",
    "ScreenElement",
    "ScreenshotEngine",
    "ScreenshotError",
    "ScreenshotMetadata",
    "ScreenshotPermissionError",
    "TesseractNotFoundError",
    "TesseractOCRProvider",
    "VisionAnalyzer",
    "VisionCloudDisabledError",
    "VisionError",
    "VisionModelError",
    "VisionProviderUnavailableError",
    "VisionSecurityError",
    "VisionTimeoutError",
    "check_cloud_vision_allowed",
    "get_monitor_count",
    "get_ocr_provider",
    "get_screen_dimensions",
    "get_vision_analyzer",
    "get_vision_provider",
    "sanitize_ocr_text_for_logging",
    "set_vision_analyzer",
    "validate_monitor_index",
    "validate_region_coordinates",
    "validate_screen_description",
    "validate_screen_element",
    "validate_screenshot_save_path",
]
