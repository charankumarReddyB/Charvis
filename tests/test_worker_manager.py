"""
Unit tests for background worker management and lifecycle bounding (Phase 17).
"""

from concurrent.futures import ThreadPoolExecutor
import threading
import time
import pytest
from config import get_settings


def test_bounded_thread_pool_limit():
    """Verify ThreadPoolExecutor enforces maximum concurrent workers."""
    settings = get_settings()
    max_workers = settings.max_background_workers
    executor = ThreadPoolExecutor(max_workers=max_workers)

    active_count = 0
    max_observed = 0
    lock = threading.Lock()
    barrier = threading.Barrier(max_workers)

    def worker_task():
        nonlocal active_count, max_observed
        with lock:
            active_count += 1
            if active_count > max_observed:
                max_observed = active_count
        try:
            barrier.wait(timeout=2.0)
            time.sleep(0.05)
        finally:
            with lock:
                active_count -= 1

    # Submit 2x max workers
    futures = [executor.submit(worker_task) for _ in range(max_workers * 2)]
    for f in futures:
        f.result(timeout=5.0)

    executor.shutdown(wait=True)
    assert max_observed <= max_workers


def test_worker_exception_isolation():
    """Verify worker exceptions are safely isolated and do not crash pool."""
    executor = ThreadPoolExecutor(max_workers=2)

    def failing_task():
        raise ValueError("Simulated worker failure")

    def succeeding_task():
        return "success"

    f1 = executor.submit(failing_task)
    f2 = executor.submit(succeeding_task)

    with pytest.raises(ValueError):
        f1.result(timeout=2.0)

    assert f2.result(timeout=2.0) == "success"
    executor.shutdown(wait=True)
