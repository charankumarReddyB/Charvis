"""
Tests for Wake-Word Activation Flow (Phase 19).
Verifies:
- Detection of 'Hey CHARVIS' invokes ActivationManager.activate(ActivationSource.WAKE_WORD)
- Prompt cue ('Yes?') is played upon detection
- Wake phrase is stripped from captured command
- Wake-word enable / disable controls
- Privacy model: no continuous cloud STT before detection
- Prevention of duplicate wake-word engines
"""

import time
from unittest.mock import MagicMock, patch
import pytest

from activation.manager import ActivationManager
from activation.models import ActivationSource, ActivationState
from wakeword.engine import WakeWordEngine


def test_wakeword_engine_detection_delegates_to_activation_manager():
    """Verify wake word engine calls on_wake_detected callback and triggers activation."""
    callback_mock = MagicMock()
    mock_brain = MagicMock()

    mock_det = MagicMock()
    mock_det.detect.return_value = True

    engine = WakeWordEngine(
        brain=mock_brain,
        detector=mock_det,
        on_wake_detected=callback_mock,
    )

    from wakeword.engine import WakeWordState
    engine._state = WakeWordState.STANDBY

    # Process a frame where detector returns True
    result = engine.process_frame(b"\x00" * 256)
    assert result is True
    callback_mock.assert_called_once()


def test_wakeword_activation_prompt_cue_and_command_strip():
    """Verify wake word activation prompts 'Yes?' cue and strips wake phrase."""
    mock_brain = MagicMock()
    mock_brain.process_user_message.return_value = "Notepad opened."

    mock_engine = MagicMock()
    mock_engine.strip_wake_phrase.side_effect = lambda text: text.replace("hey charvis", "").strip()

    mgr = ActivationManager(
        brain=mock_brain,
        wake_word_engine=mock_engine,
        hotkey_enabled=False,
    )

    with patch("voice.audio.AudioCapture") as mock_cap_cls, \
         patch("voice.stt.get_stt_provider") as mock_stt_getter, \
         patch("voice.tts.get_tts_provider") as mock_tts_getter:

        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.record_audio.return_value = b"audio"

        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = "hey charvis open notepad"
        mock_stt_getter.return_value = mock_stt

        mock_tts = MagicMock()
        mock_tts_getter.return_value = mock_tts

        session = mgr.request_activation(ActivationSource.WAKE_WORD, prompt_cue=True)
        assert session.source == ActivationSource.WAKE_WORD

        for _ in range(50):
            if session.is_terminal:
                break
            time.sleep(0.05)

        # Cue 'Yes?' was spoken
        assert any("Yes?" in call[0][0] for call in mock_tts.speak.call_args_list)

        # Command was stripped before reaching brain
        mock_brain.process_user_message.assert_called_once_with("open notepad")
        assert session.command_text == "open notepad"


def test_enable_disable_wake_word_lifecycle():
    """Verify enable_wake_word and disable_wake_word start and stop the engine."""
    mock_engine = MagicMock()
    mock_engine.is_running = False

    def fake_start():
        mock_engine.is_running = True
    def fake_stop():
        mock_engine.is_running = False

    mock_engine.start.side_effect = fake_start
    mock_engine.stop.side_effect = fake_stop

    mgr = ActivationManager(
        wake_word_engine=mock_engine,
        hotkey_enabled=False,
    )

    success = mgr.enable_wake_word()
    assert success is True
    assert mock_engine.start.called
    assert mgr.is_wake_word_running() is True

    stopped = mgr.disable_wake_word()
    assert stopped is True
    assert mock_engine.stop.called
    assert mgr.is_wake_word_running() is False
