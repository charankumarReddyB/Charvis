"""
Lifecycle and single-instance management for CHARVIS Background Runtime (Phase 16).
Provides safe PID lockfiles, process metadata verification, and non-destructive stale lock recovery.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, Optional

import psutil

from config import get_settings
from logger import get_logger

logger = get_logger("CHARVIS.Runtime.Lifecycle")


class RuntimeAlreadyRunningError(RuntimeError):
    """Raised when an active background runtime instance is already running."""
    pass


AnotherInstanceRunningError = RuntimeAlreadyRunningError


class RuntimeLock:
    """
    Guarantees a single authoritative background runtime instance.
    Uses process metadata and start timestamps to prevent PID collision errors.
    """

    def __init__(self, runtime_dir: Optional[Path] = None) -> None:
        settings = get_settings()
        self.runtime_dir = Path(runtime_dir) if runtime_dir else settings.runtime_dir
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file = self.runtime_dir / "runtime.lock"
        self.meta_file = self.runtime_dir / "runtime.json"
        self._acquired = False

    @property
    def is_acquired(self) -> bool:
        return self._acquired

    def get_runtime_metadata(self) -> Optional[Dict[str, Any]]:
        """Read and return current runtime metadata if metadata file exists and is valid."""
        if not self.meta_file.exists():
            return None
        try:
            with open(self.meta_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to read runtime metadata: %s", e)
            return None

    def is_another_instance_running(self) -> bool:
        """
        Check if an active runtime instance exists and its recorded process is alive.
        Does NOT rely on PID alone: inspects process start time and status safely.
        """
        meta = self.get_runtime_metadata()
        if not meta:
            # Fallback: check lock file
            if self.lock_file.exists():
                try:
                    pid_str = self.lock_file.read_text(encoding="utf-8").strip()
                    if pid_str.isdigit():
                        return self._is_process_alive(int(pid_str))
                except Exception:
                    pass
            return False

        pid = meta.get("pid")
        if not pid or not isinstance(pid, int):
            return False

        recorded_create_time = meta.get("process_create_time")
        return self._is_process_alive(pid, recorded_create_time)

    def _is_process_alive(self, pid: int, recorded_create_time: Optional[float] = None) -> bool:
        """Safely inspect whether the given process is still alive and matches."""
        try:
            proc = psutil.Process(pid)
            if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                return False

            # If create_time was recorded, verify PID hasn't been recycled by another process
            if recorded_create_time is not None:
                current_create_time = proc.create_time()
                # Allow minor float precision tolerance (within 1.0 second)
                if abs(current_create_time - recorded_create_time) > 1.0:
                    logger.warning(
                        "PID %d reused by an unrelated process (create_time mismatch: recorded=%.2f, current=%.2f).",
                        pid,
                        recorded_create_time,
                        current_create_time,
                    )
                    return False

            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
        except Exception as e:
            logger.warning("Unexpected error inspecting process %d: %s", pid, e)
            return False

    def acquire(self, port: int, host: str = "127.0.0.1", version: str = "0.17.0", session_token: Optional[str] = None) -> None:
        """
        Acquire the single runtime lock.
        Raises RuntimeAlreadyRunningError if an existing runtime is verified alive.
        Recovers stale lock safely if recorded process is dead.
        """
        if self.is_another_instance_running():
            meta = self.get_runtime_metadata() or {}
            existing_pid = meta.get("pid", "unknown")
            msg = f"Another CHARVIS runtime instance is already active (PID: {existing_pid}). Duplicate startup rejected."
            logger.warning(msg)
            raise RuntimeAlreadyRunningError(msg)

        # Recover stale metadata if dead
        if self.lock_file.exists() or self.meta_file.exists():
            logger.info("Stale runtime lock or metadata detected without active process. Recovering stale files safely.")
            self._cleanup_files()

        pid = os.getpid()
        create_time = None
        try:
            create_time = psutil.Process(pid).create_time()
        except Exception:
            pass

        now_iso = datetime.now(timezone.utc).isoformat()
        metadata: Dict[str, Any] = {
            "pid": pid,
            "process_create_time": create_time,
            "version": version,
            "host": host,
            "port": port,
            "started_at": now_iso,
            "timestamp": time.time(),
        }
        if session_token:
            metadata["session_token"] = session_token

        try:
            # Write lock file
            self.lock_file.write_text(str(pid), encoding="utf-8")
            # Write metadata
            with open(self.meta_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
            self._acquired = True
            logger.info("Acquired single runtime instance lock (PID: %d, Port: %d).", pid, port)
        except Exception as e:
            logger.error("Failed to write runtime lock metadata: %s", e)
            self._cleanup_files()
            raise RuntimeError(f"Could not acquire runtime lock: {e}")

    def release(self) -> None:
        """
        Release runtime lock on normal shutdown.
        Only deletes lock if current process owns it.
        """
        if not self._acquired:
            return

        try:
            # Verify we are releasing our own lock
            meta = self.get_runtime_metadata()
            if meta and meta.get("pid") == os.getpid():
                self._cleanup_files()
                logger.info("Released runtime instance lock cleanly.")
        except Exception as e:
            logger.warning("Error releasing runtime lock: %s", e)
        finally:
            self._acquired = False

    def _cleanup_files(self) -> None:
        """Non-destructive removal of lock and metadata files."""
        for path in (self.lock_file, self.meta_file):
            try:
                if path.exists():
                    path.unlink()
            except Exception as e:
                logger.warning("Could not delete %s: %s", path.name, e)
