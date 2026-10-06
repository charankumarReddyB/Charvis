"""
Lightweight metrics collector for CHARVIS (Phase 17).
Gathers process-level CPU, memory, thread counts, and subsystem states safely.
"""

import os
import time
from typing import Optional
import psutil

from logger import get_logger
from diagnostics.models import ResourceMetrics

logger = get_logger("CHARVIS.Diagnostics.Metrics")


class SystemMetricsCollector:
    """
    Lightweight resource metrics collector using psutil.
    Designed for infrequent non-blocking sampling without introducing busy loops.
    """

    def __init__(self, start_time: Optional[float] = None) -> None:
        self.process = psutil.Process(os.getpid())
        self.start_time = start_time or time.time()
        # Initial call to cpu_percent to initialize internal counter
        try:
            self.process.cpu_percent(interval=None)
        except Exception:
            pass

    def collect_metrics(
        self,
        active_tasks: int = 0,
        active_workers: int = 0,
        ipc_connections: int = 0,
        browser_pages: int = 0,
        voice_active: bool = False,
    ) -> ResourceMetrics:
        """Collect current system and process resource metrics."""
        now = time.time()
        uptime = max(0.0, now - self.start_time)

        try:
            mem_info = self.process.memory_info()
            rss_mb = round(mem_info.rss / (1024 * 1024), 2)
        except Exception as e:
            logger.debug("Failed to read memory info: %s", e)
            rss_mb = 0.0

        try:
            cpu = round(self.process.cpu_percent(interval=None), 2)
        except Exception as e:
            logger.debug("Failed to read CPU percent: %s", e)
            cpu = 0.0

        try:
            threads = self.process.num_threads()
        except Exception as e:
            logger.debug("Failed to read thread count: %s", e)
            threads = 1

        return ResourceMetrics(
            timestamp=now,
            rss_memory_mb=rss_mb,
            cpu_percent=cpu,
            thread_count=threads,
            active_tasks=active_tasks,
            active_workers=active_workers,
            ipc_connections=ipc_connections,
            browser_pages=browser_pages,
            voice_active=voice_active,
            uptime_seconds=round(uptime, 2),
        )
