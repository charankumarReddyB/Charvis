"""
Unit tests for Runtime models and serialization (Phase 16).
"""

import pytest

from runtime.models import IPCRequest, IPCResponse, RuntimeStatus
from runtime.state import RuntimeState


def test_runtime_status_default_and_serialization():
    """Verify default RuntimeStatus and clean dictionary serialization."""
    status = RuntimeStatus()
    assert status.state == RuntimeState.STOPPED.value
    assert status.version == "0.17.0"
    assert status.process_id is None
    assert status.uptime == 0.0
    assert status.health_state == "HEALTHY"

    d = status.to_dict()
    assert isinstance(d, dict)
    assert d["state"] == "STOPPED"
    assert "version" in d

    # Deserialize back
    restored = RuntimeStatus.from_dict(d)
    assert restored.state == "STOPPED"
    assert restored.version == "0.17.0"


def test_runtime_status_custom_fields():
    """Verify custom fields and round-trip serialization."""
    status = RuntimeStatus(
        state=RuntimeState.RUNNING.value,
        version="0.16.0",
        process_id=12345,
        started_at="2026-09-22T10:00:00Z",
        uptime=120.5,
        active_tasks=2,
        voice_state="inactive",
        wake_word_state="disabled",
        browser_state="closed",
        memory_state="ready",
        health_state="HEALTHY",
        host="127.0.0.1",
        port=5555,
    )
    d = status.to_dict()
    assert d["process_id"] == 12345
    assert d["uptime"] == 120.5
    assert d["active_tasks"] == 2
    assert d["port"] == 5555

    restored = RuntimeStatus.from_dict(d)
    assert restored.process_id == 12345
    assert restored.uptime == 120.5


def test_runtime_status_ignores_secrets():
    """Verify RuntimeStatus.from_dict strips unknown/sensitive credentials."""
    untrusted_payload = {
        "state": "RUNNING",
        "version": "0.16.0",
        "openai_api_key": "sk-secret12345",
        "password": "supersecretpassword",
        "token": "bearer-token-abc",
    }
    status = RuntimeStatus.from_dict(untrusted_payload)
    status_dict = status.to_dict()
    assert "openai_api_key" not in status_dict
    assert "password" not in status_dict
    assert "token" not in status_dict


def test_ipc_request_and_response_models():
    """Verify IPCRequest and IPCResponse models and serialization."""
    req = IPCRequest(type="status", parameters={"verbose": True})
    req_dict = req.to_dict()
    assert req_dict["type"] == "status"
    assert req_dict["parameters"] == {"verbose": True}

    restored_req = IPCRequest.from_dict(req_dict)
    assert restored_req.type == "status"
    assert restored_req.parameters == {"verbose": True}
    assert restored_req.request_id == req.request_id

    # Response
    resp = IPCResponse(request_id=req.request_id, success=True, data={"uptime": 100})
    resp_dict = resp.to_dict()
    assert resp_dict["success"] is True
    assert resp_dict["data"]["uptime"] == 100

    restored_resp = IPCResponse.from_dict(resp_dict)
    assert restored_resp.success is True
    assert restored_resp.data["uptime"] == 100
    assert restored_resp.error is None


def test_ipc_request_validation_errors():
    """Verify malformed IPC payloads raise ValueError."""
    with pytest.raises(ValueError, match="JSON object"):
        IPCRequest.from_dict(["not", "a", "dict"])  # type: ignore

    with pytest.raises(ValueError, match="type"):
        IPCRequest.from_dict({"parameters": {}})

    with pytest.raises(ValueError, match="parameters"):
        IPCRequest.from_dict({"type": "status", "parameters": "not-a-dict"})
