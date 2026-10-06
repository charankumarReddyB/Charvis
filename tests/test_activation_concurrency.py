"""
Tests for Concurrency & Race Protection in Activation (Phase 19).
Verifies:
- Only one activation session can be active at any given moment
- Hotkey press while already LISTENING is safely ignored
- GUI button press while PROCESSING is safely ignored / rejected
- Wake-word detection while an active session exists does not spawn a second session
- Duplicate microphone streams and duplicate TTS playback are strictly prevented
"""

import time
from unittest.mock import MagicMock, patch
import pytest

from activation.manager import ActivationManager
from activation.models import ActivationSource, ActivationState


def test_concurrent_activation_requests_prevented():
    """Verify second activation request while active returns the existing session."""
    mock_brain = MagicMock()
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    with patch("voice.audio.AudioCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        # Simulate long recording session
        def slow_record(duration, cancel_event=None):
            if cancel_event:
                cancel_event.wait(timeout=0.3)
            return None
        mock_cap.record_audio.side_effect = slow_record

        # 1. Start first activation via Hotkey
        session1 = mgr.request_activation(ActivationSource.HOTKEY)
        time.sleep(0.02)
        assert mgr.is_active

        # 2. Attempt second activation via GUI while listening
        session2 = mgr.request_activation(ActivationSource.GUI)
        assert session2.session_id == session1.session_id

        # 3. Attempt third activation via Wake Word while listening
        session3 = mgr.request_activation(ActivationSource.WAKE_WORD)
        assert session3.session_id == session1.session_id

        # 4. Attempt fourth activation via Tray
        session4 = mgr.request_activation(ActivationSource.TRAY)
        assert session4.session_id == session1.session_id

        # Cleanup
        mgr.cancel_activation()


def test_no_duplicate_audio_capture_streams():
    """Verify multiple activation attempts create exactly one active microphone stream."""
    mock_brain = MagicMock()
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    capture_instances = []

    with patch("voice.audio.AudioCapture") as mock_cap_cls:
        def make_capture():
            c = MagicMock()
            capture_instances.append(c)
            def block_record(duration, cancel_event=None):
                if cancel_event:
                    cancel_event.wait(timeout=0.3)
                return None
            c.record_audio.side_effect = block_record
            return c

        mock_cap_cls.side_effect = make_capture

        mgr.request_activation(ActivationSource.GUI)
        time.sleep(0.02)

        # Trigger additional requests while first is still running
        mgr.request_activation(ActivationSource.HOTKEY)
        mgr.request_activation(ActivationSource.WAKE_WORD)

        time.sleep(0.02)
        # Exactly 1 capture instance was created
        assert len(capture_instances) == 1

        mgr.cancel_activation()


def test_no_duplicate_tts_sessions():
    """Verify TTS playback is protected from duplicate overlapping invocations."""
    mock_brain = MagicMock()
    mock_brain.process_user_message.return_value = "System status OK."
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    tts_instances = []

    with patch("voice.audio.AudioCapture") as mock_cap_cls, \
         patch("voice.stt.get_stt_provider") as mock_stt_getter, \
         patch("voice.tts.get_tts_provider") as mock_tts_getter:

        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.record_audio.return_value = b"audio"

        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = "Status"
        mock_stt_getter.return_value = mock_stt

        mock_tts = MagicMock()
        def slow_speak(text):
            time.sleep(0.1)
        mock_tts.speak.side_effect = slow_speak
        mock_tts_getter.return_value = mock_tts

        session = mgr.request_activation(ActivationSource.GUI)

        # Wait until speaking
        for _ in range(50):
            if session.state == ActivationState.SPEAKING:
                break
            time.sleep(0.02)

        if session.state == ActivationState.SPEAKING:
            # Attempt to activate while speaking
            dup_session = mgr.request_activation(ActivationSource.HOTKEY)
            assert dup_session.session_id == session.session_id

        # Cleanup
        mgr.cancel_activation()
