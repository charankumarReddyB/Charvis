"""
Diagnostics models and data structures for CHARVIS (Phase 17).
"""

from dataclasses import asdict, dataclass
import time
from typing import Any, Dict


@dataclass
class ResourceMetrics:
    """Snapshot of process and system resource utilization."""
    timestamp: float
    rss_memory_mb: float
    cpu_percent: float
    thread_count: int
    active_tasks: int = 0
    active_workers: int = 0
    ipc_connections: int = 0
    browser_pages: int = 0
    voice_active: bool = False
    uptime_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to a JSON-serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResourceMetrics":
        """Instantiate metrics from a dictionary."""
        return cls(
            timestamp=float(data.get("timestamp", time.time())),
            rss_memory_mb=float(data.get("rss_memory_mb", 0.0)),
            cpu_percent=float(data.get("cpu_percent", 0.0)),
            thread_count=int(data.get("thread_count", 0)),
            active_tasks=int(data.get("active_tasks", 0)),
            active_workers=int(data.get("active_workers", 0)),
            ipc_connections=int(data.get("ipc_connections", 0)),
            browser_pages=int(data.get("browser_pages", 0)),
            voice_active=bool(data.get("voice_active", False)),
            uptime_seconds=float(data.get("uptime_seconds", 0.0)),
        )
