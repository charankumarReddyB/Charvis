"""
Unit tests for Runtime state machine and transitions (Phase 16).
"""

import pytest

from runtime.state import InvalidStateTransitionError, RuntimeState, RuntimeStateMachine


def test_state_machine_initial_state():
    """Verify state machine defaults to STOPPED."""
    sm = RuntimeStateMachine()
    assert sm.state == RuntimeState.STOPPED
    assert sm.is_stopped()
    assert not sm.is_running()


def test_valid_state_transitions():
    """Verify valid state progression: STOPPED -> STARTING -> RUNNING -> STOPPING -> STOPPED."""
    sm = RuntimeStateMachine()
    history = []

    def on_change(old, new):
        history.append((old, new))

    sm.add_listener(on_change)

    sm.transition_to(RuntimeState.STARTING, reason="Startup initiated")
    assert sm.state == RuntimeState.STARTING

    sm.transition_to(RuntimeState.RUNNING, reason="Core ready")
    assert sm.state == RuntimeState.RUNNING
    assert sm.is_running()

    sm.transition_to(RuntimeState.STOPPING, reason="User shutdown")
    assert sm.state == RuntimeState.STOPPING

    sm.transition_to(RuntimeState.STOPPED, reason="Cleanup complete")
    assert sm.state == RuntimeState.STOPPED
    assert sm.is_stopped()

    assert len(history) == 4
    assert history[0] == (RuntimeState.STOPPED, RuntimeState.STARTING)
    assert history[1] == (RuntimeState.STARTING, RuntimeState.RUNNING)
    assert history[2] == (RuntimeState.RUNNING, RuntimeState.STOPPING)
    assert history[3] == (RuntimeState.STOPPING, RuntimeState.STOPPED)


def test_invalid_transitions_raise_exception():
    """Verify invalid transitions raise InvalidStateTransitionError."""
    sm = RuntimeStateMachine()

    # STOPPED -> RUNNING is invalid (must go through STARTING)
    with pytest.raises(InvalidStateTransitionError, match="Invalid runtime state transition"):
        sm.transition_to(RuntimeState.RUNNING)

    # STOPPED -> STOPPING is invalid
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(RuntimeState.STOPPING)


def test_error_state_transition():
    """Verify transition to ERROR from running and recovery to STOPPING -> STOPPED."""
    sm = RuntimeStateMachine()
    sm.transition_to(RuntimeState.STARTING)
    sm.transition_to(RuntimeState.RUNNING)

    sm.set_error("Simulated fatal crash")
    assert sm.state == RuntimeState.ERROR
    assert sm.last_error == "Simulated fatal crash"

    # From ERROR can transition to STOPPING -> STOPPED
    sm.transition_to(RuntimeState.STOPPING)
    sm.transition_to(RuntimeState.STOPPED)
    assert sm.state == RuntimeState.STOPPED


def test_idempotent_stop():
    """Verify calling transition to STOPPED when already STOPPED does not raise error."""
    sm = RuntimeStateMachine()
    assert sm.state == RuntimeState.STOPPED
    # Calling transition_to STOPPED again should be a clean no-op
    sm.transition_to(RuntimeState.STOPPED)
    assert sm.state == RuntimeState.STOPPED
