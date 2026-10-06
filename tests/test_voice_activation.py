"""
Tests for Voice Interaction Flow (Phase 19).
Verifies:
- Voice activation from GUI button and Tray Voice Mode
- AudioCapture records and passes audio to STT
- STT transcription passes directly to authoritative AIBrain
- AIBrain response triggers Phase 8 TTS
- Non-blocking execution outside the GUI thread
- Graceful handling of empty speech / STT timeout
"""

import time
from unittest.mock import MagicMock, patch
import pytest

from activation.manager import ActivationManager
from activation.models import ActivationSource, ActivationState


def test_voice_activation_gui_source():
    """Verify GUI activation button triggers the unified voice pipeline."""
    mock_brain = MagicMock()
    mock_brain.process_user_message.return_value = "Chrome is opened."
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    with patch("voice.audio.AudioCapture") as mock_cap_cls, \
         patch("voice.stt.get_stt_provider") as mock_stt_getter, \
         patch("voice.tts.get_tts_provider") as mock_tts_getter:

        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.record_audio.return_value = b"audio_bytes"

        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = "Open Chrome"
        mock_stt_getter.return_value = mock_stt

        mock_tts = MagicMock()
        mock_tts_getter.return_value = mock_tts

        session = mgr.request_activation(ActivationSource.GUI)
        assert session.source == ActivationSource.GUI

        for _ in range(50):
            if session.is_terminal:
                break
            time.sleep(0.05)

        mock_stt.transcribe.assert_called_once_with(b"audio_bytes")
        mock_brain.process_user_message.assert_called_once_with("Open Chrome")
        mock_tts.speak.assert_called_once_with("Chrome is opened.")
        assert session.state == ActivationState.COMPLETED


def test_voice_activation_tray_source():
    """Verify Tray Voice Mode triggers activation with ActivationSource.TRAY."""
    mock_brain = MagicMock()
    mock_brain.process_user_message.return_value = "It is 3 PM."
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    with patch("voice.audio.AudioCapture") as mock_cap_cls, \
         patch("voice.stt.get_stt_provider") as mock_stt_getter, \
         patch("voice.tts.get_tts_provider") as mock_tts_getter:

        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.record_audio.return_value = b"audio_bytes"

        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = "What time is it?"
        mock_stt_getter.return_value = mock_stt

        mock_tts = MagicMock()
        mock_tts_getter.return_value = mock_tts

        session = mgr.request_activation(ActivationSource.TRAY)
        assert session.source == ActivationSource.TRAY

        for _ in range(50):
            if session.is_terminal:
                break
            time.sleep(0.05)

        mock_brain.process_user_message.assert_called_once_with("What time is it?")
        assert session.state == ActivationState.COMPLETED


def test_voice_activation_empty_speech_returns_to_ready():
    """When no speech is captured or STT returns empty string, session completes gracefully."""
    mock_brain = MagicMock()
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    with patch("voice.audio.AudioCapture") as mock_cap_cls, \
         patch("voice.stt.get_stt_provider") as mock_stt_getter:

        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.record_audio.return_value = None  # No audio recorded

        mock_stt = MagicMock()
        mock_stt_getter.return_value = mock_stt

        session = mgr.request_activation(ActivationSource.GUI)

        for _ in range(50):
            if session.is_terminal:
                break
            time.sleep(0.05)

        assert not mock_brain.process_user_message.called
        assert session.state in (ActivationState.COMPLETED, ActivationState.INACTIVE)
        assert not mgr.is_active
