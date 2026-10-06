"""
Runtime Manager for CHARVIS (Phase 16).
High-level interface to inspect, connect to, or launch the background runtime process.
"""

from pathlib import Path
import subprocess
import sys
import time
from typing import Optional

from config import BASE_DIR, get_settings
from logger import get_logger
from runtime.client import RuntimeClient, RuntimeConnectionRefusedError
from runtime.controller import RuntimeController
from runtime.lifecycle import RuntimeLock
from runtime.models import RuntimeStatus

logger = get_logger("CHARVIS.Runtime.Manager")

_global_controller: Optional[RuntimeController] = None


def get_runtime_controller() -> RuntimeController:
    """Retrieve or create in-process singleton RuntimeController."""
    global _global_controller
    if _global_controller is None:
        _global_controller = RuntimeController()
    return _global_controller


def set_runtime_controller(controller: Optional[RuntimeController]) -> None:
    """Set or reset in-process singleton RuntimeController."""
    global _global_controller
    _global_controller = controller


class RuntimeManager:
    """
    High-level manager for checking runtime status and spawning background daemon.
    """

    def __init__(self, runtime_dir: Optional[Path] = None) -> None:
        self.settings = get_settings()
        self.runtime_dir = runtime_dir or self.settings.runtime_dir
        self.lock = RuntimeLock(runtime_dir=self.runtime_dir)

    def is_running(self) -> bool:
        """Check whether a background runtime is alive and responding."""
        if not self.lock.is_another_instance_running():
            return False
        client = RuntimeClient(runtime_dir=self.runtime_dir)
        return client.is_runtime_running()

    def get_client(self) -> RuntimeClient:
        """Create a client configured for the local runtime."""
        return RuntimeClient(runtime_dir=self.runtime_dir)

    def get_status(self) -> RuntimeStatus:
        """Fetch status either via client (if running) or default stopped status."""
        client = self.get_client()
        try:
            return client.get_status()
        except Exception:
            return RuntimeStatus(
                state="STOPPED",
                version=self.settings.app_version,
                health_state="UNHEALTHY",
            )

    def start_background_process(self) -> bool:
        """
        Launch CHARVIS background runtime as a detached background process.
        Uses explicit executable path without shell=True.
        """
        if self.is_running():
            logger.info("CHARVIS runtime is already running.")
            return True

        cmd = [sys.executable, str(BASE_DIR / "main.py"), "--background"]
        logger.info("Launching background runtime: %s", " ".join(cmd))

        try:
            # On Windows, use creationflags to run detached without popping terminal if possible
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

            subprocess.Popen(
                cmd,
                cwd=str(BASE_DIR),
                close_fds=True,
                creationflags=creationflags,
            )

            # Wait up to 5 seconds for runtime to report online
            for _ in range(25):
                time.sleep(0.2)
                if self.is_running():
                    logger.info("Background runtime successfully launched and verified online.")
                    return True

            logger.warning("Background runtime launched but took too long to report online.")
            return False
        except Exception as e:
            logger.error("Failed to launch background runtime process: %s", e)
            return False

    def stop_runtime(self) -> bool:
        """Stop running background runtime via IPC request."""
        if not self.is_running():
            return True

        client = self.get_client()
        try:
            client.shutdown()
            for _ in range(15):
                time.sleep(0.2)
                if not self.is_running():
                    return True
            return False
        except Exception as e:
            logger.warning("Failed to shut down runtime via IPC: %s", e)
            return False
