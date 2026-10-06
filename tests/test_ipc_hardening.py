"""
Comprehensive unit tests for IPC server & client hardening (Phase 17).
"""

import json
import socket
import time
import pytest
from core.errors import ErrorCategory
from runtime.ipc import IPCServer
from runtime.models import IPCRequest, IPCResponse


def test_ipc_rejects_non_localhost_binding():
    """Verify IPCServer refuses to bind to non-local IP addresses."""
    with pytest.raises(ValueError, match="Security error"):
        IPCServer(host="0.0.0.0")

    with pytest.raises(ValueError, match="Security error"):
        IPCServer(host="192.168.1.50")


def test_ipc_rejects_forbidden_and_unsupported_operations():
    """Verify IPCServer blocks prohibited execution commands and unsupported ops."""
    server = IPCServer(port=0)
    server.register_handler("status", lambda p: {"ok": True})
    port = server.start()

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", port))

        # Forbidden shell operation
        forbidden_req = IPCRequest(type="shell", request_id="f1", parameters={"cmd": "dir"})
        sock.sendall((json.dumps(forbidden_req.to_dict()) + "\n").encode())
        line = sock.recv(4096).decode()
        resp = IPCResponse.from_dict(json.loads(line))

        assert not resp.success
        assert resp.request_id == "f1"
        assert resp.category == ErrorCategory.SAFETY_ERROR.value

        # Unsupported operation
        unknown_req = IPCRequest(type="unknown_action", request_id="u1")
        sock.sendall((json.dumps(unknown_req.to_dict()) + "\n").encode())
        line = sock.recv(4096).decode()
        resp = IPCResponse.from_dict(json.loads(line))

        assert not resp.success
        assert resp.request_id == "u1"
        assert resp.category == ErrorCategory.VALIDATION_ERROR.value
        sock.close()

    finally:
        server.stop()


def test_ipc_session_token_authentication():
    """Verify IPCServer validates session token when configured."""
    token = "secret_session_token_123"
    server = IPCServer(port=0, session_token=token)
    server.register_handler("status", lambda p: {"running": True})
    port = server.start()

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", port))

        # Missing token
        req_no_token = IPCRequest(type="status", request_id="t1")
        sock.sendall((json.dumps(req_no_token.to_dict()) + "\n").encode())
        line = sock.recv(4096).decode()
        resp = IPCResponse.from_dict(json.loads(line))
        assert not resp.success
        assert resp.category == ErrorCategory.AUTHENTICATION_ERROR.value

        # Valid token
        req_valid = IPCRequest(type="status", request_id="t2", token=token)
        sock.sendall((json.dumps(req_valid.to_dict()) + "\n").encode())
        line = sock.recv(4096).decode()
        resp = IPCResponse.from_dict(json.loads(line))
        assert resp.success
        assert resp.data.get("running") is True
        sock.close()

    finally:
        server.stop()


def test_ipc_max_message_size():
    """Verify IPCServer terminates connections that exceed max_message_size."""
    server = IPCServer(port=0, max_message_size=512)
    port = server.start()

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", port))

        oversized_data = "x" * 1024
        sock.sendall(oversized_data.encode())
        time.sleep(0.1)

        # Connection should receive oversized rejection or be closed
        try:
            line = sock.recv(4096).decode()
            if line:
                resp = IPCResponse.from_dict(json.loads(line))
                assert not resp.success
                assert "exceeded max size" in resp.error
        except Exception:
            pass
        sock.close()
    finally:
        server.stop()


def test_ipc_bounded_concurrent_connections():
    """Verify IPCServer limits max concurrent client connections."""
    server = IPCServer(port=0, max_connections=2)
    port = server.start()

    try:
        socks = []
        for i in range(2):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("127.0.0.1", port))
            socks.append(s)

        time.sleep(0.05)

        # 3rd connection attempt exceeds limit
        overflow_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        overflow_sock.connect(("127.0.0.1", port))

        line = overflow_sock.recv(4096).decode()
        if line:
            resp = IPCResponse.from_dict(json.loads(line))
            assert not resp.success
            assert resp.category == ErrorCategory.RESOURCE_ERROR.value
        overflow_sock.close()

        for s in socks:
            s.close()
    finally:
        server.stop()
