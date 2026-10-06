"""
Unit tests for RuntimeLock, single-instance enforcement, and safe stale lock recovery (Phase 16).
"""

import json
import os
from unittest.mock import patch
import pytest

from runtime.lifecycle import RuntimeAlreadyRunningError, RuntimeLock


def test_runtime_lock_acquire_and_release(tmp_path):
    """Verify acquiring and releasing the single instance lock."""
    lock = RuntimeLock(runtime_dir=tmp_path)
    assert not lock.is_acquired

    lock.acquire(port=5000)
    assert lock.is_acquired
    assert (tmp_path / "runtime.lock").exists()
    assert (tmp_path / "runtime.json").exists()

    meta = lock.get_runtime_metadata()
    assert meta["port"] == 5000
    assert meta["pid"] == os.getpid()

    lock.release()
    assert not lock.is_acquired
    assert not (tmp_path / "runtime.lock").exists()
    assert not (tmp_path / "runtime.json").exists()


def test_runtime_lock_duplicate_prevention(tmp_path):
    """Verify attempting to acquire an already-held active lock raises RuntimeAlreadyRunningError."""
    lock1 = RuntimeLock(runtime_dir=tmp_path)
    lock1.acquire(port=5000)

    lock2 = RuntimeLock(runtime_dir=tmp_path)
    with pytest.raises(RuntimeAlreadyRunningError):
        lock2.acquire(port=5001)

    lock1.release()


def test_runtime_lock_recovers_stale_metadata_safely(tmp_path):
    """Verify dead process PID in lock file is safely recovered without killing processes."""
    lock_file = tmp_path / "runtime.lock"
    meta_file = tmp_path / "runtime.json"

    # Write a fake dead PID (e.g. 999999)
    stale_pid = 999999
    lock_file.write_text(str(stale_pid), encoding="utf-8")
    meta_file.write_text(
        json.dumps({
            "pid": stale_pid,
            "process_create_time": 0.0,
            "port": 9999,
        }),
        encoding="utf-8",
    )

    lock = RuntimeLock(runtime_dir=tmp_path)
    # The recorded process 999999 is dead, so is_another_instance_running() should return False
    assert not lock.is_another_instance_running()

    # Acquiring should safely clean up the dead files and acquire
    lock.acquire(port=5002)
    assert lock.is_acquired
    assert lock.get_runtime_metadata()["pid"] == os.getpid()

    lock.release()
