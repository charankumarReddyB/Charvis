"""
Localhost IPC server for CHARVIS Background Runtime (Phase 16 & Phase 17 Hardening).
Provides secure, isolated localhost-only communication between GUI/CLI and Background Runtime.
Enforces size limits, session tokens, request correlation, timeouts, and bounded connection pools.
"""

import json
import socket
import threading
from typing import Any, Callable, Dict, List, Optional

from config import get_settings
from core.errors import ErrorCategory
from logger import get_logger
from runtime.models import IPCRequest, IPCResponse

logger = get_logger("CHARVIS.Runtime.IPC")

# Operations explicitly permitted through IPC
ALLOWED_OPERATIONS = {
    "status",
    "health",
    "chat",
    "task_create",
    "task_run",
    "task_pause",
    "task_resume",
    "task_cancel",
    "voice_start",
    "voice_stop",
    "shutdown",
    "ping",
}

# Operations explicitly banned
FORBIDDEN_OPERATIONS = {
    "execute_tool",
    "run_tool",
    "call_tool",
    "eval",
    "exec",
    "shell",
    "cmd",
    "powershell",
    "subprocess",
    "system",
    "sql",
    "query_sql",
}


class IPCServer:
    """
    Hardened Localhost TCP IPC Server (Phase 17).
    Bound strictly to 127.0.0.1. Rejects external binding, enforces message size limits,
    bounded concurrent connections, request timeouts, and runtime session authentication.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        max_message_size: Optional[int] = None,
        session_token: Optional[str] = None,
        max_connections: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        clean_host = (host or "127.0.0.1").strip().lower()
        if clean_host not in {"127.0.0.1", "localhost"}:
            raise ValueError(f"Security error: IPCServer bound to non-local address '{host}'. Only 127.0.0.1 is permitted.")

        self.host = "127.0.0.1"
        self.requested_port = port
        self.max_message_size = max_message_size or settings.runtime_max_message_size
        self.session_token = session_token
        self.max_connections = max_connections or settings.max_ipc_connections

        self._handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self._server_socket: Optional[socket.socket] = None
        self._server_thread: Optional[threading.Thread] = None
        self._is_running = False
        self._active_connections: List[socket.socket] = []
        self._conn_lock = threading.Lock()
        self.actual_port: int = 0

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def port(self) -> int:
        return self.actual_port

    def register_handler(self, op_type: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """Register a handler callback for a supported high-level IPC operation."""
        clean_type = op_type.strip().lower()
        if clean_type in FORBIDDEN_OPERATIONS:
            raise ValueError(f"Security error: Operation '{clean_type}' is strictly forbidden over IPC.")
        self._handlers[clean_type] = handler

    def start(self) -> int:
        """
        Start the IPC server on 127.0.0.1.
        Returns the bound local port.
        """
        if self._is_running:
            return self.actual_port

        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.requested_port))
        self._server_socket.listen(10)
        self.actual_port = self._server_socket.getsockname()[1]
        self._is_running = True

        logger.info(
            "IPCServer listening on %s:%d (Max Msg: %d bytes, Max Conn: %d)",
            self.host,
            self.actual_port,
            self.max_message_size,
            self.max_connections,
        )

        self._server_thread = threading.Thread(
            target=self._listen_loop,
            name="CHARVIS-IPCServer",
            daemon=True,
        )
        self._server_thread.start()
        return self.actual_port

    def _listen_loop(self) -> None:
        """Main socket accept loop."""
        while self._is_running and self._server_socket:
            try:
                client_sock, client_addr = self._server_socket.accept()
                # Security check: ensure client is from 127.0.0.1
                client_ip = client_addr[0]
                if client_ip not in {"127.0.0.1", "::1", "localhost"}:
                    logger.warning("Rejected non-localhost connection attempt from %s", client_ip)
                    try:
                        client_sock.close()
                    except Exception:
                        pass
                    continue

                # Bounded connection pool check
                with self._conn_lock:
                    if len(self._active_connections) >= self.max_connections:
                        logger.warning(
                            "Max concurrent IPC connections (%d) reached. Rejecting client from %s:%d",
                            self.max_connections,
                            client_ip,
                            client_addr[1],
                        )
                        err_resp = IPCResponse(
                            request_id="rejected",
                            success=False,
                            error=f"Server busy: max concurrent connections ({self.max_connections}) reached",
                            category=ErrorCategory.RESOURCE_ERROR.value,
                        )
                        self._send_response(client_sock, err_resp)
                        try:
                            client_sock.close()
                        except Exception:
                            pass
                        continue

                    self._active_connections.append(client_sock)

                conn_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock,),
                    name=f"CHARVIS-IPCClient-{client_addr[1]}",
                    daemon=True,
                )
                conn_thread.start()

            except (OSError, socket.error):
                # Socket closed during shutdown
                break
            except Exception as e:
                if self._is_running:
                    logger.error("Unexpected error in IPCServer accept loop: %s", e)

    def _handle_client(self, client_sock: socket.socket) -> None:
        """Process messages for a single client socket with bounded idle timeout."""
        buffer = bytearray()
        try:
            # Set idle socket timeout
            settings = get_settings()
            client_sock.settimeout(settings.runtime_ipc_timeout * 3)

            while self._is_running:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break  # Connection closed by client

                buffer.extend(chunk)
                if len(buffer) > self.max_message_size:
                    logger.warning(
                        "IPC message exceeded size limit (%d bytes). Closing connection.",
                        self.max_message_size,
                    )
                    err_resp = IPCResponse(
                        request_id="oversized",
                        success=False,
                        error=f"Message exceeded max size limit of {self.max_message_size} bytes",
                        category=ErrorCategory.VALIDATION_ERROR.value,
                    )
                    self._send_response(client_sock, err_resp)
                    break

                # Newline delimited framing
                while b"\n" in buffer:
                    line, _, remaining = buffer.partition(b"\n")
                    buffer = bytearray(remaining)
                    if not line.strip():
                        continue

                    response = self._process_raw_message(line.decode("utf-8", errors="replace"))
                    self._send_response(client_sock, response)

        except (socket.timeout, ConnectionResetError):
            pass
        except Exception as e:
            logger.debug("IPC client connection error: %s", e)
        finally:
            with self._conn_lock:
                if client_sock in self._active_connections:
                    self._active_connections.remove(client_sock)
            try:
                client_sock.close()
            except Exception:
                pass

    def _process_raw_message(self, raw_text: str) -> IPCResponse:
        """Validate, authorize, and dispatch an incoming raw JSON message."""
        try:
            payload = json.loads(raw_text)
            request = IPCRequest.from_dict(payload)
        except Exception as err:
            logger.warning("Malformed IPC request payload received: %s", err)
            return IPCResponse(
                request_id="invalid",
                success=False,
                error=f"Invalid request schema: {err}",
                category=ErrorCategory.VALIDATION_ERROR.value,
            )

        # Session token authenticity check
        if self.session_token:
            if not request.token or request.token != self.session_token:
                logger.warning("Unauthorized IPC request rejected (request_id=%s)", request.request_id)
                return IPCResponse(
                    request_id=request.request_id,
                    success=False,
                    error="Authentication error: Invalid or missing session token",
                    category=ErrorCategory.AUTHENTICATION_ERROR.value,
                )

        op = request.type
        # Security validation against forbidden actions
        if op in FORBIDDEN_OPERATIONS:
            logger.warning("Blocked forbidden IPC operation '%s' (request_id=%s)", op, request.request_id)
            return IPCResponse(
                request_id=request.request_id,
                success=False,
                error=f"Operation '{op}' is strictly prohibited over IPC.",
                category=ErrorCategory.SAFETY_ERROR.value,
            )

        if op not in ALLOWED_OPERATIONS:
            logger.warning("Rejected unsupported IPC operation '%s' (request_id=%s)", op, request.request_id)
            return IPCResponse(
                request_id=request.request_id,
                success=False,
                error=f"Unsupported operation '{op}'.",
                category=ErrorCategory.VALIDATION_ERROR.value,
            )

        handler = self._handlers.get(op)
        if not handler:
            return IPCResponse(
                request_id=request.request_id,
                success=False,
                error=f"No handler registered for operation '{op}'.",
                category=ErrorCategory.RUNTIME_ERROR.value,
            )

        try:
            result_data = handler(request.parameters)
            return IPCResponse(
                request_id=request.request_id,
                success=True,
                data=result_data if isinstance(result_data, dict) else {"result": result_data},
            )
        except Exception as handler_err:
            logger.error("Handler error executing '%s': %s", op, handler_err)
            return IPCResponse(
                request_id=request.request_id,
                success=False,
                error=f"Operation execution failed: {type(handler_err).__name__}: {str(handler_err)}",
                category=ErrorCategory.RUNTIME_ERROR.value,
            )

    def _send_response(self, client_sock: socket.socket, response: IPCResponse) -> None:
        """Send JSON response terminated with newline."""
        try:
            payload = json.dumps(response.to_dict()) + "\n"
            client_sock.sendall(payload.encode("utf-8"))
        except Exception as e:
            logger.debug("Failed to send IPC response: %s", e)

    def stop(self) -> None:
        """Idempotent shutdown of IPC server and all active client connections."""
        if not self._is_running:
            return

        self._is_running = False
        logger.info("Stopping IPCServer...")

        # Close all active client connections
        with self._conn_lock:
            for sock in list(self._active_connections):
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    sock.close()
                except Exception:
                    pass
            self._active_connections.clear()

        # Close server listening socket
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
            self._server_socket = None

        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=1.0)
        logger.info("IPCServer stopped.")
