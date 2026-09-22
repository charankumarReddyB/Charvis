"""
Security and validation rules for CHARVIS Vision and OCR.
Phase 11: Screenshot & OCR.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from config import get_settings
from vision.models import (
    MalformedVisionOutputError,
    SUPPORTED_ELEMENT_TYPES,
    ScreenDescription,
    ScreenElement,
    VisionCloudDisabledError,
    VisionSecurityError,
)


# Allowed image extensions for saving screenshots
ALLOWED_SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg"}

# Regex patterns for sensitive data redaction in diagnostic logs
SENSITIVE_PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE), "sk-***REDACTED***"),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "***CARD-REDACTED***"),
    (re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE), "Bearer ***TOKEN-REDACTED***"),
    (re.compile(r"(?:password|passwd|pwd)[\s:=]+([^\s,;]+)", re.IGNORECASE), "password=***REDACTED***"),
    (re.compile(r"\b(?:otp|pin|cvv|cvc)[\s:=]+(\d{3,8})\b", re.IGNORECASE), "code=***REDACTED***"),
]


def validate_region_coordinates(
    x: int,
    y: int,
    width: int,
    height: int,
    screen_width: int,
    screen_height: int,
    max_area: int = 33_177_600,
) -> Tuple[int, int, int, int]:
    """
    Validate rectangular region coordinates for screen capture.

    Enforces:
    - Coordinates must be integers.
    - x >= 0, y >= 0.
    - width > 0, height > 0.
    - Region cannot extend beyond desktop bounds.
    - Total area (width * height) cannot exceed max_area.

    Returns validated (x, y, width, height) tuple or raises VisionSecurityError.
    """
    if not isinstance(x, int) or not isinstance(y, int):
        raise VisionSecurityError(f"Coordinates (x, y) must be integers, got ({type(x).__name__}, {type(y).__name__})")

    if not isinstance(width, int) or not isinstance(height, int):
        raise VisionSecurityError(f"Dimensions (width, height) must be integers, got ({type(width).__name__}, {type(height).__name__})")

    if x < 0 or y < 0:
        raise VisionSecurityError(f"Coordinates cannot be negative: ({x}, {y})")

    if width <= 0 or height <= 0:
        raise VisionSecurityError(f"Dimensions must be strictly positive: width={width}, height={height}")

    area = width * height
    if area > max_area:
        raise VisionSecurityError(
            f"Requested region area ({area:,} px) exceeds maximum allowed ({max_area:,} px)"
        )

    if screen_width > 0 and screen_height > 0:
        if x + width > screen_width:
            raise VisionSecurityError(
                f"Region horizontal span (x={x} + width={width} = {x + width}) "
                f"exceeds screen width ({screen_width})"
            )
        if y + height > screen_height:
            raise VisionSecurityError(
                f"Region vertical span (y={y} + height={height} = {y + height}) "
                f"exceeds screen height ({screen_height})"
            )

    return x, y, width, height


def validate_monitor_index(monitor: int, available_monitors: int) -> int:
    """
    Validate that monitor index is valid and available.
    Monitor 0 is always the primary display.
    """
    if not isinstance(monitor, int):
        raise VisionSecurityError(f"Monitor index must be an integer, got {type(monitor).__name__}")

    if monitor < 0:
        raise VisionSecurityError(f"Monitor index cannot be negative: {monitor}")

    if available_monitors > 0 and monitor >= available_monitors:
        raise VisionSecurityError(
            f"Monitor index {monitor} is out of range. Available monitors: 0 to {available_monitors - 1}"
        )

    return monitor


def validate_screenshot_save_path(
    filename: str,
    sandbox_root: Path,
) -> Path:
    """
    Validate that a screenshot destination filename stays strictly within
    the sandbox directory and uses an allowed image extension.

    Prevents:
    - Path traversal (..)
    - Absolute path escapes
    - Prohibited extensions (.exe, .bat, etc.)
    """
    if not filename or not filename.strip():
        raise VisionSecurityError("Screenshot filename cannot be empty")

    clean_name = filename.strip()

    # Reject explicit path traversal tokens
    if ".." in clean_name or "/" in clean_name or ("\\" in clean_name and not clean_name.startswith(str(sandbox_root))):
        # If user passed a relative subpath or traversal
        parts = Path(clean_name).parts
        if ".." in parts:
            raise VisionSecurityError(f"Path traversal detected in filename: '{clean_name}'")

    sandbox_resolved = sandbox_root.resolve()
    target_path = Path(clean_name)

    if target_path.is_absolute():
        resolved_target = target_path.resolve()
        try:
            resolved_target.relative_to(sandbox_resolved)
        except ValueError:
            raise VisionSecurityError(
                f"Cannot save screenshot outside sandbox: '{clean_name}'. "
                f"Must be inside '{sandbox_resolved}'"
            )
        final_path = resolved_target
    else:
        final_path = (sandbox_resolved / target_path).resolve()
        try:
            final_path.relative_to(sandbox_resolved)
        except ValueError:
            raise VisionSecurityError(
                f"Path traversal escape detected: '{clean_name}' resolves outside sandbox"
            )

    # Validate image extension
    ext = final_path.suffix.lower()
    if not ext:
        final_path = final_path.with_suffix(".png")
    elif ext not in ALLOWED_SCREENSHOT_EXTENSIONS:
        raise VisionSecurityError(
            f"Invalid screenshot file extension '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_SCREENSHOT_EXTENSIONS))}"
        )

    return final_path


def sanitize_ocr_text_for_logging(text: str) -> str:
    """
    Mask common sensitive patterns in OCR text for diagnostic logs.
    """
    if not text:
        return ""

    sanitized = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    return sanitized


# ---------------------------------------------------------------------------
# Phase 12: Vision Understanding & Cloud Boundary Validation
# ---------------------------------------------------------------------------

def check_cloud_vision_allowed(settings: Optional[Any] = None) -> None:
    """
    Verify that cloud vision transmission has been explicitly authorized.
    Raises VisionCloudDisabledError if vision_cloud_enabled is False.
    """
    current_settings = settings or get_settings()
    if not getattr(current_settings, "vision_cloud_enabled", False):
        raise VisionCloudDisabledError(
            "Cloud vision is disabled by default. Screenshot images cannot be transmitted "
            "to an external cloud API without explicit user configuration. "
            "Set 'VISION_CLOUD_ENABLED=true' in your .env file to authorize cloud vision."
        )


def validate_screen_element(
    elem_dict: Any,
    max_width: int,
    max_height: int,
    max_label_len: int = 100,
) -> ScreenElement:
    """
    Validate and sanitize a single raw detected screen element.

    Enforces:
    - Must be a dictionary.
    - element_type in supported set (falls back to 'unknown').
    - Coordinates are valid integers >= 0.
    - Dimensions are strictly positive > 0.
    - Coordinates remain within image bounds.
    - Confidence normalized to [0.0, 1.0].
    - Label and text bounded to max_label_len.

    Raises MalformedVisionOutputError if coordinates or structure are invalid.
    """
    if not isinstance(elem_dict, dict):
        raise MalformedVisionOutputError(
            f"Screen element must be a dictionary, got {type(elem_dict).__name__}"
        )

    # Validate and normalize element type
    raw_type = str(elem_dict.get("element_type", "unknown")).strip().lower()
    element_type = raw_type if raw_type in SUPPORTED_ELEMENT_TYPES else "unknown"

    # Validate label and text
    raw_label = str(elem_dict.get("label", "")).strip()
    label = raw_label[:max_label_len]
    raw_text = str(elem_dict.get("text", "")).strip()
    text = raw_text[: max_label_len * 2]

    # Validate confidence
    raw_conf = elem_dict.get("confidence", 0.0)
    try:
        conf = float(raw_conf)
        # Normalize if model passed percentage 0-100 instead of 0.0-1.0
        if conf > 1.0 and conf <= 100.0:
            conf = conf / 100.0
        conf = max(0.0, min(1.0, conf))
    except (ValueError, TypeError):
        conf = 0.0

    # Validate coordinates
    try:
        x = int(elem_dict.get("x", 0))
        y = int(elem_dict.get("y", 0))
        width = int(elem_dict.get("width", 0))
        height = int(elem_dict.get("height", 0))
    except (ValueError, TypeError) as exc:
        raise MalformedVisionOutputError(
            f"Element coordinates must be integers: {exc}"
        ) from exc

    if x < 0 or y < 0:
        raise MalformedVisionOutputError(
            f"Element coordinates cannot be negative: ({x}, {y})"
        )

    if width <= 0 or height <= 0:
        raise MalformedVisionOutputError(
            f"Element dimensions must be strictly positive: width={width}, height={height}"
        )

    if max_width > 0 and max_height > 0:
        if x >= max_width or y >= max_height:
            raise MalformedVisionOutputError(
                f"Element origin ({x}, {y}) exceeds screen dimensions ({max_width}x{max_height})"
            )
        # Safely clamp span to screen boundaries if minor overflow
        if x + width > max_width:
            width = max(1, max_width - x)
        if y + height > max_height:
            height = max(1, max_height - y)

    return ScreenElement(
        element_type=element_type,
        label=label,
        text=text,
        confidence=conf,
        x=x,
        y=y,
        width=width,
        height=height,
    )


def validate_screen_description(
    data: Any,
    max_width: int,
    max_height: int,
    max_elements: int = 50,
    max_label_len: int = 100,
    max_summary_len: int = 1000,
) -> ScreenDescription:
    """
    Parse, validate, and constrain a complete ScreenDescription payload from a model or heuristic analyzer.

    Enforces:
    - Must be a valid dictionary (or JSON string).
    - Caps total elements to max_elements (sorted by confidence descending).
    - Bounds summary length.
    - Validates each individual ScreenElement.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception as exc:
            raise MalformedVisionOutputError(
                f"Failed to parse vision model JSON output: {exc}"
            ) from exc

    if not isinstance(data, dict):
        raise MalformedVisionOutputError(
            f"Vision result payload must be a JSON object/dictionary, got {type(data).__name__}"
        )

    # Validate dimensions
    try:
        w = int(data.get("screen_width", max_width))
        h = int(data.get("screen_height", max_height))
    except (ValueError, TypeError):
        w, h = max_width, max_height

    w = max(1, w)
    h = max(1, h)

    # Application and title
    raw_app = str(data.get("application", "unknown")).strip()
    application = raw_app[:100] if raw_app else "unknown"
    raw_title = str(data.get("title", "")).strip()
    title = raw_title[:200]

    # Overall summary
    raw_summary = str(data.get("summary", "")).strip()
    summary = raw_summary[:max_summary_len]

    # Overall confidence
    try:
        overall_conf = float(data.get("confidence", 0.0))
        if overall_conf > 1.0 and overall_conf <= 100.0:
            overall_conf = overall_conf / 100.0
        overall_conf = max(0.0, min(1.0, overall_conf))
    except (ValueError, TypeError):
        overall_conf = 0.0

    # Parse and validate elements
    raw_elements = data.get("elements", [])
    if not isinstance(raw_elements, list):
        raise MalformedVisionOutputError(
            f"'elements' field must be a list, got {type(raw_elements).__name__}"
        )

    valid_elements: List[ScreenElement] = []
    for item in raw_elements:
        try:
            elem = validate_screen_element(
                elem_dict=item,
                max_width=w,
                max_height=h,
                max_label_len=max_label_len,
            )
            valid_elements.append(elem)
        except MalformedVisionOutputError:
            # Skip individually malformed elements if there are others
            continue

    # Sort by confidence descending and truncate to max_elements limit
    valid_elements.sort(key=lambda e: e.confidence, reverse=True)
    if len(valid_elements) > max_elements:
        valid_elements = valid_elements[:max_elements]

    return ScreenDescription(
        screen_width=w,
        screen_height=h,
        application=application,
        title=title,
        elements=valid_elements,
        summary=summary,
        confidence=overall_conf,
    )

