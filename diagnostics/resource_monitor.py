"""
Bounded background resource monitor for CHARVIS (Phase 17).
Periodically samples resource utilization at 5-15s intervals without high-frequency busy loops.
"""

from collections import deque
import threading
import time
from typing import Callable, Deque, Dict, List, Optional

from config import get_settings
from logger import get_logger
from diagnostics.metrics import SystemMetricsCollector
from diagnostics.models import ResourceMetrics

logger = get_logger("CHARVIS.Diagnostics.ResourceMonitor")


class ResourceMonitor:
    """
    Low-frequency, bounded periodic resource monitor.
    Guarantees clean shutdown and zero thread leaks.
    """

    def __init__(
        self,
        interval_seconds: float = 10.0,
        max_history: int = 120,
        collector: Optional[SystemMetricsCollector] = None,
        state_provider: Optional[Callable[[], Dict[str, Any]]] = None,
    ) -> None:
        self.interval = max(1.0, min(60.0, interval_seconds))
        self.max_history = max_history
        self.collector = collector or SystemMetricsCollector()
        self.state_provider = state_provider
        self.history: Deque[ResourceMetrics] = deque(maxlen=max_history)

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

        settings = get_settings()
        self.memory_warning_mb = settings.max_runtime_memory_warning_mb

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> None:
        """Start the background monitoring thread."""
        with self._lock:
            if self._is_running:
                return
            self._stop_event.clear()
            self._is_running = True
            self._thread = threading.Thread(
                target=self._monitor_loop,
                name="CHARVIS-ResourceMonitor",
                daemon=True,
            )
            self._thread.start()
            logger.info("ResourceMonitor started (interval=%.1fs, max_history=%d)", self.interval, self.max_history)

    def stop(self, timeout: float = 2.0) -> None:
        """Stop monitoring cleanly and wait for the thread to terminate."""
        with self._lock:
            if not self._is_running:
                return
            self._is_running = False
            self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("ResourceMonitor thread did not terminate within timeout.")
        self._thread = None
        logger.info("ResourceMonitor stopped cleanly.")

    def sample_now(self) -> ResourceMetrics:
        """Take an immediate sample and store it in history."""
        kwargs = {}
        if self.state_provider:
            try:
                state_data = self.state_provider()
                kwargs = {
                    "active_tasks": state_data.get("active_tasks", 0),
                    "active_workers": state_data.get("active_workers", 0),
                    "ipc_connections": state_data.get("ipc_connections", 0),
                    "browser_pages": state_data.get("browser_pages", 0),
                    "voice_active": state_data.get("voice_active", False),
                }
            except Exception as e:
                logger.debug("State provider error during sample: %s", e)

        metrics = self.collector.collect_metrics(**kwargs)
        with self._lock:
            self.history.append(metrics)

        # Check memory threshold
        if metrics.rss_memory_mb > self.memory_warning_mb:
            logger.warning(
                "High RSS memory warning: %.1f MB exceeds threshold of %d MB",
                metrics.rss_memory_mb,
                self.memory_warning_mb,
            )

        return metrics

    def get_latest_metrics(self) -> Optional[ResourceMetrics]:
        """Return the most recent metrics sample."""
        with self._lock:
            return self.history[-1] if self.history else None

    def get_history(self) -> List[ResourceMetrics]:
        """Return a copy of the sampled metrics history."""
        with self._lock:
            return list(self.history)

    def _monitor_loop(self) -> None:
        """Periodic background sampling loop."""
        # Initial sample on startup
        try:
            self.sample_now()
        except Exception as e:
            logger.debug("Error during initial sample: %s", e)

        while not self._stop_event.is_set():
            # Wait with event to allow immediate responsive termination
            if self._stop_event.wait(timeout=self.interval):
                break
            try:
                self.sample_now()
            except Exception as e:
                logger.debug("Error during resource sampling: %s", e)
