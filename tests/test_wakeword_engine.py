"""Tests for Wake-Word Engine and State Machine (Phase 9).

Verifies the state machine lifecycle, transition guards, command stripping,
timeout handling, resource cleanup, safety gate enforcement, and privacy guarantees.
"""

from unittest.mock import MagicMock, patch
import pytest

from core.brain import AIBrain
from core.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from core.safety import RiskLevel, SafetyManager
from voice.audio import AudioCapture, MicrophoneUnavailableError, NoSpeechDetectedError
from voice.stt import MockSTTProvider
from voice.tts import MockTTSProvider
from wakeword.detector import MockWakeWordDetector
from wakeword.engine import (
    InvalidStateTransitionError,
    WakeWordEngine,
    WakeWordState,
)


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM Provider for deterministic brain responses and tool calls."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-model"

    def generate_response(self, messages, tools=None, temperature=0.7, max_tokens=None) -> LLMResponse:
        if self._responses:
            return self._responses.pop(0)
        return LLMResponse(content="Mock response", tool_calls=[])


@pytest.fixture
def mock_engine():
    """Create a fully-mocked WakeWordEngine instance."""
    provider = MockLLMProvider([LLMResponse(content="I am ready.", tool_calls=[])])
    brain = AIBrain(provider=provider)
    detector = MockWakeWordDetector(wake_phrase="hey charvis")
    stt = MockSTTProvider(default_response="what time is it")
    tts = MockTTSProvider()
    capture = MagicMock(spec=AudioCapture)
    capture.is_microphone_available.return_value = True
    capture.record_audio.return_value = b"RIFFmockaudiobytes12345"

    engine = WakeWordEngine(
        brain=brain,
        detector=detector,
        audio_capture=capture,
        stt_provider=stt,
        tts_provider=tts,
    )
    return engine


def test_initial_state_is_stopped(mock_engine) -> None:
    """Verify engine starts in STOPPED state."""
    assert mock_engine.state == WakeWordState.STOPPED


def test_start_transitions_to_standby(mock_engine) -> None:
    """Verify starting the engine moves from STOPPED to STANDBY."""
    mock_engine.start()
    assert mock_engine.state == WakeWordState.STANDBY
    assert mock_engine.detector.is_running() is True


def test_stop_transitions_to_stopped(mock_engine) -> None:
    """Verify stopping the engine moves to STOPPED."""
    mock_engine.start()
    mock_engine.stop()
    assert mock_engine.state == WakeWordState.STOPPED
    assert mock_engine.detector.is_running() is False


def test_valid_state_transitions(mock_engine) -> None:
    """Verify that all legal transitions succeed according to the state machine."""
    mock_engine.start()  # STOPPED -> STANDBY
    assert mock_engine.state == WakeWordState.STANDBY

    mock_engine.transition_to(WakeWordState.LISTENING)  # STANDBY -> LISTENING
    assert mock_engine.state == WakeWordState.LISTENING

    mock_engine.transition_to(WakeWordState.PROCESSING)  # LISTENING -> PROCESSING
    assert mock_engine.state == WakeWordState.PROCESSING

    mock_engine.transition_to(WakeWordState.SPEAKING)  # PROCESSING -> SPEAKING
    assert mock_engine.state == WakeWordState.SPEAKING

    mock_engine.transition_to(WakeWordState.STANDBY)  # SPEAKING -> STANDBY
    assert mock_engine.state == WakeWordState.STANDBY

    mock_engine.transition_to(WakeWordState.ERROR)  # STANDBY -> ERROR
    assert mock_engine.state == WakeWordState.ERROR

    mock_engine.transition_to(WakeWordState.STANDBY)  # ERROR -> STANDBY
    assert mock_engine.state == WakeWordState.STANDBY

    mock_engine.stop()  # STANDBY -> STOPPED
    assert mock_engine.state == WakeWordState.STOPPED


def test_invalid_state_transitions_raise_error(mock_engine) -> None:
    """Verify illegal state transitions raise InvalidStateTransitionError."""
    # Cannot jump directly from STOPPED to PROCESSING or SPEAKING
    assert mock_engine.state == WakeWordState.STOPPED
    with pytest.raises(InvalidStateTransitionError):
        mock_engine.transition_to(WakeWordState.PROCESSING)

    with pytest.raises(InvalidStateTransitionError):
        mock_engine.transition_to(WakeWordState.SPEAKING)

    # Move to STANDBY
    mock_engine.start()
    # Cannot jump from STANDBY directly to SPEAKING
    with pytest.raises(InvalidStateTransitionError):
        mock_engine.transition_to(WakeWordState.SPEAKING)

    # Cannot jump from LISTENING directly to SPEAKING without PROCESSING
    mock_engine.transition_to(WakeWordState.LISTENING)
    with pytest.raises(InvalidStateTransitionError):
        mock_engine.transition_to(WakeWordState.SPEAKING)


def test_wake_phrase_is_stripped_from_command(mock_engine) -> None:
    """Verify wake phrase prefix is completely stripped from user command."""
    assert mock_engine.strip_wake_phrase("Hey CHARVIS, open notepad") == "open notepad"
    assert mock_engine.strip_wake_phrase("hey charvis what is my cpu usage") == "what is my cpu usage"
    assert mock_engine.strip_wake_phrase("HEY CHARVIS!") == ""
    assert mock_engine.strip_wake_phrase("open notepad") == "open notepad"


