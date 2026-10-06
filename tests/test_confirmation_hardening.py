"""
Comprehensive tests for confirmation race hardening, single-use enforcement,
state transitions, timeouts, and multi-task isolation (Phase 17).
"""

import time
import pytest
from core.safety import (
    ConfirmationRequest,
    ConfirmationState,
    ConfirmationStateError,
    RiskLevel,
    SafetyManager,
)


def test_confirmation_state_machine_valid_transitions():
    """Verify only allowed transitions from PENDING succeed."""
    # PENDING -> APPROVED
    req1 = ConfirmationRequest(
        tool_name="delete_file",
        arguments={"path": "test.txt"},
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
    )
    assert req1.state == ConfirmationState.PENDING
    req1.transition_to(ConfirmationState.APPROVED)
    assert req1.state == ConfirmationState.APPROVED

    # PENDING -> DENIED
    req2 = ConfirmationRequest(
        tool_name="delete_file",
        arguments={"path": "test.txt"},
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
    )
    req2.transition_to(ConfirmationState.DENIED)
    assert req2.state == ConfirmationState.DENIED

    # PENDING -> EXPIRED
    req3 = ConfirmationRequest(
        tool_name="delete_file",
        arguments={"path": "test.txt"},
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
    )
    req3.transition_to(ConfirmationState.EXPIRED)
    assert req3.state == ConfirmationState.EXPIRED

    # PENDING -> CANCELLED
    req4 = ConfirmationRequest(
        tool_name="delete_file",
        arguments={"path": "test.txt"},
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
    )
    req4.transition_to(ConfirmationState.CANCELLED)
    assert req4.state == ConfirmationState.CANCELLED


def test_confirmation_single_use_enforcement():
    """Verify once resolved, subsequent transitions are rejected (single-use invariant)."""
    req = ConfirmationRequest(
        tool_name="delete_file",
        arguments={"path": "test.txt"},
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
    )
    req.transition_to(ConfirmationState.APPROVED)

    # Double approve rejected
    with pytest.raises(ConfirmationStateError):
        req.transition_to(ConfirmationState.APPROVED)

    # Transitioning approved to denied rejected
    with pytest.raises(ConfirmationStateError):
        req.transition_to(ConfirmationState.DENIED)

    # Transitioning approved to cancelled rejected
    with pytest.raises(ConfirmationStateError):
        req.transition_to(ConfirmationState.CANCELLED)


def test_confirmation_timeout_expiration():
    """Verify expired confirmation transitions to EXPIRED and cannot be approved."""
    # Create request with 0.1s timeout
    req = ConfirmationRequest(
        tool_name="delete_file",
        arguments={"path": "test.txt"},
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
        timeout_seconds=0.1,
    )
    assert not req.is_expired()
    time.sleep(0.15)
    assert req.is_expired()

    # Attempting to approve an expired request must fail
    with pytest.raises(ConfirmationStateError):
        req.transition_to(ConfirmationState.APPROVED)
    assert req.state == ConfirmationState.EXPIRED


def test_safety_manager_resolve_confirmation():
    """Verify SafetyManager resolve_confirmation is atomic and single-use."""
    manager = SafetyManager()
    req = manager.create_confirmation_request(
        tool_name="delete_file",
        arguments={"path": "data.txt"},
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
        timeout_seconds=60.0,
    )

    cid = req.confirmation_id
    assert manager.get_confirmation(cid) is not None

    # First resolve: APPROVED
    assert manager.resolve_confirmation(cid, approved=True) is True

    # Second resolve (double-click): rejected
    assert manager.resolve_confirmation(cid, approved=True) is False
    assert manager.resolve_confirmation(cid, approved=False) is False


def test_safety_manager_multi_request_isolation():
    """Verify confirmation for action A does NOT authorize action B."""
    manager = SafetyManager()
    req1 = manager.create_confirmation_request(
        tool_name="delete_file",
        arguments={"path": "file1.txt"},
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
        task_id="task_1",
    )
    req2 = manager.create_confirmation_request(
        tool_name="delete_file",
        arguments={"path": "file2.txt"},
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
        task_id="task_2",
    )

    assert req1.confirmation_id != req2.confirmation_id

    # Resolve req1
    assert manager.resolve_confirmation(req1.confirmation_id, approved=True) is True

    # Req2 must still be pending
    assert req2.state == ConfirmationState.PENDING
    assert manager.get_confirmation(req2.confirmation_id) is not None

    # Deny req2
    assert manager.resolve_confirmation(req2.confirmation_id, approved=False) is False
    assert req2.state == ConfirmationState.DENIED


def test_safety_manager_cancel_all_pending():
    """Verify cancel_all_pending transitions all active requests to CANCELLED."""
    manager = SafetyManager()
    req1 = manager.create_confirmation_request(
        tool_name="delete_file",
        arguments={"path": "file1.txt"},
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
    )
    req2 = manager.create_confirmation_request(
        tool_name="delete_file",
        arguments={"path": "file2.txt"},
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
    )

    cancelled_count = manager.cancel_all_pending(reason="Test shutdown")
    assert cancelled_count == 2
    assert req1.state == ConfirmationState.CANCELLED
    assert req2.state == ConfirmationState.CANCELLED
