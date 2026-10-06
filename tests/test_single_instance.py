"""
Unit tests for Single-Instance Desktop Architecture (Phase 18).
Ensures duplicate background runtimes are prevented, existing runtime is preserved,
and second launches connect to active runtime via RuntimeClient.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from runtime.client import RuntimeClient
from runtime.lifecycle import AnotherInstanceRunningError, RuntimeLock


def test_runtime_lock_prevents_duplicate_instance(tmp_path):
    """Verify acquiring lock when another process is running raises error."""
    lock1 = RuntimeLock(runtime_dir=tmp_path)
    lock1.acquire(port=9876, host="127.0.0.1", version="0.18.0")

    lock2 = RuntimeLock(runtime_dir=tmp_path)
    # Since lock1 created a valid lock file for the current PID, lock2 detects active instance
    assert lock2.is_another_instance_running() is True

    with pytest.raises(AnotherInstanceRunningError):
        lock2.acquire(port=9877, host="127.0.0.1", version="0.18.0")

    lock1.release()
    assert lock2.is_another_instance_running() is False


def test_second_launch_discovers_existing_runtime(tmp_path):
    """Verify RuntimeClient connects to existing active runtime port."""
    lock = RuntimeLock(runtime_dir=tmp_path)
    lock.acquire(port=14567, host="127.0.0.1", version="0.18.0", session_token="tok-18")

    client = RuntimeClient(runtime_dir=tmp_path)
    host, port = client._resolve_connection_details()
    assert host == "127.0.0.1"
    assert port == 14567
    assert client.session_token == "tok-18"

    lock.release()


def test_duplicate_background_launch_in_main(monkeypatch, capsys):
    """Verify main.py --background does not crash or kill existing runtime."""
    import sys
    import main

    monkeypatch.setattr(sys, "argv", ["main.py", "--background"])

    with patch.object(RuntimeClient, "is_runtime_running", return_value=True):
        ret = main.main()
        assert ret == 0
        captured = capsys.readouterr()
        assert "Duplicate startup avoided" in captured.out
