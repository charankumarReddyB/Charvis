"""CHARVIS Speech-to-Text (STT) Subsystem.

Provides provider-independent speech transcription with support for local offline,
web, and OpenAI Whisper providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import io
from typing import Optional

import speech_recognition as sr

from config import get_settings
from logger import get_logger
from voice.audio import NoSpeechDetectedError, VoiceError

logger = get_logger(__name__)


class BaseSTTProvider(ABC):
    """Abstract base class for Speech-to-Text providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifier name for this STT provider."""
        pass

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, language: str = "en-US") -> str:
        """Transcribe WAV-formatted audio bytes into text.

        Args:
            audio_bytes: In-memory WAV audio file bytes.
            language: Language code for transcription.

        Returns:
            str: Transcribed text.

        Raises:
            NoSpeechDetectedError: When silence or unrecognized audio is provided.
            VoiceError: When provider communication or decoding fails.
        """
        pass


class GoogleWebSTTProvider(BaseSTTProvider):
    """Speech transcription using Google Web Speech API via SpeechRecognition.

    Free, built-in, and requires no API key for standard testing.
    """

    def __init__(self) -> None:
        self.recognizer = sr.Recognizer()

    @property
    def provider_name(self) -> str:
        return "google"

    def transcribe(self, audio_bytes: bytes, language: str = "en-US") -> str:
        if not audio_bytes:
            raise NoSpeechDetectedError("Empty audio payload provided for transcription.")

        try:
            with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
                audio_data = self.recognizer.record(source)

            text = self.recognizer.recognize_google(audio_data, language=language)
            logger.info("Google STT transcribed %d bytes of audio: '%s'", len(audio_bytes), text)
            return str(text).strip()
        except sr.UnknownValueError:
            logger.debug("Google STT: No recognizable speech found in audio")
            raise NoSpeechDetectedError("No intelligible speech detected in audio.")
        except sr.RequestError as err:
            logger.error("Google STT service request error: %s", err)
            raise VoiceError(f"STT service connection error: {err}") from err
        except Exception as err:
            logger.error("Unexpected error during STT transcription: %s", err)
            raise VoiceError(f"Transcription failure: {err}") from err


class OpenAISTTProvider(BaseSTTProvider):
    """Cloud-based speech transcription using OpenAI Whisper API."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.openai_api_key

    @property
    def provider_name(self) -> str:
        return "openai"

    def transcribe(self, audio_bytes: bytes, language: str = "en-US") -> str:
        if not self.api_key:
            raise VoiceError("OpenAI API key is not configured for Whisper STT.")
        if not audio_bytes:
            raise NoSpeechDetectedError("Empty audio payload provided for transcription.")

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            audio_file = ("audio.wav", io.BytesIO(audio_bytes), "audio/wav")
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language.split("-")[0],  # e.g. 'en'
            )
            text = transcription.text.strip()
            if not text:
                raise NoSpeechDetectedError("No speech detected by Whisper.")
            logger.info("OpenAI Whisper transcribed audio: '%s'", text)
            return text
        except Exception as err:
            if isinstance(err, (VoiceError, NoSpeechDetectedError)):
                raise
            logger.error("OpenAI Whisper transcription error: %s", err)
            raise VoiceError(f"OpenAI Whisper error: {err}") from err


class MockSTTProvider(BaseSTTProvider):
    """Mock STT provider for deterministic testing without audio hardware or network."""

    def __init__(self, default_response: str = "Hello CHARVIS") -> None:
        self._responses: list[str] = [default_response]
        self._raise_no_speech: bool = False
        self._raise_error: bool = False

    @property
    def provider_name(self) -> str:
        return "mock"

    def queue_transcription(self, text: str) -> None:
        """Queue a transcription result to return on next call."""
        self._responses.append(text)

    def set_raise_no_speech(self, raise_it: bool = True) -> None:
        """Configure mock to raise NoSpeechDetectedError."""
        self._raise_no_speech = raise_it

    def set_raise_error(self, raise_it: bool = True) -> None:
        """Configure mock to raise VoiceError."""
        self._raise_error = raise_it

    def transcribe(self, audio_bytes: bytes, language: str = "en-US") -> str:
        if self._raise_error:
            raise VoiceError("Mock STT provider simulated error")
        if self._raise_no_speech or not audio_bytes:
            raise NoSpeechDetectedError("Mock STT simulated no speech detected")
        if self._responses:
            return self._responses.pop(0)
        return "Mock transcribed utterance"


def get_stt_provider(provider_name: Optional[str] = None) -> BaseSTTProvider:
    """Factory function to instantiate the configured STT provider."""
    settings = get_settings()
    name = (provider_name or settings.stt_provider).strip().lower()

    if name == "google":
        return GoogleWebSTTProvider()
    elif name == "openai":
        return OpenAISTTProvider()
    elif name == "mock":
        return MockSTTProvider()
    else:
        logger.warning("Unknown STT provider '%s', defaulting to Google STT", name)
        return GoogleWebSTTProvider()
