"""CHARVIS Voice Subsystem.

Provides on-demand audio capture, Speech-to-Text (STT), and Text-to-Speech (TTS)
without background monitoring or wake words.
"""

from voice.audio import (
    AudioCapture,
    MicrophoneUnavailableError,
    NoSpeechDetectedError,
    VoiceError,
)
from voice.stt import (
    BaseSTTProvider,
    GoogleWebSTTProvider,
    MockSTTProvider,
    OpenAISTTProvider,
    get_stt_provider,
)
from voice.tts import (
    BaseTTSProvider,
    MockTTSProvider,
    OpenAITTSProvider,
    Pyttsx3TTSProvider,
    get_tts_provider,
    sanitize_speech_text,
)

__all__ = [
    "AudioCapture",
    "VoiceError",
    "MicrophoneUnavailableError",
    "NoSpeechDetectedError",
    "BaseSTTProvider",
    "GoogleWebSTTProvider",
    "OpenAISTTProvider",
    "MockSTTProvider",
    "get_stt_provider",
    "BaseTTSProvider",
    "Pyttsx3TTSProvider",
    "OpenAITTSProvider",
    "MockTTSProvider",
    "get_tts_provider",
    "sanitize_speech_text",
]
