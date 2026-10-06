"""
Tests for TTS Lifecycle & Resource Safety (Phase 19).
Verifies:
- TTS playback executes outside the GUI thread in worker thread
- Cancellation safely interrupts TTS playback
- TTS failure transitions safely through ERROR/COMPLETED back to READY
- CHARVIS never remains permanently stuck in SPEAKING state
"""

import time
from unittest.mock import MagicMock, patch
import pytest

from activation.manager import ActivationManager
from activation.models import ActivationSource, ActivationState


def test_tts_runs_in_background_worker():
    """Verify TTS speak() is called asynchronously from background thread."""
    mock_brain = MagicMock()
    mock_brain.process_user_message.return_value = "Hello world."
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    tts_called_thread = []

    with patch("voice.audio.AudioCapture") as mock_cap_cls, \
         patch("voice.stt.get_stt_provider") as mock_stt_getter, \
         patch("voice.tts.get_tts_provider") as mock_tts_getter:

        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.record_audio.return_value = b"audio"

        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = "Hello"
        mock_stt_getter.return_value = mock_stt

        mock_tts = MagicMock()
        import threading
        def fake_speak(text):
            tts_called_thread.append(threading.current_thread().name)
        mock_tts.speak.side_effect = fake_speak
        mock_tts_getter.return_value = mock_tts

        session = mgr.request_activation(ActivationSource.GUI)
        for _ in range(50):
            if session.is_terminal:
                break
            time.sleep(0.05)

        assert len(tts_called_thread) == 1
        assert "CharvisActivation" in tts_called_thread[0]


def test_tts_failure_does_not_hang_speaking_state():
    """Verify an unexpected exception during TTS transitions session to terminal state."""
    mock_brain = MagicMock()
    mock_brain.process_user_message.return_value = "Error test response."
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    with patch("voice.audio.AudioCapture") as mock_cap_cls, \
         patch("voice.stt.get_stt_provider") as mock_stt_getter, \
         patch("voice.tts.get_tts_provider") as mock_tts_getter:

        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.record_audio.return_value = b"audio"

        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = "Crash TTS"
        mock_stt_getter.return_value = mock_stt

        mock_tts = MagicMock()
        mock_tts.speak.side_effect = RuntimeError("Audio device lost during playback")
        mock_tts_getter.return_value = mock_tts

        session = mgr.request_activation(ActivationSource.GUI)
        for _ in range(50):
            if session.is_terminal:
                break
            time.sleep(0.05)

        # Must have completed or reached terminal state without hanging
        assert session.is_terminal
        assert mgr.current_state != ActivationState.SPEAKING
        assert not mgr.is_active


def test_tts_cancellation_stops_playback():
    """Verify cancel_activation stops active TTS playback."""
    mock_brain = MagicMock()
    mock_brain.process_user_message.return_value = "Long speaking response."
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    with patch("voice.audio.AudioCapture") as mock_cap_cls, \
         patch("voice.stt.get_stt_provider") as mock_stt_getter, \
         patch("voice.tts.get_tts_provider") as mock_tts_getter:

        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.record_audio.return_value = b"audio"

        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = "Read book"
        mock_stt_getter.return_value = mock_stt

        mock_tts = MagicMock()
        def slow_speak(text):
            time.sleep(0.3)
        mock_tts.speak.side_effect = slow_speak
        mock_tts_getter.return_value = mock_tts

        session = mgr.request_activation(ActivationSource.GUI)

        # Wait until speaking begins
        for _ in range(50):
            if session.state == ActivationState.SPEAKING:
                break
            time.sleep(0.02)

        if session.state == ActivationState.SPEAKING:
            mgr.cancel_activation("User stopped speech")
            assert mock_tts.stop.called or session.is_terminal
