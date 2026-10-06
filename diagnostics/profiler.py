"""
Lightweight diagnostic latency profiler for CHARVIS (Phase 17).
Provides low-overhead timing of critical operations with bounded sample history.
"""

from collections import deque
from contextlib import contextmanager
import functools
import threading
import time
from typing import Any, Callable, Dict, Generator, List, Optional


class SimpleProfiler:
    """
    Lightweight, thread-safe operation profiler.
    Stores up to `max_samples` execution latencies per operation name.
    """

    def __init__(self, max_samples: int = 100) -> None:
        self.max_samples = max_samples
        self._latencies: Dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def record_duration(self, operation: str, duration_seconds: float) -> None:
        """Record the execution duration of an operation."""
        with self._lock:
            if operation not in self._latencies:
                self._latencies[operation] = deque(maxlen=self.max_samples)
            self._latencies[operation].append(duration_seconds)

    @contextmanager
    def measure(self, operation: str) -> Generator[None, None, None]:
        """Context manager to measure and record block execution duration."""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self.record_duration(operation, elapsed)

    def profile(self, operation: Optional[str] = None) -> Callable[..., Any]:
        """Decorator to measure and record function execution duration."""
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            op_name = operation or func.__name__

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                with self.measure(op_name):
                    return func(*args, **kwargs)
            return wrapper
        return decorator

    def get_stats(self, operation: str) -> Dict[str, Any]:
        """Return summary statistics for a given operation."""
        with self._lock:
            samples = list(self._latencies.get(operation, []))

        if not samples:
            return {
                "operation": operation,
                "count": 0,
                "avg_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "p95_ms": 0.0,
            }

        sorted_samples = sorted(samples)
        count = len(sorted_samples)
        avg_s = sum(sorted_samples) / count
        min_s = sorted_samples[0]
        max_s = sorted_samples[-1]
        p95_idx = int(0.95 * (count - 1))
        p95_s = sorted_samples[p95_idx]

        return {
            "operation": operation,
            "count": count,
            "avg_ms": round(avg_s * 1000, 2),
            "min_ms": round(min_s * 1000, 2),
            "max_ms": round(max_s * 1000, 2),
            "p95_ms": round(p95_s * 1000, 2),
        }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Return summary statistics for all tracked operations."""
        with self._lock:
            ops = list(self._latencies.keys())
        return {op: self.get_stats(op) for op in ops}

    def clear(self) -> None:
        """Clear all recorded metrics."""
        with self._lock:
            self._latencies.clear()
