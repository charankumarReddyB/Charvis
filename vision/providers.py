"""
Vision provider abstraction and implementations for CHARVIS.
Phase 12: Vision / Screen Understanding.

Provides:
- BaseVisionProvider: Abstract interface for vision comprehension.
- LocalHeuristicVisionProvider: Default 100% local, zero-cloud visual parsing using layout & OCR.
- MockVisionProvider: Deterministic in-memory mock for automated unit and regression testing.
- OpenAIVisionProvider: Multimodal cloud vision provider guarded by explicit user authorization.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import base64
import io
import json
import logging
from typing import Any, Dict, List, Optional

from PIL import Image

from config import Settings, get_settings
from vision.models import (
    MalformedVisionOutputError,
    OCRResult,
    ScreenDescription,
    ScreenElement,
    VisionCloudDisabledError,
    VisionModelError,
    VisionProviderUnavailableError,
    VisionTimeoutError,
)
from vision.security import check_cloud_vision_allowed, validate_screen_description

logger = logging.getLogger(__name__)

# Common UI keywords for local heuristic classification
BUTTON_KEYWORDS = {
    "ok", "cancel", "save", "apply", "close", "yes", "no", "submit",
    "next", "back", "settings", "search", "start", "run", "open",
    "new", "edit", "file", "view", "help", "options", "done", "delete",
    "remove", "continue", "retry", "accept", "decline", "send",
}

INPUT_KEYWORDS = {
    "search", "type here", "find", "enter", "username", "password",
    "email", "query", "filter", "address",
}

KNOWN_APPLICATIONS = [
    ("Notepad", ["notepad", "untitled - notepad"]),
    ("Google Chrome", ["chrome", "google chrome"]),
    ("Mozilla Firefox", ["firefox", "mozilla firefox"]),
    ("Microsoft Edge", ["edge", "microsoft edge"]),
    ("Visual Studio Code", ["code", "visual studio code", "vscode"]),
    ("Calculator", ["calculator"]),
    ("Command Prompt", ["cmd", "command prompt"]),
    ("PowerShell", ["powershell", "windows powershell"]),
    ("Windows Terminal", ["terminal", "windows terminal"]),
    ("Settings", ["settings", "windows settings"]),
    ("File Explorer", ["explorer", "file explorer", "this pc"]),
    ("Task Manager", ["task manager"]),
    ("Word", ["word", "microsoft word"]),
    ("Excel", ["excel", "microsoft excel"]),
]


class BaseVisionProvider(ABC):
    """Abstract base class for CHARVIS visual understanding engines."""

    @abstractmethod
    def analyze(
        self,
        image: Image.Image,
        context: Optional[str] = None,
        ocr_result: Optional[OCRResult] = None,
    ) -> ScreenDescription:
        """
        Analyze an in-memory desktop or region image and produce structured screen understanding.

        :param image: PIL Image of the screen or region.
        :param context: Optional guiding query (e.g. 'find the Settings button').
        :param ocr_result: Optional pre-extracted OCR text and bounding boxes.
        :return: Validated ScreenDescription object.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider can currently process vision queries."""
        pass


# ---------------------------------------------------------------------------
# 1. Local Heuristic Vision Provider (Default, 100% Private, Zero Cloud)
# ---------------------------------------------------------------------------

class LocalHeuristicVisionProvider(BaseVisionProvider):
    """
    Local layout and visual heuristics engine.
    Derives structured UI elements, application name, title, and summary
    using in-memory PIL image metrics and Phase 11 OCR bounding boxes.
    Guarantees 100% privacy: zero images or text ever leave the computer.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()

    def is_available(self) -> bool:
        return True

    def analyze(
        self,
        image: Image.Image,
        context: Optional[str] = None,
        ocr_result: Optional[OCRResult] = None,
    ) -> ScreenDescription:
        if image is None:
            raise VisionModelError("Cannot analyze a None image.")

        img_w, img_h = image.size
        detected_elements: List[ScreenElement] = []
        app_name = "unknown"
        detected_title = ""

        # Use OCR results if provided
        blocks = ocr_result.blocks if ocr_result else []

        # 1. Identify Active Application & Title Bar
        # Check top 25% of the screen for title bar patterns
        top_cutoff = int(img_h * 0.25)
        top_blocks = [b for b in blocks if b.y <= top_cutoff]

        for block in top_blocks:
            clean_text = block.text.strip()
            lower_text = clean_text.lower()
            for app_display, match_tokens in KNOWN_APPLICATIONS:
                if any(token in lower_text for token in match_tokens):
                    app_name = app_display
                    detected_title = clean_text
                    break
            if app_name != "unknown":
                break

        # If a top block looks like a title but didn't match known apps
        if app_name == "unknown" and top_blocks:
            first_block = top_blocks[0]
            if len(first_block.text) > 3:
                detected_title = first_block.text

        # 2. Add Top-Level Window Element if title/app detected
        if app_name != "unknown" or detected_title:
            window_label = detected_title or app_name
            detected_elements.append(
                ScreenElement(
                    element_type="window",
                    label=window_label[: self._settings.max_element_label_length],
                    text=window_label[: self._settings.max_element_label_length],
                    confidence=0.85,
                    x=0,
                    y=0,
                    width=img_w,
                    height=img_h,
                )
            )

        # 3. Categorize OCR blocks into UI elements (Buttons, Inputs, Text)
        for b in blocks:
            clean_word = b.text.strip()
            if not clean_word:
                continue

            lower_word = clean_word.lower()

            # Check if button keyword
            if lower_word in BUTTON_KEYWORDS:
                detected_elements.append(
                    ScreenElement(
                        element_type="button",
                        label=clean_word[: self._settings.max_element_label_length],
                        text=clean_word,
                        confidence=round(min(1.0, (b.confidence / 100.0) * 0.9), 2),
                        x=b.x,
                        y=b.y,
                        width=b.width,
                        height=b.height,
                    )
                )
            # Check if input field prompt
            elif any(prompt in lower_word for prompt in INPUT_KEYWORDS):
                detected_elements.append(
                    ScreenElement(
                        element_type="input",
                        label=clean_word[: self._settings.max_element_label_length],
                        text=clean_word,
                        confidence=0.70,
                        x=b.x,
                        y=b.y,
                        width=max(b.width, 100),
                        height=max(b.height, 24),
                    )
                )
            else:
                # Default text element
                detected_elements.append(
                    ScreenElement(
                        element_type="text",
                        label=clean_word[: self._settings.max_element_label_length],
                        text=clean_word,
                        confidence=round(min(1.0, b.confidence / 100.0), 2),
                        x=b.x,
                        y=b.y,
                        width=b.width,
                        height=b.height,
                    )
                )

        # 4. Generate structured human-readable summary
        btn_count = sum(1 for e in detected_elements if e.element_type == "button")
        inp_count = sum(1 for e in detected_elements if e.element_type == "input")
        txt_count = sum(1 for e in detected_elements if e.element_type == "text")

        summary_parts = [
            f"Screen dimensions {img_w}x{img_h} px.",
            f"Active application: '{app_name}'." if app_name != "unknown" else "Active application could not be uniquely identified.",
        ]
        if detected_title:
            summary_parts.append(f"Window title: '{detected_title}'.")
        summary_parts.append(
            f"Detected {len(detected_elements)} visual elements: {btn_count} buttons, {inp_count} inputs, {txt_count} text blocks."
        )
        if context:
            summary_parts.append(f"Query context: '{context}'.")

        summary = " ".join(summary_parts)

        # Validate through central security validator to enforce limits and boundary rules
        raw_payload = {
            "screen_width": img_w,
            "screen_height": img_h,
            "application": app_name,
            "title": detected_title,
            "elements": [e.to_dict() for e in detected_elements],
            "summary": summary,
            "confidence": 0.75 if app_name != "unknown" else 0.50,
        }

        return validate_screen_description(
            data=raw_payload,
            max_width=img_w,
            max_height=img_h,
            max_elements=self._settings.max_screen_elements,
            max_label_len=self._settings.max_element_label_length,
            max_summary_len=self._settings.max_screen_summary_length,
        )


