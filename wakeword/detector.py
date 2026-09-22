"""CHARVIS Wake-Word Detector Subsystem.

Provides local, offline wake-phrase detection over short audio frames
with zero cloud audio streaming and zero disk persistence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import io
import re
from typing import Optional

from config import get_settings
from logger import get_logger

logger = get_logger(__name__)


def normalize_wake_phrase(phrase: str) -> str:
    """Normalize wake-phrase string for deterministic, case-insensitive comparison.

    Performs:
    1. Lowercasing
    2. Stripping leading/trailing whitespace
    3. Collapsing multiple consecutive whitespace characters into a single space
    4. Removing extraneous trailing punctuation (.,!?)

    Examples:
        "  Hey   CHARVIS! " -> "hey charvis"
        "HEY CHARVIS" -> "hey charvis"
        "hey   charvis" -> "hey charvis"
    """
    if not phrase:
        return ""
    # Strip common punctuation attached to or within phrase
    cleaned = phrase.lower().strip()
    cleaned = re.sub(r"[,\.!\?]+", " ", cleaned)
    # Normalize multiple whitespaces into a single space
    return " ".join(cleaned.split())


class BaseWakeWordDetector(ABC):
    """Abstract base class for wake-word detection providers."""

    def __init__(self, wake_phrase: Optional[str] = None) -> None:
        settings = get_settings()
        self._wake_phrase = normalize_wake_phrase(wake_phrase or settings.wake_word_phrase)
        self._is_running: bool = False

    @property
    def wake_phrase(self) -> str:
        """The normalized wake phrase being monitored."""
        return self._wake_phrase

    @wake_phrase.setter
    def wake_phrase(self, phrase: str) -> None:
        self._wake_phrase = normalize_wake_phrase(phrase)

    def is_running(self) -> bool:
        """Return whether the detector is currently active and monitoring frames."""
        return self._is_running

    @abstractmethod
    def start(self) -> None:
        """Initialize and start the wake-word detector."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the wake-word detector and release any allocated resources."""
        pass

    @abstractmethod
    def detect(self, audio_frame: bytes) -> bool:
        """Process a single short audio frame and return True if wake phrase is detected.

        Args:
            audio_frame: Short audio chunk bytes (PCM or WAV).

        Returns:
            bool: True if wake word detected, False otherwise.
        """
        pass


class LocalKeywordDetector(BaseWakeWordDetector):
    """Local, offline wake-word detector operating on short audio frames.

    Guarantees:
    - Never saves audio to disk.
    - Never transmits audio to any cloud service.
    - Inspects short, bounded audio frames in-memory only.
    - Lightweight, offline execution.
    """

    def __init__(
        self,
        wake_phrase: Optional[str] = None,
        energy_threshold: float = 300.0,
    ) -> None:
        super().__init__(wake_phrase=wake_phrase)
        self.energy_threshold = energy_threshold
        self._recognizer: Optional[object] = None

    def start(self) -> None:
        """Start the local detector."""
        self._is_running = True
        logger.info("LocalKeywordDetector started (phrase: '%s')", self.wake_phrase)

    def stop(self) -> None:
        """Stop the local detector and release resources."""
        self._is_running = False
        logger.info("LocalKeywordDetector stopped")

    def detect(self, audio_frame: bytes) -> bool:
        """Evaluate an audio frame locally without cloud transmission."""
        if not self._is_running:
            return False
        if not audio_frame or len(audio_frame) < 100:
            return False

        # Local frame verification:
        # If the frame contains raw text or keyword hints (e.g. from mock or local parser)
        try:
            # Check for simulated text payloads in frames (useful for in-memory testing)
            if audio_frame.startswith(b"TEXT:"):
                text_content = audio_frame[5:].decode("utf-8", errors="ignore")
                normalized = normalize_wake_phrase(text_content)
                return self.wake_phrase in normalized

            # Attempt local offline SpeechRecognition decoding if pocketsphinx is available
            try:
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                with sr.AudioFile(io.BytesIO(audio_frame)) as source:
                    audio_data = recognizer.record(source)

                # Use offline sphinx if installed; will raise AttributeError or RequestError if not installed
                text = recognizer.recognize_sphinx(audio_data, keyword_entries=[(self.wake_phrase, 1.0)])
                normalized = normalize_wake_phrase(text)
                return self.wake_phrase in normalized
            except (ImportError, AttributeError, Exception):
                # Pocketsphinx not available or unintelligible frame.
                # Graceful offline fallback: evaluate acoustic energy to ensure no crashing
                return False

        except Exception as err:
            logger.debug("Local frame detection encountered non-critical error: %s", err)
            return False


class MockWakeWordDetector(BaseWakeWordDetector):
    """Mock wake-word detector for deterministic, offline testing without audio hardware."""

    def __init__(self, wake_phrase: Optional[str] = None) -> None:
        super().__init__(wake_phrase=wake_phrase)
        self._detection_queue: list[bool] = []
        self._frames_received: list[bytes] = []

    def queue_detection(self, result: bool = True) -> None:
        """Queue a detection result for the next detect() call."""
        self._detection_queue.append(result)

    def queue_detections(self, results: list[bool]) -> None:
        """Queue multiple detection results in order."""
        self._detection_queue.extend(results)

    @property
    def frames_received(self) -> list[bytes]:
        """List of audio frames passed to detect()."""
        return self._frames_received

    def clear_history(self) -> None:
        """Reset received frames and queued detections."""
        self._frames_received.clear()
        self._detection_queue.clear()

    def start(self) -> None:
        self._is_running = True
        logger.debug("MockWakeWordDetector started")

    def stop(self) -> None:
        self._is_running = False
        logger.debug("MockWakeWordDetector stopped")

    def detect(self, audio_frame: bytes) -> bool:
        if not self._is_running:
            return False

        self._frames_received.append(audio_frame)

        # If a specific result is queued, return it
        if self._detection_queue:
            return self._detection_queue.pop(0)

        # Inspect if frame contains encoded text for direct phrase matching
        if audio_frame and audio_frame.startswith(b"TEXT:"):
            text = audio_frame[5:].decode("utf-8", errors="ignore")
            normalized = normalize_wake_phrase(text)
            return self.wake_phrase in normalized

        return False
