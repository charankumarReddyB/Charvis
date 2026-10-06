"""
Data models for CHARVIS Background Runtime (Phase 16).
Defines RuntimeStatus, IPCRequest, and IPCResponse with strict secret sanitization.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional
import uuid

from runtime.state import RuntimeState

# Maximum allowable length for arbitrary string fields to prevent memory abuse
MAX_PARAM_STRING_LEN = 10_000


@dataclass
class RuntimeStatus:
    """
    Structured status descriptor for the CHARVIS background runtime.
    Strictly sanitized: never includes credentials, API keys, or memory contents.
    """
    state: str = RuntimeState.STOPPED.value
    version: str = "0.17.0"
    process_id: Optional[int] = None
    started_at: Optional[str] = None
    uptime: float = 0.0
    active_tasks: int = 0
    voice_state: str = "inactive"
    wake_word_state: str = "disabled"
    browser_state: str = "closed"
    memory_state: str = "ready"
    health_state: str = "HEALTHY"
    last_error: Optional[str] = None
    host: str = "127.0.0.1"
    port: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize status to a clean dictionary."""
        data = asdict(self)
        # Ensure state is string representation
        if isinstance(data.get("state"), RuntimeState):
            data["state"] = data["state"].value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuntimeStatus":
        """Deserialize status safely from dictionary."""
        clean_data = dict(data)
        # Drop any unexpected or sensitive keys
        allowed_keys = {
            "state", "version", "process_id", "started_at", "uptime",
            "active_tasks", "voice_state", "wake_word_state", "browser_state",
            "memory_state", "health_state", "last_error", "host", "port",
        }
        filtered = {k: v for k, v in clean_data.items() if k in allowed_keys}
        return cls(**filtered)


@dataclass
class IPCRequest:
    """
    Structured request message received over local IPC.
    Treated as untrusted input: strictly validated before execution.
    """
    type: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parameters: Dict[str, Any] = field(default_factory=dict)
    token: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "request_id": self.request_id,
            "type": self.type,
            "parameters": self.parameters,
        }
        if self.token:
            res["token"] = self.token
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IPCRequest":
        if not isinstance(data, dict):
            raise ValueError("Malformed IPC request: payload must be a JSON object")
        
        req_type = data.get("type")
        if not req_type or not isinstance(req_type, str):
            raise ValueError("Malformed IPC request: missing or invalid 'type'")
        
        req_id = data.get("request_id")
        if not req_id or not isinstance(req_id, str):
            req_id = str(uuid.uuid4())
        
        params = data.get("parameters", {})
        if not isinstance(params, dict):
            raise ValueError("Malformed IPC request: 'parameters' must be an object")

        tok = data.get("token")
        token_str = str(tok) if tok else None

        return cls(request_id=req_id, type=req_type.strip().lower(), parameters=params, token=token_str)


@dataclass
class IPCResponse:
    """
    Structured response message returned over local IPC.
    """
    request_id: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    category: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "request_id": self.request_id,
            "success": self.success,
            "data": self.data,
            "error": self.error,
        }
        if self.category:
            res["category"] = self.category
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IPCResponse":
        if not isinstance(data, dict):
            raise ValueError("Malformed IPC response: payload must be a JSON object")
        return cls(
            request_id=str(data.get("request_id", "")),
            success=bool(data.get("success", False)),
            data=dict(data.get("data", {})),
            error=data.get("error"),
            category=data.get("category"),
        )

