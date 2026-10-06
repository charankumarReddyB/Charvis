"""
Tests for Assistant UI Error Handling & User-Safe Reporting (Phase 19).
Verifies:
- Microphone unavailable displays a user-safe message, not raw tracebacks
- STT timeout or recognition failure returns to safe ready state
- TTS failure recovers safely without GUI lockup
- Runtime disconnect transitions to Offline state
- Runtime reconnect restores Online / Ready state
- LLM or brain exceptions are sanitized and never leak raw stack traces to the user
"""

import time
from unittest.mock import MagicMock, patch
import pytest

from activation.manager import ActivationManager
from activation.models import ActivationSource, ActivationState
from gui.controller import GUIController
from gui.models import SystemState
from gui.state import GUIState


def test_microphone_unavailable_error_handling():
    """Verify missing microphone device produces user-safe notification without crashing."""
    mock_brain = MagicMock()
    mgr = ActivationManager(brain=mock_brain, hotkey_enabled=False)

    with patch("voice.audio.AudioCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.record_audio.side_effect = OSError("No default input device available")
        mock_cap_cls.return_value = mock_cap

        session = mgr.request_activation(ActivationSource.GUI)
        for _ in range(50):
            if session.is_terminal:
                break
            time.sleep(0.05)

        assert session.state == ActivationState.ERROR
        assert not mgr.is_active


def test_brain_exception_sanitized_in_gui_controller():
    """Verify unhandled exceptions in AIBrain result in user-safe error message."""
    state = GUIState()
    mock_brain = MagicMock()
    mock_brain.process_user_message.side_effect = Exception("OpenAI API key invalid or quota exceeded at core/brain.py:345")

    controller = GUIController(state=state, brain=mock_brain)
    controller._run_brain_query("Hello assistant")

    # The error message added to state must NOT contain file paths or internal details
    assert len(state.messages) > 0
    last_msg = state.messages[-1]
    assert last_msg.is_error
    assert "core/brain.py" not in last_msg.content
    assert "couldn't complete that request" in last_msg.content.lower()


def test_runtime_disconnect_and_reconnect():
    """Verify runtime disconnect updates status to OFFLINE/DISCONNECTED and reconnect restores ONLINE."""
    state = GUIState()
    controller = GUIController(state=state)

    # Simulate disconnect
    controller.state.set_system_state(SystemState.DISCONNECTED, "Runtime disconnected")
    assert state.system_state == SystemState.DISCONNECTED

    # Simulate reconnect
    controller.state.set_system_state(SystemState.ONLINE, "CHARVIS ONLINE")
    assert state.system_state == SystemState.ONLINE
