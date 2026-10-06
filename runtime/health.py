"""
Lightweight health monitoring for CHARVIS Background Runtime (Phase 16).
Provides non-destructive status inspection across core subsystems.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from logger import get_logger

logger = get_logger("CHARVIS.Runtime.Health")


class HealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


class RuntimeHealthChecker:
    """
    Performs fast, non-destructive health checks of CHARVIS subsystems.
    Does NOT make external network requests or modify state.
    """

    def __init__(
        self,
        brain: Optional[Any] = None,
        ipc_server: Optional[Any] = None,
    ) -> None:
        self.brain = brain
        self.ipc_server = ipc_server

    def check_health(self) -> Dict[str, Any]:
        """
        Evaluate all subsystems and return overall health status and breakdown.
        """
        subsystems: Dict[str, Dict[str, Any]] = {}
        issues_critical = 0
        issues_degraded = 0

        # 1. AI Brain Core check
        if self.brain is not None:
            subsystems["core"] = {"status": "ok", "detail": "AIBrain initialized"}
        else:
            subsystems["core"] = {"status": "error", "detail": "AIBrain not initialized"}
            issues_critical += 1

        # 2. IPC Server check
        if self.ipc_server is not None:
            if getattr(self.ipc_server, "is_running", False):
                port = getattr(self.ipc_server, "actual_port", 0)
                subsystems["ipc"] = {"status": "ok", "detail": f"Listening on port {port}"}
            else:
                subsystems["ipc"] = {"status": "error", "detail": "IPCServer is not running"}
                issues_critical += 1
        else:
            subsystems["ipc"] = {"status": "disabled", "detail": "IPCServer not configured"}
            issues_degraded += 1

        # 3. Memory Subsystem check
        try:
            mem_mgr = getattr(self.brain, "memory_manager", None)
            if mem_mgr is not None:
                count = mem_mgr.session.count()
                subsystems["memory"] = {"status": "ok", "detail": f"Session active ({count} items)"}
            else:
                subsystems["memory"] = {"status": "degraded", "detail": "Memory manager unavailable"}
                issues_degraded += 1
        except Exception as e:
            subsystems["memory"] = {"status": "error", "detail": f"Memory check failed: {e}"}
            issues_critical += 1

        # 4. Planner Subsystem check
        try:
            planner = getattr(self.brain, "planner", None)
            executor = getattr(self.brain, "task_executor", None)
            if planner is not None and executor is not None:
                subsystems["planner"] = {"status": "ok", "detail": "Planner & executor ready"}
            else:
                subsystems["planner"] = {"status": "degraded", "detail": "Planner or executor missing"}
                issues_degraded += 1
        except Exception as e:
            subsystems["planner"] = {"status": "error", "detail": f"Planner check failed: {e}"}
            issues_degraded += 1

        # 5. Voice Subsystem check (non-destructive)
        try:
            from voice.audio import AudioCapture
            audio = AudioCapture()
            mic_ok = audio.is_microphone_available()
            subsystems["voice"] = {
                "status": "ok" if mic_ok else "unavailable",
                "detail": "Microphone detected" if mic_ok else "No microphone hardware detected",
            }
            if not mic_ok:
                issues_degraded += 1
        except Exception as e:
            subsystems["voice"] = {"status": "unavailable", "detail": f"Audio check: {e}"}
            issues_degraded += 1

        # 6. Browser Automation check
        try:
            from tools.browser import get_browser_controller
            controller = get_browser_controller()
            is_active = controller.is_active if hasattr(controller, "is_active") else False
            subsystems["browser"] = {
                "status": "ok",
                "detail": "Browser active" if is_active else "Browser standby (not launched)",
            }
        except Exception as e:
            subsystems["browser"] = {"status": "degraded", "detail": f"Browser module error: {e}"}
            issues_degraded += 1

        # Determine overall state
        if issues_critical > 0:
            overall = HealthState.UNHEALTHY.value
        elif issues_degraded > 0:
            overall = HealthState.DEGRADED.value
        else:
            overall = HealthState.HEALTHY.value

        return {
            "status": overall,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "subsystems": subsystems,
        }
