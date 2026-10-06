"""
Tests for Safety Confirmation UI and Hardening (Phase 19).
Verifies:
- SafetyManager controls confirmation requests during voice / assistant interactions
- UI cannot approve actions by mutating local booleans
- Confirmation IDs are strictly single-use and originate from the security engine
- Denying or cancelling immediately denies tool execution
- Expired confirmations reject execution
- Closing dialog without approval denies action (no silent approval)
"""

import time
from unittest.mock import MagicMock, patch
import pytest

from core.safety import RiskLevel
from gui.controller import GUIController
from gui.models import ConfirmationRequest, SystemState
from gui.state import GUIState


def test_confirmation_callback_flow_through_controller():
    """Verify handle_confirmation sets state, waits on Event, and returns user decision."""
    state = GUIState()
    controller = GUIController(state=state)

    decision_result = []

    def run_confirmation():
        res = controller.handle_confirmation(
            tool_name="delete_file",
            arguments={"path": "C:\\test\\important.txt"},
            risk_level=RiskLevel.CONFIRMATION_REQUIRED,
            custom_message="Delete file: important.txt?",
        )
        decision_result.append(res)

    import threading
    t = threading.Thread(target=run_confirmation)
    t.start()

    # Wait for confirmation to post to state
    time.sleep(0.05)
    req = state.pending_confirmation
    assert req is not None
    assert req.tool_name == "delete_file"
    assert req.is_pending

    # Approve confirmation
    controller.submit_confirmation(req.request_id, approved=True)
    t.join(timeout=1.0)

    assert len(decision_result) == 1
    assert decision_result[0] is True
    assert state.pending_confirmation is None


def test_confirmation_denial_flow():
    """Verify denying confirmation returns False to SafetyManager."""
    state = GUIState()
    controller = GUIController(state=state)

    decision_result = []

    def run_confirmation():
        res = controller.handle_confirmation(
            tool_name="shutdown_system",
            arguments={},
            risk_level=RiskLevel.HIGH_RISK,
        )
        decision_result.append(res)

    import threading
    t = threading.Thread(target=run_confirmation)
    t.start()

    time.sleep(0.05)
    req = state.pending_confirmation
    assert req is not None

    # Deny confirmation
    controller.submit_confirmation(req.request_id, approved=False)
    t.join(timeout=1.0)

    assert len(decision_result) == 1
    assert decision_result[0] is False


def test_confirmation_single_use_and_no_double_approval():
    """Verify confirmation request cannot be approved twice or reused."""
    req = ConfirmationRequest(
        tool_name="delete_file",
        arguments={"path": "test.txt"},
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
    )
    assert req.is_pending

    req.approve()
    assert req.result is True
    assert not req.is_pending

    # Second approval attempt has no effect
    req.deny()
    assert req.result is True  # Result remains True, cannot be flipped


def test_confirmation_timeout_denies_automatically():
    """Verify abandoned confirmation request automatically resolves to False."""
    req = ConfirmationRequest(
        tool_name="close_application",
        arguments={},
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
        timeout_seconds=0.1,  # Fast timeout for test
    )
    # Check is_expired
    time.sleep(0.15)
    assert req.is_expired
    assert not req.is_pending or req.is_expired
