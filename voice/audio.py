"""CHARVIS Audio Capture Subsystem.

Provides controlled, on-demand microphone audio recording with strict resource
cleanup and zero background listening.
"""

from __future__ import annotations

import io
import time
import wave
from typing import Optional

import sounddevice as sd

from logger import get_logger

logger = get_logger(__name__)


class VoiceError(Exception):
    """Base exception for voice subsystem errors."""
    pass


class MicrophoneUnavailableError(VoiceError):
    """Raised when no functional microphone input device is found."""
    pass


class NoSpeechDetectedError(VoiceError):
    """Raised when no audible speech was captured within the timeout."""
    pass


class AudioCapture:
    """Safely captures a single bounded audio utterance from the default microphone.

    Strictly on-demand: never listens in the background or leaves streams open.
    """

    def __init__(self, default_sample_rate: int = 16000) -> None:
        self.default_sample_rate = default_sample_rate

    def is_microphone_available(self) -> bool:
        """Check whether any audio input device is available."""
        try:
            devices = sd.query_devices()
            if not devices:
                return False
            for dev in devices:
                if dev.get("max_input_channels", 0) > 0:
                    return True
            return False
        except Exception as err:
            logger.warning("Microphone availability check failed: %s", err)
            return False

    def record_audio(
        self,
        duration: float = 5.0,
        sample_rate: Optional[int] = None,
        channels: int = 1,
    ) -> bytes:
        """Record a single bounded audio snippet and return standard WAV-encoded bytes.

        Args:
            duration: Maximum recording duration in seconds (0.5 to 30.0).
            sample_rate: Audio sampling rate in Hz (defaults to 16000).
            channels: Number of audio channels (defaults to 1 mono).

        Returns:
            bytes: Complete WAV audio file bytes.

        Raises:
            MicrophoneUnavailableError: If no microphone device is found.
            VoiceError: If recording fails.
        """
        if not self.is_microphone_available():
            logger.error("Attempted audio recording with no microphone available")
            raise MicrophoneUnavailableError("No microphone device is available or accessible on this system.")

        rate = sample_rate or self.default_sample_rate
        clamped_duration = max(0.5, min(30.0, float(duration)))
        total_frames = int(clamped_duration * rate)

        logger.info("Recording microphone audio (duration: %.1fs, rate: %dHz)", clamped_duration, rate)

        try:
            # Record 16-bit signed integer audio
            audio_data = sd.rec(
                total_frames,
                samplerate=rate,
                channels=channels,
                dtype="int16",
                blocking=True,
            )
        except Exception as err:
            logger.error("Audio recording failed during sounddevice.rec: %s", err)
            raise VoiceError(f"Failed to record audio from microphone: {err}") from err

        # Encode PCM data into in-memory standard WAV
        wav_buffer = io.BytesIO()
        try:
            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)  # 16-bit = 2 bytes
                wf.setframerate(rate)
                wf.writeframes(audio_data.tobytes())
            wav_bytes = wav_buffer.getvalue()
        finally:
            wav_buffer.close()

        logger.debug("Captured %d bytes of WAV audio data", len(wav_bytes))
        return wav_bytes
