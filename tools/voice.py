"""CHARVIS Voice Tools.

Provides on-demand listen (STT) and speak (TTS) tools registered within the
CHARVIS tool-calling cognitive loop.
Zero background listening, zero wake words.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.safety import RiskLevel
from tools.base import BaseTool
from tools.schemas import ToolParameter, ToolSchema
from voice.audio import (
    AudioCapture,
    MicrophoneUnavailableError,
    NoSpeechDetectedError,
    VoiceError,
)
from voice.stt import BaseSTTProvider, get_stt_provider
from voice.tts import BaseTTSProvider, get_tts_provider


class ListenTool(BaseTool):
    """Tool to capture a single spoken audio utterance from the microphone and transcribe it."""

    def __init__(
        self,
        audio_capture: Optional[AudioCapture] = None,
        stt_provider: Optional[BaseSTTProvider] = None,
    ) -> None:
        self._audio = audio_capture or AudioCapture()
        self._stt = stt_provider or get_stt_provider()

    @property
    def name(self) -> str:
        return "listen"

    @property
    def description(self) -> str:
        return (
            "Capture a single spoken utterance from the microphone and return its transcribed text. "
            "Safe and bounded: listens once for a limited duration and immediately closes the microphone."
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
                    name="duration",
                    param_type="number",
                    description="Maximum listening duration in seconds (1.0 to 15.0, default: 5.0)",
                    required=False,
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        duration = float(kwargs.get("duration", 5.0))
        duration = max(1.0, min(15.0, duration))

        try:
            audio_bytes = self._audio.record_audio(duration=duration)
            transcription = self._stt.transcribe(audio_bytes)
            return {
                "success": True,
                "transcription": transcription,
            }
        except NoSpeechDetectedError:
            return {
                "success": False,
                "transcription": "",
                "error": "No speech detected in audio input.",
            }
        except MicrophoneUnavailableError as err:
            return {
                "success": False,
                "error": f"Microphone error: {err}",
            }
        except VoiceError as err:
            return {
                "success": False,
                "error": f"Voice recognition failure: {err}",
            }


class SpeakTool(BaseTool):
    """Tool to vocalize a message using text-to-speech output."""

    def __init__(self, tts_provider: Optional[BaseTTSProvider] = None) -> None:
        self._tts = tts_provider or get_tts_provider()

    @property
    def name(self) -> str:
        return "speak"

    @property
    def description(self) -> str:
        return (
            "Speak a message aloud using text-to-speech audio output. "
            "Safe operation with built-in secret sanitization."
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
                    description="Text message to vocalize through the speaker",
                    required=True,
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        text = str(kwargs.get("text", "")).strip()
        if not text:
            return {
                "success": False,
                "error": "Cannot speak empty or blank text.",
            }

        try:
            self._tts.speak(text)
            return {
                "success": True,
                "spoken_text": text,
            }
        except Exception as err:
            return {
                "success": False,
                "error": f"TTS synthesis failed: {err}",
            }
