"""
Unit tests for CHARVIS ResourceMonitor (Phase 17).
"""

import time
import pytest
from diagnostics.models import ResourceMetrics
from diagnostics.resource_monitor import ResourceMonitor


def test_resource_monitor_lifecycle():
    """Verify ResourceMonitor starts, samples, and stops without thread leaks."""
    monitor = ResourceMonitor(interval_seconds=1.0, max_history=10)
    assert not monitor.is_running

    monitor.start()
    assert monitor.is_running

    # Give loop a brief moment to take initial sample
    time.sleep(0.1)
    latest = monitor.get_latest_metrics()
    assert latest is not None
    assert isinstance(latest, ResourceMetrics)
    assert len(monitor.get_history()) >= 1

    monitor.stop(timeout=1.0)
    assert not monitor.is_running


def test_resource_monitor_bounded_history():
    """Verify ResourceMonitor respects max_history limit."""
    monitor = ResourceMonitor(interval_seconds=1.0, max_history=3)

    for i in range(5):
        monitor.sample_now()

    history = monitor.get_history()
    assert len(history) == 3


def test_resource_monitor_state_provider():
    """Verify custom state_provider supplies active task/worker info to sample."""
    state_mock = {
        "active_tasks": 3,
        "active_workers": 2,
        "ipc_connections": 1,
        "browser_pages": 1,
        "voice_active": True,
    }

    monitor = ResourceMonitor(
        interval_seconds=1.0,
        max_history=5,
        state_provider=lambda: state_mock,
    )

    sample = monitor.sample_now()
    assert sample.active_tasks == 3
    assert sample.active_workers == 2
    assert sample.voice_active is True
