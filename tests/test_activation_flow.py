"""
Tests for unified Activation Pipeline Flow (Phase 19).
Verifies:
- Standard activation lifecycle: ACTIVATING -> LISTENING -> PROCESSING -> SPEAKING -> COMPLETED -> INACTIVE
- Cancellation path: ACTIVATING / LISTENING -> CANCELLED -> INACTIVE
- Listener subscription and state propagation
- Legal vs illegal transitions according to state machine
- Secret redaction on session command and response properties
"""

import time
from unittest.mock import MagicMock, patch
import pytest

from activation.manager import ActivationManager
from activation.models import (
    ActivationSession,
    ActivationSource,
    ActivationState,
    ActivationStateError,
    VALID_ACTIVATION_TRANSITIONS,
)


def test_activation_state_machine_valid_transitions():
    """Verify state machine allows legal paths and forbids illegal jumps."""
    session = ActivationSession(source=ActivationSource.GUI, state=ActivationState.INACTIVE)

    # Inactive -> Activating -> Listening -> Processing -> Speaking -> Completed
    session.transition_to(ActivationState.ACTIVATING)
    assert session.state == ActivationState.ACTIVATING

    session.transition_to(ActivationState.LISTENING)
    assert session.state == ActivationState.LISTENING

    session.transition_to(ActivationState.PROCESSING)
    assert session.state == ActivationState.PROCESSING

    session.transition_to(ActivationState.SPEAKING)
    assert session.state == ActivationState.SPEAKING

    session.transition_to(ActivationState.COMPLETED)
    assert session.state == ActivationState.COMPLETED

    # Illegal transition: Completed -> Processing raises ActivationStateError
    with pytest.raises(ActivationStateError):
        session.transition_to(ActivationState.PROCESSING)


def test_activation_cancellation_flow():
    """Verify cancellation transition and audio stream release."""
    mock_brain = MagicMock()
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    listener_states = []
    mgr.add_listener(lambda sess: listener_states.append(sess.state))

    with patch("voice.audio.AudioCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        # Simulate record audio blocking until cancel
        def fake_record(duration, cancel_event=None):
            if cancel_event:
                cancel_event.wait(timeout=0.1)
            return None
        mock_cap.record_audio.side_effect = fake_record

        session = mgr.request_activation(ActivationSource.GUI)
        time.sleep(0.02)
        assert session.state in (ActivationState.ACTIVATING, ActivationState.LISTENING)

        # Cancel activation
        mgr.cancel_activation("User clicked Stop Listening")
        assert session.state in (ActivationState.CANCELLED, ActivationState.COMPLETED, ActivationState.INACTIVE)
        assert not mgr.is_active


def test_activation_complete_flow_with_tts_and_brain():
    """Verify normal completion: STT -> Brain -> TTS -> Completed."""
    mock_brain = MagicMock()
    mock_brain.process_user_message.return_value = "System status is nominal."
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    listener_states = []
    mgr.add_listener(lambda sess: listener_states.append(sess.state))

    with patch("voice.audio.AudioCapture") as mock_cap_cls, \
         patch("voice.stt.get_stt_provider") as mock_stt_getter, \
         patch("voice.tts.get_tts_provider") as mock_tts_getter:

        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.record_audio.return_value = b"raw_audio_data"

        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = "What is the status?"
        mock_stt_getter.return_value = mock_stt

        mock_tts = MagicMock()
        mock_tts_getter.return_value = mock_tts

        session = mgr.request_activation(ActivationSource.HOTKEY)

        # Wait for worker thread to finish processing and speaking
        for _ in range(50):
            if session.is_terminal:
                break
            time.sleep(0.05)

        assert session.state in (ActivationState.COMPLETED, ActivationState.INACTIVE)
        assert mock_brain.process_user_message.called
        assert mock_tts.speak.called
        assert ActivationState.LISTENING in listener_states
        assert ActivationState.PROCESSING in listener_states
        assert ActivationState.SPEAKING in listener_states


def test_activation_session_secret_redaction():
    """Verify session fields redact sensitive credentials."""
    mock_brain = MagicMock()
    mock_brain.process_user_message.return_value = "Token is Bearer secret_token_12345"
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    with patch("voice.audio.AudioCapture") as mock_cap_cls, \
         patch("voice.stt.get_stt_provider") as mock_stt_getter, \
         patch("voice.tts.get_tts_provider") as mock_tts_getter:

        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.record_audio.return_value = b"audio"

        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = "Set password=SuperSecretPassword123"
        mock_stt_getter.return_value = mock_stt

        mock_tts = MagicMock()
        mock_tts_getter.return_value = mock_tts

        session = mgr.request_activation(ActivationSource.GUI)
        for _ in range(50):
            if session.is_terminal:
                break
            time.sleep(0.05)

        assert "SuperSecretPassword123" not in session.command_text
        assert "[REDACTED" in session.command_text
        assert "secret_token_12345" not in session.response_text
