"""
Authoritative Background Runtime Controller for CHARVIS (Phase 16).
Manages lifecycle, IPC server, health checks, single-instance locks, and graceful resource cleanup.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import threading
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

from config import Settings, get_settings
from logger import get_logger
from runtime.health import RuntimeHealthChecker
from runtime.ipc import IPCServer
from runtime.lifecycle import RuntimeLock
from runtime.models import RuntimeStatus
from runtime.state import InvalidStateTransitionError, RuntimeState, RuntimeStateMachine

if TYPE_CHECKING:
    from core.brain import AIBrain

logger = get_logger("CHARVIS.Runtime.Controller")


class RuntimeController:
    """
    Coordinates the CHARVIS Background Runtime lifecycle.
    Hosts the authoritative AIBrain and handles IPC requests, but never executes arbitrary tools directly.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        brain: Optional[Any] = None,
        runtime_dir: Optional[Path] = None,
    ) -> None:
        self.settings = settings or get_settings()
        if brain is not None:
            self.brain = brain
        else:
            from core.brain import AIBrain
            self.brain = AIBrain()
        import secrets
        self.session_token = secrets.token_hex(16)
        self.state_machine = RuntimeStateMachine(initial_state=RuntimeState.STOPPED)
        self.runtime_lock = RuntimeLock(runtime_dir=runtime_dir or self.settings.runtime_dir)
        self.ipc_server = IPCServer(
            host=self.settings.runtime_host,
            port=self.settings.runtime_port,
            max_message_size=self.settings.runtime_max_message_size,
            session_token=self.session_token,
            max_connections=self.settings.max_ipc_connections,
        )
        self.health_checker = RuntimeHealthChecker(brain=self.brain, ipc_server=self.ipc_server)
        self.resource_monitor = None

        self._started_at: Optional[datetime] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._lock = threading.Lock()

        # Register IPC handlers
        self._register_ipc_handlers()

    @property
    def state(self) -> RuntimeState:
        return self.state_machine.state

    def _register_ipc_handlers(self) -> None:
        """Wire permitted IPC operations to internal controller & brain workflows."""
        self.ipc_server.register_handler("status", self._handle_ipc_status)
        self.ipc_server.register_handler("health", self._handle_ipc_health)
        self.ipc_server.register_handler("ping", lambda p: {"status": "pong"})
        self.ipc_server.register_handler("chat", self._handle_ipc_chat)
        self.ipc_server.register_handler("task_create", self._handle_ipc_task_create)
        self.ipc_server.register_handler("task_run", self._handle_ipc_task_run)
        self.ipc_server.register_handler("task_pause", self._handle_ipc_task_pause)
        self.ipc_server.register_handler("task_resume", self._handle_ipc_task_resume)
        self.ipc_server.register_handler("task_cancel", self._handle_ipc_task_cancel)
        self.ipc_server.register_handler("pause", self._handle_ipc_pause)
        self.ipc_server.register_handler("resume", self._handle_ipc_resume)
        self.ipc_server.register_handler("voice_start", self._handle_ipc_voice_start)
        self.ipc_server.register_handler("voice_stop", self._handle_ipc_voice_stop)
        self.ipc_server.register_handler("shutdown", self._handle_ipc_shutdown)

    # =========================================================================
    # Lifecycle Control
    # =========================================================================

    def start(self, block: bool = False) -> None:
        """
        Start the background runtime, acquire lock, bind IPC, and begin heartbeat.
        If block=True, waits until shutdown is requested.
        """
        with self._lock:
            if self.state_machine.is_running():
                logger.info("Runtime is already RUNNING.")
                return

            self.state_machine.transition_to(RuntimeState.STARTING, reason="Starting background runtime")
            try:
                # 1. Bind IPC server to get allocated port
                port = self.ipc_server.start()

                # 2. Acquire single instance lock with session token
                self.runtime_lock.acquire(
                    port=port,
                    host=self.settings.runtime_host,
                    version=self.settings.app_version,
                    session_token=self.session_token,
                )

                self._started_at = datetime.now(timezone.utc)
                self._shutdown_event.clear()

                # 3. Transition to RUNNING
                self.state_machine.transition_to(RuntimeState.RUNNING, reason="Runtime initialized successfully")

                # 4. Start lightweight periodic heartbeat
                self._start_heartbeat()

                # 5. Start lightweight resource monitor
                try:
                    from diagnostics.resource_monitor import ResourceMonitor
                    self.resource_monitor = ResourceMonitor(
                        interval_seconds=10.0,
                        state_provider=lambda: self.get_status().to_dict(),
                    )
                    self.resource_monitor.start()
                except Exception as e:
                    logger.debug("Resource monitor startup notice: %s", e)

                logger.info(
                    "CHARVIS Background Runtime started (PID: %d, Port: %d, Version: %s).",
                    os.getpid(),
                    port,
                    self.settings.app_version,
                )

            except Exception as e:
                logger.error("Failed to start CHARVIS Background Runtime: %s", e)
                # Cleanup partially initialized resources
                try:
                    self.ipc_server.stop()
                except Exception:
                    pass
                try:
                    self.runtime_lock.release()
                except Exception:
                    pass
                self.state_machine.set_error(str(e))
                raise

        if block:
            try:
                while not self._shutdown_event.is_set():
                    time.sleep(0.5)
            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt received in runtime loop. Shutting down...")
                self.stop()

    def stop(self) -> None:
        """
        Gracefully, boundedly, and idempotently shut down the background runtime.
        Follows authoritative 13-step Phase 17 shutdown sequence.
        """
        with self._lock:
            if self.state_machine.is_stopped():
                # Idempotent stop
                return

            logger.info("Shutting down CHARVIS Background Runtime...")
            # 1. Mark STOPPING
            try:
                self.state_machine.transition_to(RuntimeState.STOPPING, reason="Graceful shutdown initiated")
            except InvalidStateTransitionError:
                pass

            self._shutdown_event.set()

            # 2. Reject new requests (stop IPC server)
            try:
                self.ipc_server.stop()
            except Exception as e:
                logger.warning("Error stopping IPC server: %s", e)

            # 3. Cancel pending confirmations safely
            try:
                if hasattr(self.brain, "safety_manager") and hasattr(self.brain.safety_manager, "cancel_all_pending"):
                    self.brain.safety_manager.cancel_all_pending("Runtime stopping")
            except Exception as e:
                logger.debug("Confirmation cancellation notice: %s", e)

            # 4. Stop running tasks cleanly
            try:
                from tools.planner import get_task_store
                from planner.models import TaskStatus
                store = get_task_store()
                for t in store.get_active_tasks():
                    try:
                        t.transition_to(TaskStatus.CANCELLED, "Runtime shutdown")
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("Task cancellation notice: %s", e)

            # 5. Stop voice/wake-word engines
            try:
                from tools.wakeword import get_active_engine, set_active_engine
                engine = get_active_engine()
                if engine is not None:
                    engine.stop()
                    set_active_engine(None)
                    logger.info("Wake-word engine stopped.")
            except Exception as e:
                logger.debug("Wake-word cleanup notice: %s", e)

            # 6. Clean up browser automation resources
            try:
                from tools.browser import get_browser_controller
                browser = get_browser_controller()
                if hasattr(browser, "close"):
                    browser.close()
                    logger.info("Browser resources closed.")
            except Exception as e:
                logger.debug("Browser cleanup notice: %s", e)

            # 7. Clean up memory database storage handles
            try:
                if hasattr(self.brain, "memory_manager") and hasattr(self.brain.memory_manager, "storage"):
                    self.brain.memory_manager.storage.close()
            except Exception as e:
                logger.debug("Memory cleanup notice: %s", e)

            # 8. Stop resource monitor
            if self.resource_monitor:
                try:
                    self.resource_monitor.stop()
                except Exception as e:
                    logger.debug("Resource monitor stop notice: %s", e)
                self.resource_monitor = None

            # 9. Release single instance lock
            try:
                self.runtime_lock.release()
            except Exception as e:
                logger.warning("Error releasing runtime lock: %s", e)

            # 10. Mark STOPPED
            try:
                self.state_machine.transition_to(RuntimeState.STOPPED, reason="Shutdown complete")
            except Exception:
                pass

            logger.info("CHARVIS Background Runtime cleanly stopped.")

    def restart(self) -> None:
        """Gracefully restart the background runtime."""
        logger.info("Restarting CHARVIS Background Runtime...")
        self.stop()
        time.sleep(0.5)
        self.start()

    def get_status(self) -> RuntimeStatus:
        """Generate structured and sanitized RuntimeStatus snapshot."""
        now = datetime.now(timezone.utc)
        uptime = (now - self._started_at).total_seconds() if self._started_at else 0.0

        # Subsystem statuses
        active_tasks = 0
        try:
            from tools.planner import get_task_store
            store = get_task_store()
            active_tasks = len(store.get_active_tasks())
        except Exception:
            pass

        wake_word_state = "disabled"
        try:
            from tools.wakeword import get_active_engine
            engine = get_active_engine()
            if engine and getattr(engine, "is_running", False):
                wake_word_state = "listening"
        except Exception:
            pass

        health_data = self.health_checker.check_health()
        health_state = health_data.get("status", "HEALTHY")

        return RuntimeStatus(
            state=self.state_machine.state.value,
            version=self.settings.app_version,
            process_id=os.getpid() if self.state_machine.is_running() else None,
            started_at=self._started_at.isoformat() if self._started_at else None,
            uptime=round(uptime, 1),
            active_tasks=active_tasks,
            voice_state="inactive",
            wake_word_state=wake_word_state,
            browser_state="closed",
            memory_state="ready",
            health_state=health_state,
            last_error=self.state_machine.last_error,
            host=self.settings.runtime_host,
            port=self.ipc_server.actual_port if self.state_machine.is_running() else None,
        )

    def health_check(self) -> Dict[str, Any]:
        """Run and return lightweight subsystem health checks."""
        return self.health_checker.check_health()

    # =========================================================================
    # Internal Heartbeat
    # =========================================================================

    def _start_heartbeat(self) -> None:
        """Start lightweight periodic background heartbeat."""
        interval = max(5.0, min(60.0, self.settings.runtime_heartbeat_interval))

        def _heartbeat_worker() -> None:
            while not self._shutdown_event.is_set():
                try:
                    if self.state_machine.is_running():
                        health = self.health_checker.check_health()
                        if health.get("status") == "UNHEALTHY" and self.state_machine.state == RuntimeState.RUNNING:
                            self.state_machine.transition_to(
                                RuntimeState.DEGRADED,
                                reason="Subsystem health check reported UNHEALTHY",
                            )
                        elif health.get("status") == "HEALTHY" and self.state_machine.state == RuntimeState.DEGRADED:
                            self.state_machine.transition_to(
                                RuntimeState.RUNNING,
                                reason="Subsystems returned to HEALTHY",
                            )
                except Exception as e:
                    logger.debug("Heartbeat evaluation notice: %s", e)

                self._shutdown_event.wait(interval)

        self._heartbeat_thread = threading.Thread(
            target=_heartbeat_worker,
            name="CHARVIS-Heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()

    # =========================================================================
    # IPC Operation Handlers
    # =========================================================================

    def _handle_ipc_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.get_status().to_dict()

    def _handle_ipc_health(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.health_check()

    def _handle_ipc_chat(self, params: Dict[str, Any]) -> Dict[str, Any]:
        user_text = str(params.get("text", "")).strip()
        if not user_text:
            return {"response": ""}

        # Authoritative AI Brain execution
        reply = self.brain.process_user_message(user_input=user_text)
        return {"response": reply}

    def _handle_ipc_task_create(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from tools.planner import CreateTaskTool
        tool = CreateTaskTool(planner=getattr(self.brain, "planner", None))
        return tool.execute(goal=params.get("goal", ""))

    def _handle_ipc_task_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from tools.planner import RunTaskTool
        tool = RunTaskTool(executor=getattr(self.brain, "task_executor", None))
        return tool.execute(task_id=params.get("task_id", ""))

    def _handle_ipc_task_pause(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from tools.planner import PauseTaskTool
        tool = PauseTaskTool(executor=getattr(self.brain, "task_executor", None))
        return tool.execute(task_id=params.get("task_id", ""))

    def _handle_ipc_task_resume(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from tools.planner import ResumeTaskTool
        tool = ResumeTaskTool(executor=getattr(self.brain, "task_executor", None))
        return tool.execute(task_id=params.get("task_id", ""))

    def _handle_ipc_task_cancel(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from tools.planner import CancelTaskTool
        tool = CancelTaskTool(executor=getattr(self.brain, "task_executor", None))
        return tool.execute(task_id=params.get("task_id", ""), reason=params.get("reason", ""))

    def _handle_ipc_voice_start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "voice_active"}

    def _handle_ipc_voice_stop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "voice_inactive"}

    def pause(self) -> None:
        """Pause the background runtime safely."""
        with self._lock:
            if self.state_machine.state in (RuntimeState.RUNNING, RuntimeState.DEGRADED):
                self.state_machine.transition_to(RuntimeState.PAUSED, reason="User requested pause")
                logger.info("CHARVIS Background Runtime paused.")

    def resume(self) -> None:
        """Resume the background runtime safely."""
        with self._lock:
            if self.state_machine.state == RuntimeState.PAUSED:
                self.state_machine.transition_to(RuntimeState.RUNNING, reason="User requested resume")
                logger.info("CHARVIS Background Runtime resumed.")

    def _handle_ipc_pause(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self.pause()
        return {"status": "paused", "state": self.state_machine.state.value}

    def _handle_ipc_resume(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self.resume()
        return {"status": "resumed", "state": self.state_machine.state.value}

    def _handle_ipc_shutdown(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Schedule shutdown on separate thread so response returns cleanly
        threading.Thread(target=self.stop, name="CHARVIS-IPCShutdown", daemon=True).start()
        return {"status": "shutting_down"}
