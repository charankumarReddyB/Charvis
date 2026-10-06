"""
Unit tests for CHARVIS diagnostics module (Phase 17).
"""

import time
import pytest
from diagnostics.metrics import SystemMetricsCollector
from diagnostics.models import ResourceMetrics
from diagnostics.profiler import SimpleProfiler


def test_resource_metrics_serialization():
    """Verify ResourceMetrics serialization and deserialization."""
    metrics = ResourceMetrics(
        timestamp=1000.0,
        rss_memory_mb=128.5,
        cpu_percent=1.5,
        thread_count=8,
        active_tasks=2,
        active_workers=3,
        ipc_connections=1,
        browser_pages=1,
        voice_active=False,
        uptime_seconds=50.0,
    )

    data = metrics.to_dict()
    assert data["timestamp"] == 1000.0
    assert data["rss_memory_mb"] == 128.5
    assert data["cpu_percent"] == 1.5
    assert data["thread_count"] == 8
    assert data["active_tasks"] == 2

    restored = ResourceMetrics.from_dict(data)
    assert restored.timestamp == metrics.timestamp
    assert restored.rss_memory_mb == metrics.rss_memory_mb
    assert restored.cpu_percent == metrics.cpu_percent
    assert restored.thread_count == metrics.thread_count


def test_system_metrics_collector():
    """Verify SystemMetricsCollector safely queries current process."""
    collector = SystemMetricsCollector()
    metrics = collector.collect_metrics(
        active_tasks=1,
        active_workers=2,
        ipc_connections=1,
        browser_pages=0,
        voice_active=False,
    )

    assert metrics.rss_memory_mb > 0.0
    assert metrics.thread_count >= 1
    assert metrics.active_tasks == 1
    assert metrics.active_workers == 2
    assert metrics.uptime_seconds >= 0.0


def test_simple_profiler_measure_and_stats():
    """Verify SimpleProfiler context manager and stats."""
    profiler = SimpleProfiler(max_samples=10)

    for i in range(5):
        with profiler.measure("test_operation"):
            time.sleep(0.01)

    stats = profiler.get_stats("test_operation")
    assert stats["operation"] == "test_operation"
    assert stats["count"] == 5
    assert stats["avg_ms"] > 0.0
    assert stats["min_ms"] > 0.0
    assert stats["max_ms"] >= stats["min_ms"]
    assert stats["p95_ms"] >= stats["min_ms"]


def test_simple_profiler_decorator():
    """Verify SimpleProfiler decorator functionality."""
    profiler = SimpleProfiler()

    @profiler.profile("decorated_func")
    def sample_func():
        time.sleep(0.01)
        return 42

    result = sample_func()
    assert result == 42

    stats = profiler.get_stats("decorated_func")
    assert stats["count"] == 1
    assert stats["avg_ms"] > 0.0


def test_simple_profiler_empty_and_clear():
    """Verify behavior on empty profiler and clear operation."""
    profiler = SimpleProfiler()
    empty_stats = profiler.get_stats("non_existent")
    assert empty_stats["count"] == 0
    assert empty_stats["avg_ms"] == 0.0

    profiler.record_duration("op", 0.05)
    assert profiler.get_stats("op")["count"] == 1

    profiler.clear()
    assert profiler.get_stats("op")["count"] == 0
