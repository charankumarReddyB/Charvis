"""Unit tests for CHARVIS Text-to-Speech (TTS) Subsystem (Phase 8).

All audio engines and hardware output devices are strictly mocked.
"""

from unittest.mock import MagicMock, patch
import pytest

from voice.audio import VoiceError
from voice.tts import (
    BaseTTSProvider,
    MockTTSProvider,
    OpenAITTSProvider,
    Pyttsx3TTSProvider,
    get_tts_provider,
    sanitize_speech_text,
)


def test_base_tts_provider_abstract() -> None:
    """Ensure BaseTTSProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseTTSProvider()  # type: ignore


def test_sanitize_speech_text_redacts_secrets() -> None:
    """CRITICAL SECURITY: Verify API keys, passwords, and tracebacks are never spoken."""
    # API key
    raw_key_text = "Here is your key: sk-abcdef1234567890abcdef1234567890."
    clean_key = sanitize_speech_text(raw_key_text)
    assert "sk-" not in clean_key
    assert "[REDACTED SECRET]" in clean_key

    # Password
    raw_pass_text = "Your password = MySecretPassword123."
    clean_pass = sanitize_speech_text(raw_pass_text)
    assert "MySecretPassword123" not in clean_pass
    assert "[REDACTED SECRET]" in clean_pass

    # Stack trace
    raw_trace_text = "An error occurred: Traceback (most recent call last): File main.py line 40"
    clean_trace = sanitize_speech_text(raw_trace_text)
    assert "Traceback" not in clean_trace
    assert "[REDACTED SECRET]" in clean_trace


def test_validate_and_sanitize_empty_rejection() -> None:
    """Test validation rejects empty and whitespace-only text."""
    tts = MockTTSProvider()
    with pytest.raises(ValueError, match="empty or whitespace only"):
        tts.validate_and_sanitize("")

    with pytest.raises(ValueError, match="empty or whitespace only"):
        tts.validate_and_sanitize("   \n\t  ")


def test_validate_and_sanitize_truncation() -> None:
    """Test truncation of text exceeding max_length."""
    tts = MockTTSProvider(max_length=50)
    long_text = "A" * 100
    sanitized = tts.validate_and_sanitize(long_text)
    assert len(sanitized) <= 70
    assert "... (truncated)" in sanitized


def test_mock_tts_provider_success() -> None:
    """Test MockTTSProvider records spoken text cleanly in memory."""
    tts = MockTTSProvider()
    assert tts.speak("Hello world") is True
    assert tts.speak("Second message") is True
    assert len(tts.spoken_history) == 2
    assert tts.spoken_history[0] == "Hello world"
    assert tts.spoken_history[1] == "Second message"


def test_mock_tts_provider_simulated_error() -> None:
    """Test MockTTSProvider handles simulated errors."""
    tts = MockTTSProvider()
    tts.set_raise_error(True)
    with pytest.raises(VoiceError, match="simulated error"):
        tts.speak("This should fail")


def test_pyttsx3_tts_provider_success() -> None:
    """Test Pyttsx3TTSProvider invokes engine.say and engine.runAndWait."""
    tts = Pyttsx3TTSProvider()
    mock_engine = MagicMock()
    with patch.object(tts, "_get_engine", return_value=mock_engine):
        res = tts.speak("Test speech output")
        assert res is True
        mock_engine.say.assert_called_once_with("Test speech output")
        mock_engine.runAndWait.assert_called_once()


def test_pyttsx3_tts_provider_failure() -> None:
    """Test Pyttsx3TTSProvider converts engine exceptions to VoiceError."""
    tts = Pyttsx3TTSProvider()
    mock_engine = MagicMock()
    mock_engine.runAndWait.side_effect = RuntimeError("COM error")
    with patch.object(tts, "_get_engine", return_value=mock_engine):
        with pytest.raises(VoiceError, match="audio playback failed"):
            tts.speak("Test speech failure")


def test_openai_tts_missing_key() -> None:
    """Test OpenAITTSProvider raises VoiceError when API key is missing."""
    tts = OpenAITTSProvider(api_key=None)
    with patch("config.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = None
        with pytest.raises(VoiceError, match="OpenAI API key is not configured"):
            tts.speak("Hello")


def test_get_tts_provider_factory() -> None:
    """Test TTS provider factory returns correct instances."""
    assert isinstance(get_tts_provider("pyttsx3"), Pyttsx3TTSProvider)
    assert isinstance(get_tts_provider("openai"), OpenAITTSProvider)
    assert isinstance(get_tts_provider("mock"), MockTTSProvider)
    # Default fallback
    assert isinstance(get_tts_provider("unknown_tts"), Pyttsx3TTSProvider)
