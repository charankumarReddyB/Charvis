"""
Local IPC client for CHARVIS (Phase 16).
Used by Desktop GUI and CLI to query and control the authoritative Background Runtime safely.
"""

import json
from pathlib import Path
import socket
import time
from typing import Any, Dict, Optional

from config import get_settings
from logger import get_logger
from runtime.lifecycle import RuntimeLock
from runtime.models import IPCRequest, IPCResponse, RuntimeStatus

logger = get_logger("CHARVIS.Runtime.Client")


class RuntimeClientError(RuntimeError):
    """Raised when communication with the background runtime fails."""
    pass


class RuntimeConnectionRefusedError(RuntimeClientError):
    """Raised when unable to connect to the background runtime."""
    pass


class RuntimeTimeoutError(RuntimeClientError):
    """Raised when an IPC request exceeds its bounded timeout."""
    pass


class RuntimeClient:
    """
    Client for interacting with the CHARVIS Background Runtime via local IPC.
    Never duplicates the AI brain or tasks; strictly forwards queries to the authoritative core.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        timeout: Optional[float] = None,
        runtime_dir: Optional[Path] = None,
        session_token: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.host = host or "127.0.0.1"
        self._configured_port = port
        self.timeout = timeout or settings.runtime_ipc_timeout
        self.runtime_lock = RuntimeLock(runtime_dir=runtime_dir or settings.runtime_dir)
        self.session_token = session_token

    def _resolve_connection_details(self) -> tuple[str, int]:
        """Discover host and port from runtime metadata file or fallback to configured port."""
        meta = self.runtime_lock.get_runtime_metadata()
        if meta and not self.session_token and meta.get("session_token"):
            self.session_token = meta["session_token"]

        if self._configured_port and self._configured_port > 0:
            return (self.host, self._configured_port)

        if meta and meta.get("port"):
            host = meta.get("host", self.host)
            port = int(meta["port"])
            return (host, port)

        raise RuntimeConnectionRefusedError(
            "No active CHARVIS background runtime found (missing or empty runtime metadata)."
        )

    def is_runtime_running(self) -> bool:
        """Check if background runtime is active, alive, and responding to ping."""
        try:
            if not self.runtime_lock.is_another_instance_running():
                return False
            resp = self.send_request("ping", {})
            return resp.get("status") == "pong"
        except Exception:
            return False

    def send_request(self, op_type: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send a synchronous IPC request to the background runtime and wait for response.
        Raises RuntimeClientError if the request fails or error returned.
        """
        host, port = self._resolve_connection_details()
        request = IPCRequest(type=op_type, parameters=parameters or {}, token=self.session_token)

        sock: Optional[socket.socket] = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((host, port))

            # Send request terminated by newline
            payload = json.dumps(request.to_dict()) + "\n"
            sock.sendall(payload.encode("utf-8"))

            # Receive response until newline
            buffer = bytearray()
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buffer.extend(chunk)
                if b"\n" in buffer:
                    break

            line = buffer.split(b"\n")[0].decode("utf-8", errors="replace")
            if not line.strip():
                raise RuntimeClientError("Received empty response from background runtime.")

            data = json.loads(line)
            response = IPCResponse.from_dict(data)

            # Correlate request ID
            if response.request_id != request.request_id and response.request_id != "rejected":
                logger.warning(
                    "IPC request ID mismatch: expected %s, got %s",
                    request.request_id,
                    response.request_id,
                )

            if not response.success:
                raise RuntimeClientError(response.error or "Unknown error from background runtime")

            return response.data

        except socket.timeout:
            logger.warning("IPC request '%s' timed out after %.1fs", op_type, self.timeout)
            raise RuntimeTimeoutError(f"IPC request '{op_type}' timed out after {self.timeout}s")
        except ConnectionRefusedError as ce:
            logger.debug("Failed connecting to background runtime on %s:%d: %s", host, port, ce)
            raise RuntimeConnectionRefusedError(f"Cannot connect to CHARVIS runtime at {host}:{port}: {ce}")
        except RuntimeClientError:
            raise
        except Exception as e:
            logger.error("IPC communication error with runtime: %s", e)
            raise RuntimeClientError(f"IPC request '{op_type}' failed: {e}")
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    # =========================================================================
    # High-level Typed Operations
    # =========================================================================

    def get_status(self) -> RuntimeStatus:
        """Retrieve authoritative status from background runtime."""
        data = self.send_request("status")
        return RuntimeStatus.from_dict(data)

    def get_health(self) -> Dict[str, Any]:
        """Retrieve subsystem health status."""
        return self.send_request("health")

    def send_chat(self, text: str) -> str:
        """Submit a user chat message to the background runtime's authoritative AI Brain."""
        result = self.send_request("chat", {"text": text})
        return str(result.get("response", ""))

    def create_task(self, goal: str) -> Dict[str, Any]:
        """Create a planner task via background runtime."""
        return self.send_request("task_create", {"goal": goal})

    def run_task(self, task_id: str) -> Dict[str, Any]:
        """Run a task via background runtime."""
        return self.send_request("task_run", {"task_id": task_id})

    def pause_task(self, task_id: str) -> Dict[str, Any]:
        """Pause a task via background runtime."""
        return self.send_request("task_pause", {"task_id": task_id})

    def resume_task(self, task_id: str) -> Dict[str, Any]:
        """Resume a task via background runtime."""
        return self.send_request("task_resume", {"task_id": task_id})

    def cancel_task(self, task_id: str, reason: str = "") -> Dict[str, Any]:
        """Cancel a task via background runtime."""
        return self.send_request("task_cancel", {"task_id": task_id, "reason": reason})

    def start_voice(self) -> Dict[str, Any]:
        """Explicitly request voice capture start."""
        return self.send_request("voice_start")

    def stop_voice(self) -> Dict[str, Any]:
        """Explicitly stop voice capture."""
        return self.send_request("voice_stop")

    def shutdown(self) -> Dict[str, Any]:
        """Request graceful shutdown of the background runtime."""
        return self.send_request("shutdown")
