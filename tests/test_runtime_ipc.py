"""
Unit tests for Localhost IPC Server and Client communication & security (Phase 16).
"""

import json
import socket
import time
import pytest

from runtime.client import RuntimeClient, RuntimeClientError
from runtime.ipc import IPCServer
from runtime.models import IPCRequest, IPCResponse


@pytest.fixture
def ipc_test_server():
    server = IPCServer(host="127.0.0.1", port=0, max_message_size=4096)
    server.register_handler("status", lambda p: {"state": "RUNNING", "uptime": 42.0})
    server.register_handler("ping", lambda p: {"status": "pong"})
    server.register_handler("echo", lambda p: {"echo": p.get("msg")})
    port = server.start()
    yield server, port
    server.stop()


def test_ipc_valid_request_response(ipc_test_server):
    """Verify standard valid request and response correlation."""
    server, port = ipc_test_server
    client = RuntimeClient(host="127.0.0.1", port=port)

    res = client.send_request("status")
    assert res["state"] == "RUNNING"
    assert res["uptime"] == 42.0


def test_ipc_rejects_non_localhost_binding():
    """CRITICAL SECURITY: Verify binding to non-localhost address is strictly blocked."""
    with pytest.raises(ValueError, match="Security error"):
        IPCServer(host="0.0.0.0", port=0)

    with pytest.raises(ValueError, match="Security error"):
        IPCServer(host="192.168.1.100", port=0)


def test_ipc_strictly_rejects_forbidden_arbitrary_tool_operations(ipc_test_server):
    """CRITICAL SECURITY: Verify IPC rejects commands attempting arbitrary tool or shell execution."""
    server, port = ipc_test_server
    client = RuntimeClient(host="127.0.0.1", port=port)

    forbidden_commands = ["execute_tool", "run_tool", "call_tool", "eval", "exec", "shell", "cmd"]
    for cmd in forbidden_commands:
        with pytest.raises(RuntimeClientError, match="strictly prohibited|Unsupported"):
            client.send_request(cmd, {"command": "dir"})


def test_ipc_rejects_malformed_json(ipc_test_server):
    """Verify raw socket sending malformed JSON receives error response without crashing server."""
    server, port = ipc_test_server

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", port))
    sock.sendall(b"this is not valid json\n")

    response_data = sock.recv(1024)
    sock.close()

    resp_dict = json.loads(response_data.decode("utf-8"))
    assert resp_dict["success"] is False
    assert "Invalid request schema" in resp_dict["error"]


def test_ipc_oversized_message_rejection(ipc_test_server):
    """Verify message exceeding max_message_size is rejected."""
    server, port = ipc_test_server

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", port))

    # Send 5000 bytes (limit is 4096)
    oversized = b"a" * 5000 + b"\n"
    sock.sendall(oversized)

    response_data = sock.recv(1024)
    sock.close()

    resp_dict = json.loads(response_data.decode("utf-8"))
    assert resp_dict["success"] is False
    assert "exceeded max size" in resp_dict["error"]
