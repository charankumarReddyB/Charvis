"""Unit tests for CHARVIS Speech-to-Text (STT) Subsystem (Phase 8).

All audio devices and remote STT APIs are strictly mocked.
"""

from unittest.mock import MagicMock, patch
import pytest

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


def test_base_stt_provider_abstract() -> None:
    """Ensure BaseSTTProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseSTTProvider()  # type: ignore


def test_mock_stt_provider_success() -> None:
    """Test MockSTTProvider returns queued transcriptions."""
    stt = MockSTTProvider(default_response="First utterance")
    stt.queue_transcription("Second utterance")

    assert stt.transcribe(b"dummy_audio") == "First utterance"
    assert stt.transcribe(b"dummy_audio") == "Second utterance"
    # Fallback default
    assert "Mock" in stt.transcribe(b"dummy_audio")


def test_mock_stt_provider_no_speech_and_error() -> None:
    """Test MockSTTProvider raises expected errors when configured."""
    stt = MockSTTProvider()

    # Empty audio
    with pytest.raises(NoSpeechDetectedError):
        stt.transcribe(b"")

    # Explicit no speech flag
    stt.set_raise_no_speech(True)
    with pytest.raises(NoSpeechDetectedError):
        stt.transcribe(b"dummy_audio")

    # Explicit error flag
    stt.set_raise_no_speech(False)
    stt.set_raise_error(True)
    with pytest.raises(VoiceError, match="simulated error"):
        stt.transcribe(b"dummy_audio")


def test_google_stt_provider_empty_audio() -> None:
    """Test GoogleWebSTTProvider rejects empty audio with NoSpeechDetectedError."""
    stt = GoogleWebSTTProvider()
    with pytest.raises(NoSpeechDetectedError):
        stt.transcribe(b"")


def test_google_stt_provider_success() -> None:
    """Test GoogleWebSTTProvider parses speech with mocked SpeechRecognition."""
    stt = GoogleWebSTTProvider()
    with patch("speech_recognition.AudioFile"), \
         patch.object(stt.recognizer, "record"), \
         patch.object(stt.recognizer, "recognize_google", return_value="Open Notepad") as mock_rec:
        result = stt.transcribe(b"valid_wav_bytes", language="en-US")
        assert result == "Open Notepad"
        mock_rec.assert_called_once()


def test_google_stt_provider_silence_handling() -> None:
    """Test GoogleWebSTTProvider handles silence (UnknownValueError)."""
    import speech_recognition as sr

    stt = GoogleWebSTTProvider()
    with patch("speech_recognition.AudioFile"), \
         patch.object(stt.recognizer, "record"), \
         patch.object(stt.recognizer, "recognize_google", side_effect=sr.UnknownValueError):
        with pytest.raises(NoSpeechDetectedError, match="No intelligible speech"):
            stt.transcribe(b"silent_wav_bytes")


def test_google_stt_provider_service_error() -> None:
    """Test GoogleWebSTTProvider handles service request error."""
    import speech_recognition as sr

    stt = GoogleWebSTTProvider()
    with patch("speech_recognition.AudioFile"), \
         patch.object(stt.recognizer, "record"), \
         patch.object(stt.recognizer, "recognize_google", side_effect=sr.RequestError("Network drop")):
        with pytest.raises(VoiceError, match="STT service connection error"):
            stt.transcribe(b"wav_bytes")


def test_openai_stt_missing_api_key() -> None:
    """Test OpenAISTTProvider raises VoiceError when API key is missing."""
    stt = OpenAISTTProvider(api_key=None)
    with patch("config.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = None
        with pytest.raises(VoiceError, match="OpenAI API key is not configured"):
            stt.transcribe(b"audio_bytes")


def test_audio_capture_availability() -> None:
    """Test AudioCapture checks input device presence."""
    capture = AudioCapture()

    with patch("sounddevice.query_devices", return_value=[{"max_input_channels": 2}]):
        assert capture.is_microphone_available() is True

    with patch("sounddevice.query_devices", return_value=[{"max_input_channels": 0}]):
        assert capture.is_microphone_available() is False

    with patch("sounddevice.query_devices", side_effect=RuntimeError("Device error")):
        assert capture.is_microphone_available() is False


def test_audio_capture_record_unavailable_mic() -> None:
    """Test record_audio raises MicrophoneUnavailableError if no mic is found."""
    capture = AudioCapture()
    with patch.object(capture, "is_microphone_available", return_value=False):
        with pytest.raises(MicrophoneUnavailableError):
            capture.record_audio(duration=2.0)


def test_audio_capture_record_success() -> None:
    """Test record_audio generates valid WAV header bytes."""
    capture = AudioCapture()

    mock_audio_obj = MagicMock()
    mock_audio_obj.tobytes.return_value = b"\x00" * 32000  # 16000 int16 samples
    with patch.object(capture, "is_microphone_available", return_value=True), \
         patch("sounddevice.rec", return_value=mock_audio_obj):
        wav_bytes = capture.record_audio(duration=1.0)
        assert len(wav_bytes) > 44  # WAV header is 44 bytes
        assert wav_bytes.startswith(b"RIFF")


def test_get_stt_provider_factory() -> None:
    """Test STT provider factory returns correct instances."""
    assert isinstance(get_stt_provider("google"), GoogleWebSTTProvider)
    assert isinstance(get_stt_provider("openai"), OpenAISTTProvider)
    assert isinstance(get_stt_provider("mock"), MockSTTProvider)
    # Default fallback
    assert isinstance(get_stt_provider("unknown_provider"), GoogleWebSTTProvider)
