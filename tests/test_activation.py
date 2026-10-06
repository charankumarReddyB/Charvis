"""
Unit tests for Activation Subsystem (Phase 18).
Tests state transitions, session tracking, cancellation, and listener callbacks.
"""

from unittest.mock import MagicMock, patch
import pytest

from activation.manager import ActivationManager
from activation.models import (
    ActivationSession,
    ActivationSource,
    ActivationState,
    InvalidActivationTransitionError,
)


def test_activation_session_transitions():
    """Verify legal state transitions in ActivationSession."""
    sess = ActivationSession(
        session_id="act-1",
        source=ActivationSource.TRAY_MENU,
        state=ActivationState.INACTIVE,
    )
    assert sess.is_terminal is False

    sess.transition_to(ActivationState.ACTIVATING)
    sess.transition_to(ActivationState.LISTENING)
    sess.transition_to(ActivationState.PROCESSING)
    sess.transition_to(ActivationState.COMPLETED)
    assert sess.is_terminal is True


def test_activation_session_invalid_transition():
    """Verify invalid transition raises InvalidActivationTransitionError."""
    sess = ActivationSession(
        session_id="act-2",
        source=ActivationSource.KEYBOARD_SHORTCUT,
        state=ActivationState.COMPLETED,
    )
    with pytest.raises(InvalidActivationTransitionError):
        sess.transition_to(ActivationState.LISTENING)


def test_activation_manager_request_and_cancel():
    """Verify requesting and cancelling activation sessions."""
    manager = ActivationManager()
    events = []
    manager.add_listener(lambda s: events.append((s.session_id, s.state)))

    with patch.object(manager, "_run_voice_interaction"):
        session = manager.request_activation(source=ActivationSource.TRAY_MENU)
        assert session.source == ActivationSource.TRAY_MENU
        assert session.state == ActivationState.ACTIVATING

        # Cancel session
        cancelled = manager.cancel_activation(reason="User cancelled")
        assert cancelled.state == ActivationState.CANCELLED
        assert manager.current_session is None

    # Check that events were published
    states_published = [e[1] for e in events]
    assert ActivationState.ACTIVATING in states_published
    assert ActivationState.CANCELLED in states_published


def test_activation_manager_listeners():
    """Verify adding, notifying, and removing listeners."""
    manager = ActivationManager()
    calls = []

    def cb(sess):
        calls.append(sess.state)

    manager.add_listener(cb)
    manager.request_activation()
    assert len(calls) > 0

    manager.remove_listener(cb)
    initial_len = len(calls)
    manager.cancel_activation()
    assert len(calls) == initial_len


def test_activation_wake_word_control():
    """Verify enable and disable wake word delegation without creating new engines."""
    manager = ActivationManager()
    assert manager.is_wake_word_running() is False

    with patch("tools.wakeword.get_active_engine") as mock_get_engine, \
         patch("tools.wakeword.set_active_engine") as mock_set_engine:
        mock_engine = MagicMock()
        mock_engine.is_running = True
        mock_get_engine.return_value = mock_engine

        assert manager.is_wake_word_running() is True

        manager.disable_wake_word()
        mock_engine.stop.assert_called()
        mock_set_engine.assert_called_with(None)


def test_activation_never_executes_tools_directly():
    """Verify ActivationManager does not expose or directly call tool execution methods."""
    manager = ActivationManager()
    assert not hasattr(manager, "execute_tool")
    assert not hasattr(manager, "run_tool")
    assert not hasattr(manager, "execute")