# ---------------------------------------------------------------------------
# 2. Mock Vision Provider (Deterministic Testing)
# ---------------------------------------------------------------------------

class MockVisionProvider(BaseVisionProvider):
    """
    Deterministic in-memory vision provider for automated unit and regression tests.
    Allows pre-configuring exact responses, error simulation, and call inspection.
    """

    def __init__(
        self,
        default_description: Optional[ScreenDescription] = None,
        available: bool = True,
        error_to_raise: Optional[Exception] = None,
    ) -> None:
        self._default_description = default_description
        self._available = available
        self._error_to_raise = error_to_raise
        self.call_count: int = 0
        self.last_image: Optional[Image.Image] = None
        self.last_context: Optional[str] = None
        self.last_ocr_result: Optional[OCRResult] = None

    def is_available(self) -> bool:
        return self._available

    def set_available(self, available: bool) -> None:
        self._available = available

    def set_error(self, error: Optional[Exception]) -> None:
        self._error_to_raise = error

    def set_response(self, description: ScreenDescription) -> None:
        self._default_description = description

    def analyze(
        self,
        image: Image.Image,
        context: Optional[str] = None,
        ocr_result: Optional[OCRResult] = None,
    ) -> ScreenDescription:
        self.call_count += 1
        self.last_image = image
        self.last_context = context
        self.last_ocr_result = ocr_result

        if self._error_to_raise is not None:
            raise self._error_to_raise

        if not self._available:
            raise VisionProviderUnavailableError("Mock vision provider is marked unavailable.")

        if self._default_description is not None:
            return self._default_description

        w = image.size[0] if image else 1920
        h = image.size[1] if image else 1080

        # Return a deterministic baseline ScreenDescription
        return ScreenDescription(
            screen_width=w,
            screen_height=h,
            application="MockApp",
            title="Mock Window Title",
            elements=[
                ScreenElement(
                    element_type="window",
                    label="MockApp",
                    text="MockApp",
                    confidence=0.95,
                    x=0,
                    y=0,
                    width=w,
                    height=h,
                ),
                ScreenElement(
                    element_type="button",
                    label="Settings",
                    text="Settings",
                    confidence=0.90,
                    x=100,
                    y=200,
                    width=80,
                    height=30,
                ),
                ScreenElement(
                    element_type="input",
                    label="Search",
                    text="Search",
                    confidence=0.85,
                    x=200,
                    y=200,
                    width=150,
                    height=30,
                ),
            ],
            summary="Mock screen description with MockApp and Settings button.",
            confidence=0.90,
        )


