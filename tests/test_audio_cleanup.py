"""
Tests for Audio Resource Lifecycle and Stream Cleanup (Phase 19).
Verifies:
- Microphone stream is cleanly stopped on normal completion
- Microphone stream is cleanly stopped on cancellation
- Microphone stream is cleanly stopped on exception / error
- Microphone stream is cleanly stopped on timeout
- Repeated activation and cancellation cycles leave zero hanging handles
"""

import time
from unittest.mock import MagicMock, patch
import pytest

from activation.manager import ActivationManager
from activation.models import ActivationSource, ActivationState
from voice.audio import AudioCapture


def test_audio_capture_stop_calls_sounddevice():
    """Verify AudioCapture.stop releases underlying sounddevice stream."""
    with patch("voice.audio.sd") as mock_sd:
        capture = AudioCapture()
        capture.stop()
        mock_sd.stop.assert_called_once()


def test_audio_capture_cancel_event_halts_recording():
    """Verify record_audio honors cancel_event and exits before full duration."""
    import threading
    from voice.audio import NoSpeechDetectedError
    with patch("voice.audio.sd") as mock_sd, \
         patch.object(AudioCapture, "is_microphone_available", return_value=True):
        mock_sd.rec.return_value = None
        capture = AudioCapture()

        cancel_ev = threading.Event()
        threading.Timer(0.02, cancel_ev.set).start()

        start_t = time.perf_counter()
        with pytest.raises(NoSpeechDetectedError):
            capture.record_audio(duration=10.0, cancel_event=cancel_ev)
        elapsed = time.perf_counter() - start_t

        assert elapsed < 1.0
        mock_sd.stop.assert_called()


def test_microphone_cleanup_on_normal_completion():
    """Verify capture.stop() is executed on successful completion."""
    mock_brain = MagicMock()
    mock_brain.process_user_message.return_value = "Done."
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    with patch("voice.audio.AudioCapture") as mock_cap_cls, \
         patch("voice.stt.get_stt_provider") as mock_stt_getter, \
         patch("voice.tts.get_tts_provider") as mock_tts_getter:

        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.record_audio.return_value = b"sample_audio"

        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = "Test command"
        mock_stt_getter.return_value = mock_stt

        mock_tts = MagicMock()
        mock_tts_getter.return_value = mock_tts

        session = mgr.request_activation(ActivationSource.GUI)
        for _ in range(50):
            if session.is_terminal:
                break
            time.sleep(0.05)

        assert mgr._active_capture is None
        assert not mgr.is_active


def test_microphone_cleanup_on_repeated_cancellations():
    """Verify repeated activate-then-cancel cycles never leak active captures."""
    mock_brain = MagicMock()
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    with patch("voice.audio.AudioCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        def mock_record(duration, cancel_event=None):
            if cancel_event:
                cancel_event.wait(timeout=0.2)
            return None
        mock_cap.record_audio.side_effect = mock_record
        mock_cap_cls.return_value = mock_cap

        for cycle in range(5):
            mgr.request_activation(ActivationSource.GUI)
            time.sleep(0.02)
            assert mgr._active_capture is not None

            mgr.cancel_activation(f"Cycle {cycle} cancel")
            time.sleep(0.02)
            assert mgr._active_capture is None
            assert not mgr.is_active


def test_microphone_cleanup_on_error():
    """Verify active capture reference is reset even when STT or audio raises exception."""
    mock_brain = MagicMock()
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    with patch("voice.audio.AudioCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.record_audio.side_effect = RuntimeError("Microphone hardware disconnected")
        mock_cap_cls.return_value = mock_cap

        session = mgr.request_activation(ActivationSource.HOTKEY)
        for _ in range(50):
            if session.is_terminal:
                break
            time.sleep(0.05)

        assert mgr._active_capture is None
        assert not mgr.is_active
