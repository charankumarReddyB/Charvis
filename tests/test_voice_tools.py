"""Unit and integration tests for CHARVIS Voice Tools (Phase 8).

Verifies ListenTool, SpeakTool, risk classifications, schema validation,
and voice interaction mode loop termination.
"""

from unittest.mock import MagicMock, patch
import pytest

from core.safety import RiskLevel, SafetyManager
from tools.registry import ToolRegistry
from tools.router import ToolRouter
from tools.voice import ListenTool, SpeakTool
from voice.audio import AudioCapture, MicrophoneUnavailableError, NoSpeechDetectedError
from voice.stt import MockSTTProvider
from voice.tts import MockTTSProvider


@pytest.fixture
def mock_audio() -> AudioCapture:
    audio = AudioCapture()
    audio.is_microphone_available = MagicMock(return_value=True)
    audio.record_audio = MagicMock(return_value=b"RIFF_mock_wav_bytes")
    return audio


@pytest.fixture
def mock_stt() -> MockSTTProvider:
    return MockSTTProvider(default_response="Transcribed command")


@pytest.fixture
def mock_tts() -> MockTTSProvider:
    return MockTTSProvider()


def test_listen_tool_metadata_and_risk(mock_audio: AudioCapture, mock_stt: MockSTTProvider) -> None:
    """Verify ListenTool name, description, and SAFE classification."""
    tool = ListenTool(audio_capture=mock_audio, stt_provider=mock_stt)
    assert tool.name == "listen"
    assert tool.risk_level == RiskLevel.SAFE
    assert len(tool.schema.parameters) == 1
    assert tool.schema.parameters[0].name == "duration"


def test_listen_tool_execution_success(mock_audio: AudioCapture, mock_stt: MockSTTProvider) -> None:
    """Test ListenTool captures audio and returns transcription."""
    tool = ListenTool(audio_capture=mock_audio, stt_provider=mock_stt)
    result = tool.execute(duration=3.0)

    assert result["success"] is True
    assert result["transcription"] == "Transcribed command"
    mock_audio.record_audio.assert_called_once_with(duration=3.0)


def test_listen_tool_silence_handling(mock_audio: AudioCapture, mock_stt: MockSTTProvider) -> None:
    """Test ListenTool handles silence without raising unhandled exception."""
    mock_stt.set_raise_no_speech(True)
    tool = ListenTool(audio_capture=mock_audio, stt_provider=mock_stt)
    result = tool.execute()

    assert result["success"] is False
    assert result["transcription"] == ""
    assert "No speech detected" in result["error"]


def test_listen_tool_microphone_unavailable(mock_audio: AudioCapture, mock_stt: MockSTTProvider) -> None:
    """Test ListenTool handles missing microphone gracefully."""
    mock_audio.record_audio.side_effect = MicrophoneUnavailableError("Device unplugged")
    tool = ListenTool(audio_capture=mock_audio, stt_provider=mock_stt)
    result = tool.execute()

    assert result["success"] is False
    assert "Microphone error" in result["error"]


def test_speak_tool_metadata_and_risk(mock_tts: MockTTSProvider) -> None:
    """Verify SpeakTool name, description, and SAFE classification."""
    tool = SpeakTool(tts_provider=mock_tts)
    assert tool.name == "speak"
    assert tool.risk_level == RiskLevel.SAFE
    assert len(tool.schema.parameters) == 1
    assert tool.schema.parameters[0].name == "text"


def test_speak_tool_execution_success(mock_tts: MockTTSProvider) -> None:
    """Test SpeakTool vocalizes text through TTS engine."""
    tool = SpeakTool(tts_provider=mock_tts)
    result = tool.execute(text="Operation completed successfully.")

    assert result["success"] is True
    assert result["spoken_text"] == "Operation completed successfully."
    assert len(mock_tts.spoken_history) == 1
    assert mock_tts.spoken_history[0] == "Operation completed successfully."


def test_speak_tool_empty_text_rejection(mock_tts: MockTTSProvider) -> None:
    """Test SpeakTool rejects empty or blank text."""
    tool = SpeakTool(tts_provider=mock_tts)
    res_empty = tool.execute(text="")
    assert res_empty["success"] is False
    assert "Cannot speak empty" in res_empty["error"]


def test_voice_tools_router_integration(
    mock_audio: AudioCapture, mock_stt: MockSTTProvider, mock_tts: MockTTSProvider
) -> None:
    """Test that ListenTool and SpeakTool execute cleanly through ToolRouter without prompting."""
    registry = ToolRegistry()
    registry.register(ListenTool(audio_capture=mock_audio, stt_provider=mock_stt))
    registry.register(SpeakTool(tts_provider=mock_tts))

    safety = SafetyManager()
    router = ToolRouter(registry, safety)

    # Listen
    res_listen = router.execute_tool("listen", {"duration": 2.0})
    assert res_listen.success is True
    assert res_listen.data["transcription"] == "Transcribed command"

    # Speak
    res_speak = router.execute_tool("speak", {"text": "All systems operational."})
    assert res_speak.success is True
    assert res_speak.data["spoken_text"] == "All systems operational."


def test_voice_mode_exit_condition() -> None:
    """Verify that voice interaction mode terminates cleanly on exit commands."""
    from main import run_voice_mode
    from config import get_settings

    brain = MagicMock()
    settings = get_settings()

    mock_cap = MagicMock()
    mock_cap.is_microphone_available.return_value = True
    mock_cap.record_audio.return_value = b"wav_bytes"

    # User says "exit voice mode"
    mock_stt = MagicMock()
    mock_stt.transcribe.return_value = "exit voice mode"

    mock_tts = MagicMock()

    with patch("voice.audio.AudioCapture", return_value=mock_cap), \
         patch("voice.stt.get_stt_provider", return_value=mock_stt), \
         patch("voice.tts.get_tts_provider", return_value=mock_tts):
        run_voice_mode(brain, settings)

        # Brain was NOT called because exit phrase was intercepted
        brain.process_user_message.assert_not_called()
        # TTS spoke exit confirmation
        mock_tts.speak.assert_called_once_with("Exiting voice mode.")