# ---------------------------------------------------------------------------
# 3. OpenAI Multimodal Cloud Vision Provider (Opt-in Cloud Vision)
# ---------------------------------------------------------------------------

class OpenAIVisionProvider(BaseVisionProvider):
    """
    Multimodal vision provider using OpenAI chat completions API (e.g. gpt-4o-mini).
    CRITICAL: Guarded by check_cloud_vision_allowed. Screenshots are never transmitted
    unless VISION_CLOUD_ENABLED is explicitly set to true.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[Any] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    def is_available(self) -> bool:
        # Must have cloud enabled and API key configured
        return (
            getattr(self._settings, "vision_cloud_enabled", False)
            and self._settings.is_api_key_configured
        )

    def analyze(
        self,
        image: Image.Image,
        context: Optional[str] = None,
        ocr_result: Optional[OCRResult] = None,
    ) -> ScreenDescription:
        # 1. Enforce strict privacy check before anything else
        check_cloud_vision_allowed(self._settings)

        if not self._settings.is_api_key_configured:
            raise VisionProviderUnavailableError(
                "OPENAI_API_KEY is not configured in .env file."
            )

        if image is None:
            raise VisionModelError("Cannot analyze a None image.")

        img_w, img_h = image.size

        # 2. Encode image to Base64 in memory (no disk saving)
        buffered = io.BytesIO()
        # Convert RGBA to RGB for JPEG compression
        rgb_img = image.convert("RGB") if image.mode != "RGB" else image
        rgb_img.save(buffered, format="JPEG", quality=85)
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt = (
            "Analyze this Windows desktop screenshot and produce a structured JSON representation of visible UI elements.\n"
            "Return a single valid JSON object strictly matching this schema:\n"
            "{\n"
            f'  "screen_width": {img_w},\n'
            f'  "screen_height": {img_h},\n'
            '  "application": "<detected application name or unknown>",\n'
            '  "title": "<window title if visible>",\n'
            '  "summary": "<concise 2-3 sentence overview of visible screen>",\n'
            '  "confidence": <float 0.0 to 1.0>,\n'
            '  "elements": [\n'
            '    {\n'
            '      "element_type": "<window|button|text|input|checkbox|radio|dropdown|menu|icon|image|dialog|tab|link|unknown>",\n'
            '      "label": "<short label>",\n'
            '      "text": "<visible text>",\n'
            '      "confidence": <float 0.0 to 1.0>,\n'
            '      "x": <int>,\n'
            '      "y": <int>,\n'
            '      "width": <int>,\n'
            '      "height": <int>\n'
            '    }\n'
            '  ]\n'
            "}\n"
            "Do NOT wrap output in markdown fences. Return ONLY the raw JSON object.\n"
        )
        if context:
            prompt += f"User focus query: {context}\n"

        try:
            import openai

            if self._client is not None:
                client = self._client
            else:
                client = openai.OpenAI(
                    api_key=self._settings.openai_api_key.get_secret_value(),
                    base_url=str(self._settings.openai_base_url).rstrip("/") if self._settings.openai_base_url else None,
                    timeout=float(self._settings.vision_timeout),
                )

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_b64}",
                                "detail": "low",
                            },
                        },
                    ],
                }
            ]

            response = client.chat.completions.create(
                model=self._settings.vision_model,
                messages=messages,
                max_tokens=1024,
                temperature=0.2,
            )
            content = response.choices[0].message.content or ""

            return validate_screen_description(
                data=content,
                max_width=img_w,
                max_height=img_h,
                max_elements=self._settings.max_screen_elements,
                max_label_len=self._settings.max_element_label_length,
                max_summary_len=self._settings.max_screen_summary_length,
            )
        except openai.APITimeoutError as exc:
            raise VisionTimeoutError(f"OpenAI vision API request timed out: {exc}") from exc
        except openai.OpenAIError as exc:
            raise VisionModelError(f"OpenAI vision API error: {exc}") from exc
        except VisionCloudDisabledError:
            raise
        except (VisionModelError, MalformedVisionOutputError):
            raise
        except Exception as exc:
            raise VisionModelError(f"Unexpected vision model failure: {exc}") from exc


# ---------------------------------------------------------------------------
# Factory Function
# ---------------------------------------------------------------------------

def get_vision_provider(
    provider_type: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> BaseVisionProvider:
    """
    Factory function returning the configured vision provider instance.
    Defaults to LocalHeuristicVisionProvider unless explicitly configured.
    """
    curr_settings = settings or get_settings()
    ptype = (provider_type or curr_settings.vision_provider_type).strip().lower()

    if ptype == "mock":
        return MockVisionProvider()
    elif ptype == "openai":
        return OpenAIVisionProvider(curr_settings)
    else:
        # Default to local heuristic provider (100% private, offline)
        return LocalHeuristicVisionProvider(curr_settings)
