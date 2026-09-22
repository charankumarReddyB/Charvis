"""CHARVIS Text-to-Speech (TTS) Subsystem.

Provides provider-independent speech generation with local offline Windows SAPI5,
OpenAI TTS, and mock backends.
Enforces strict sanitization to never speak sensitive keys or passwords.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import re
from typing import List, Optional

from config import get_settings
from logger import get_logger
from voice.audio import VoiceError

logger = get_logger(__name__)

# Patterns for sensitive tokens that must NEVER be vocalized
SENSITIVE_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),  # OpenAI / Cloud API Keys
    re.compile(r"(password|passwd|api_key|secret|token)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"Traceback \(most recent call last\):.*", re.DOTALL | re.IGNORECASE),  # Python stack traces
]


def sanitize_speech_text(text: str) -> str:
    """Scrub sensitive credentials, secrets, and raw internal tracebacks from spoken text."""
    clean = text
    for pat in SENSITIVE_PATTERNS:
        clean = pat.sub("[REDACTED SECRET]", clean)
    return clean.strip()


class BaseTTSProvider(ABC):
    """Abstract base class for Text-to-Speech engines."""

    def __init__(self, max_length: Optional[int] = None) -> None:
        self.max_length = max_length or get_settings().max_tts_length

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifier name for this TTS provider."""
        pass

    def validate_and_sanitize(self, text: str) -> str:
        """Validate input text and scrub sensitive secrets.

        Raises:
            ValueError: If text is empty or blank.
        """
        if not text or not text.strip():
            raise ValueError("TTS text cannot be empty or whitespace only.")

        sanitized = sanitize_speech_text(text)

        # Enforce maximum length
        if len(sanitized) > self.max_length:
            logger.warning("TTS text exceeded max length (%d > %d); truncating", len(sanitized), self.max_length)
            sanitized = sanitized[: self.max_length] + "... (truncated)"

        return sanitized

    @abstractmethod
    def speak(self, text: str) -> bool:
        """Vocalize the given text through system audio output.

        Args:
            text: Text message to synthesize into speech.

        Returns:
            bool: True if speech was executed successfully.

        Raises:
            VoiceError: If speech synthesis or audio device output fails.
        """
        pass


class Pyttsx3TTSProvider(BaseTTSProvider):
    """Local, offline TTS provider using Windows SAPI5 via pyttsx3.

    Requires no internet access, no API keys, and has zero network latency.
    """

    def __init__(self, rate: int = 190, volume: float = 1.0, max_length: Optional[int] = None) -> None:
        super().__init__(max_length)
        self.rate = rate
        self.volume = volume
        self._engine = None

    @property
    def provider_name(self) -> str:
        return "pyttsx3"

    def _get_engine(self):
        if self._engine is None:
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", self.rate)
                self._engine.setProperty("volume", self.volume)
            except Exception as err:
                logger.error("Failed to initialize pyttsx3 TTS engine: %s", err)
                raise VoiceError(f"Local TTS engine initialization failed: {err}") from err
        return self._engine

    def speak(self, text: str) -> bool:
        clean_text = self.validate_and_sanitize(text)
        logger.info("Speaking text via pyttsx3 (len: %d chars)", len(clean_text))

        try:
            engine = self._get_engine()
            engine.say(clean_text)
            engine.runAndWait()
            return True
        except Exception as err:
            logger.error("pyttsx3 failed during speech synthesis: %s", err)
            raise VoiceError(f"TTS audio playback failed: {err}") from err


class OpenAITTSProvider(BaseTTSProvider):
    """Cloud-based TTS provider using OpenAI audio speech API."""

    def __init__(self, api_key: Optional[str] = None, voice: str = "alloy", max_length: Optional[int] = None) -> None:
        super().__init__(max_length)
        settings = get_settings()
        self.api_key = api_key or settings.openai_api_key
        self.voice = voice

    @property
    def provider_name(self) -> str:
        return "openai"

    def speak(self, text: str) -> bool:
        if not self.api_key:
            raise VoiceError("OpenAI API key is not configured for OpenAI TTS.")

        clean_text = self.validate_and_sanitize(text)
        logger.info("Synthesizing speech via OpenAI TTS API (len: %d chars)", len(clean_text))

        try:
            import io
            from openai import OpenAI
            import sounddevice as sd
            import soundfile as sf

            client = OpenAI(api_key=self.api_key)
            response = client.audio.speech.create(
                model="tts-1",
                voice=self.voice,
                input=clean_text,
            )
            audio_bytes = response.content
            data, fs = sf.read(io.BytesIO(audio_bytes))
            sd.play(data, fs)
            sd.wait()
            return True
        except Exception as err:
            logger.error("OpenAI TTS synthesis error: %s", err)
            raise VoiceError(f"OpenAI TTS error: {err}") from err


class MockTTSProvider(BaseTTSProvider):
    """Mock TTS provider that records spoken utterances in-memory without playing audio."""

    def __init__(self, max_length: Optional[int] = None) -> None:
        super().__init__(max_length)
        self.spoken_history: List[str] = []
        self._raise_error: bool = False

    @property
    def provider_name(self) -> str:
        return "mock"

    def set_raise_error(self, raise_it: bool = True) -> None:
        self._raise_error = raise_it

    def speak(self, text: str) -> bool:
        if self._raise_error:
            raise VoiceError("Mock TTS provider simulated error")
        clean_text = self.validate_and_sanitize(text)
        self.spoken_history.append(clean_text)
        logger.debug("Mock TTS captured speech: '%s'", clean_text)
        return True


def get_tts_provider(provider_name: Optional[str] = None) -> BaseTTSProvider:
    """Factory function to instantiate the configured TTS provider."""
    settings = get_settings()
    name = (provider_name or settings.tts_provider).strip().lower()

    if name == "pyttsx3":
        return Pyttsx3TTSProvider()
    elif name == "openai":
        return OpenAITTSProvider()
    elif name == "mock":
        return MockTTSProvider()
    else:
        logger.warning("Unknown TTS provider '%s', defaulting to pyttsx3", name)
        return Pyttsx3TTSProvider()
