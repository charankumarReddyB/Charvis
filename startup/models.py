"""
Data models for Windows Startup integration (Phase 16).
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class StartupStatus:
    """
    Status descriptor for CHARVIS Windows startup integration.
    Never exposes credentials or secrets.
    """
    enabled: bool = False
    method: str = "startup_folder"
    command: Optional[str] = None
    created_at: Optional[str] = None
    path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StartupStatus":
        clean = dict(data)
        allowed = {"enabled", "method", "command", "created_at", "path"}
        filtered = {k: v for k, v in clean.items() if k in allowed}
        return cls(**filtered)