def test_wake_word_activates_stt_and_cycles_to_standby(mock_engine) -> None:
    """Verify wake word triggers cue, STT transcribe, cognitive processing, and returns to STANDBY."""
    mock_engine.start()
    mock_engine.detector.queue_detection(True)

    # Queue STT response
    mock_engine.stt_provider.queue_transcription("Hey CHARVIS, what is polymorphism")

    result = mock_engine.process_frame(b"audio_frame_sample")

    assert result is True
    # Verify cue was spoken
    assert "Yes?" in mock_engine.tts_provider.spoken_history
    # Returned to STANDBY
    assert mock_engine.state == WakeWordState.STANDBY


def test_command_timeout_returns_to_standby(mock_engine) -> None:
    """Verify silence / timeout after wake detection safely returns to STANDBY without recording forever."""
    mock_engine.start()
    mock_engine.detector.queue_detection(True)

    # Configure STT to simulate silence
    mock_engine.stt_provider.set_raise_no_speech(True)

    result = mock_engine.process_frame(b"audio_frame_sample")

    assert result is True
    # System safely returns to STANDBY
    assert mock_engine.state == WakeWordState.STANDBY


def test_error_state_and_safe_recovery(mock_engine) -> None:
    """Verify that exceptions during processing transition through ERROR and recover to STANDBY."""
    mock_engine.start()
    mock_engine.detector.queue_detection(True)

    # Force an unhandled exception inside brain
    with patch.object(mock_engine.brain, "process_user_message", side_effect=RuntimeError("Simulated LLM crash")):
        mock_engine.stt_provider.queue_transcription("Hey CHARVIS, do something")
        mock_engine.process_frame(b"audio_frame_sample")

    # Should have recovered to STANDBY
    assert mock_engine.state == WakeWordState.STANDBY
    assert mock_engine.last_error is not None
    assert "Simulated LLM crash" in mock_engine.last_error


def test_ctrl_c_stops_standby_loop(mock_engine) -> None:
    """Verify KeyboardInterrupt immediately stops the standby loop and transitions to STOPPED."""
    mock_engine.audio_capture.record_audio.side_effect = KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        mock_engine.run_standby_loop()

    assert mock_engine.state == WakeWordState.STOPPED
    assert mock_engine.detector.is_running() is False


def test_no_audio_files_persisted_to_disk(mock_engine, tmp_path) -> None:
    """CRITICAL PRIVACY: Verify that no audio files (.wav, .pcm, etc.) are written to disk."""
    import os
    before_files = set(os.listdir("."))

    mock_engine.start()
    mock_engine.detector.queue_detection(True)
    mock_engine.stt_provider.queue_transcription("Hey CHARVIS, calculate 2 + 2")
    mock_engine.process_frame(b"audio_frame_in_memory")
    mock_engine.stop()

    after_files = set(os.listdir("."))
    # No new files created in working directory
    assert before_files == after_files


def test_no_cloud_stt_called_during_wake_detection(mock_engine) -> None:
    """CRITICAL PRIVACY: Verify wake-word detection does not call cloud STT."""
    with patch("voice.stt.OpenAISTTProvider.transcribe") as mock_openai:
        mock_engine.start()
        # Normal frame with no wake word
        mock_engine.detector.queue_detection(False)
        mock_engine.process_frame(b"ambient_room_noise")

        assert mock_openai.call_count == 0
        mock_engine.stop()


def test_wake_word_does_not_bypass_safety_manager(tmp_path) -> None:
    """CRITICAL SECURITY: Dangerous action via wake word must trigger confirmation and fail if denied."""
    confirmation_mock = MagicMock(return_value=False)  # User DENIES confirmation

    # Mock provider returning shutdown_system tool call
    provider = MockLLMProvider([
        LLMResponse(
            content="",
            tool_calls=[ToolCall(id="call_1", name="shutdown_system", arguments={})],
        ),
        LLMResponse(content="Action aborted by user.", tool_calls=[]),
    ])

    brain = AIBrain(provider=provider)
    detector = MockWakeWordDetector(wake_phrase="hey charvis")
    stt = MockSTTProvider(default_response="Hey CHARVIS, shut down the computer")
    tts = MockTTSProvider()
    capture = MagicMock(spec=AudioCapture)
    capture.is_microphone_available.return_value = True
    capture.record_audio.return_value = b"audio"

    engine = WakeWordEngine(
        brain=brain,
        detector=detector,
        audio_capture=capture,
        stt_provider=stt,
        tts_provider=tts,
        confirmation_callback=confirmation_mock,
    )

    engine.start()
    detector.queue_detection(True)

    with patch("system.control.SystemController.shutdown_system") as mock_shutdown_func:
        engine.process_frame(b"frame")
        # System shutdown MUST NOT have been called
        assert mock_shutdown_func.call_count == 0

    # User was prompted for confirmation
    assert confirmation_mock.call_count == 1
    call_args = confirmation_mock.call_args[0]
    assert call_args[0] == "shutdown_system"
    assert call_args[2] == RiskLevel.HIGH_RISK
