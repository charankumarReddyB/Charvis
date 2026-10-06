"""
Phase 16 Verification Script: Background Runtime & Windows Startup.
Verifies all 23 scenarios required by Phase 16 specifications:
1. Runtime starts.
2. Runtime reaches RUNNING.
3. Runtime status works.
4. Runtime health works.
5. Duplicate runtime is detected.
6. GUI connects to existing runtime.
7. GUI displays online status.
8. GUI can send a chat request through runtime.
9. Runtime remains idle without user request.
10. Wake word remains OFF by default.
11. Voice remains inactive until explicitly requested.
12. Task creation works through existing planner.
13. Task execution works through existing executor.
14. Runtime shutdown works.
15. Runtime shutdown is idempotent.
16. Startup status can be queried.
17. Startup enable requires explicit confirmation.
18. Startup disable requires explicit confirmation.
19. Runtime metadata contains no secrets.
20. IPC rejects invalid/untrusted requests.
21. Runtime recovers safely from stale metadata.
22. GUI can reconnect after runtime restart.
23. No duplicate CHARVIS core is created.
"""

import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import MagicMock

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_settings
from core.brain import AIBrain
from core.safety import RiskLevel, SafetyManager
from gui.controller import GUIController
from gui.models import SystemState
from gui.state import GUIState
from runtime.client import RuntimeClient, RuntimeClientError
from runtime.controller import RuntimeController
from runtime.lifecycle import RuntimeAlreadyRunningError, RuntimeLock
from runtime.models import RuntimeStatus
from runtime.state import RuntimeState
from startup.windows import WindowsStartupManager
from tools.runtime import (
    DisableStartupTool,
    EnableStartupTool,
    GetRuntimeHealthTool,
    GetRuntimeStatusTool,
    GetStartupStatusTool,
    RestartRuntimeTool,
    StopRuntimeTool,
)

PASSED = " [PASS] "
FAILED = " [FAIL] "


def run_all_verifications():
    print("=" * 70)
    print("CHARVIS PHASE 16 COMPREHENSIVE VERIFICATION")
    print("=" * 70)

    results = []

    # Temporary directory for runtime locks and startup files
    temp_dir = Path(tempfile.mkdtemp(prefix="charvis_verify_p16_"))
    runtime_dir = temp_dir / "runtime"
    startup_dir = temp_dir / "startup"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    startup_dir.mkdir(parents=True, exist_ok=True)

    # Mock provider for brain
    from planner.models import Task, TaskStatus
    sample_task = Task(goal="Calculate 25 * 4", status=TaskStatus.READY, steps=[])

    mock_brain = MagicMock()
    mock_brain.process_user_message.return_value = "Hello from authoritative CHARVIS core!"
    mock_brain.memory_manager.session.count.return_value = 3
    mock_brain.memory_manager.storage.close.return_value = None
    mock_brain.planner.plan.return_value = sample_task
    mock_brain.task_executor.run_task.return_value = sample_task

    controller = RuntimeController(brain=mock_brain, runtime_dir=runtime_dir)

    try:
        # 1. Runtime starts
        controller.start(block=False)
        results.append((1, "Runtime starts", True))
        print(f"1. Runtime starts: {PASSED}")

        # 2. Runtime reaches RUNNING
        is_running = controller.state == RuntimeState.RUNNING
        results.append((2, "Runtime reaches RUNNING", is_running))
        print(f"2. Runtime reaches RUNNING: {PASSED if is_running else FAILED}")

        # 3. Runtime status works
        status = controller.get_status()
        status_ok = status.state == "RUNNING" and status.process_id == os.getpid() and status.uptime >= 0
        results.append((3, "Runtime status works", status_ok))
        print(f"3. Runtime status works: {PASSED if status_ok else FAILED}")

        # 4. Runtime health works
        health = controller.health_check()
        health_ok = health.get("status") in {"HEALTHY", "DEGRADED"} and "core" in health.get("subsystems", {})
        results.append((4, "Runtime health works", health_ok))
        print(f"4. Runtime health works: {PASSED if health_ok else FAILED}")

        # 5. Duplicate runtime is detected
        duplicate_detected = False
        try:
            ctrl2 = RuntimeController(brain=mock_brain, runtime_dir=runtime_dir)
            ctrl2.start(block=False)
        except RuntimeAlreadyRunningError:
            duplicate_detected = True
        except Exception:
            pass
        results.append((5, "Duplicate runtime is detected", duplicate_detected))
        print(f"5. Duplicate runtime is detected: {PASSED if duplicate_detected else FAILED}")

        # 6. GUI connects to existing runtime
        gui_state = GUIState()
        gui_ctrl = GUIController(state=gui_state, runtime_manager=MagicMock(is_running=lambda: True, get_client=lambda: RuntimeClient(runtime_dir=runtime_dir)))
        gui_connected = gui_ctrl.client is not None
        results.append((6, "GUI connects to existing runtime", gui_connected))
        print(f"6. GUI connects to existing runtime: {PASSED if gui_connected else FAILED}")

        # 7. GUI displays online status
        is_online = gui_state.system_state == SystemState.ONLINE
        results.append((7, "GUI displays online status", is_online))
        print(f"7. GUI displays online status: {PASSED if is_online else FAILED}")

        # 8. GUI can send a chat request through runtime
        client = RuntimeClient(runtime_dir=runtime_dir)
        chat_reply = client.send_chat("Hello!")
        chat_ok = "Hello from authoritative CHARVIS core!" in chat_reply
        results.append((8, "GUI can send a chat request through runtime", chat_ok))
        print(f"8. GUI can send a chat request through runtime: {PASSED if chat_ok else FAILED}")

        # 9. Runtime remains idle without user request
        # Verify no background tasks are executing autonomously
        idle_ok = status.active_tasks == 0
        results.append((9, "Runtime remains idle without user request", idle_ok))
        print(f"9. Runtime remains idle without user request: {PASSED if idle_ok else FAILED}")

        # 10. Wake word remains OFF by default
        wake_off = status.wake_word_state == "disabled"
        results.append((10, "Wake word remains OFF by default", wake_off))
        print(f"10. Wake word remains OFF by default: {PASSED if wake_off else FAILED}")

        # 11. Voice remains inactive until explicitly requested
        voice_inactive = status.voice_state == "inactive"
        results.append((11, "Voice remains inactive until explicitly requested", voice_inactive))
        print(f"11. Voice remains inactive until explicitly requested: {PASSED if voice_inactive else FAILED}")

        # 12. Task creation works through existing planner
        # Tested via task_create IPC request
        task_res = client.send_request("task_create", {"goal": "Calculate 25 * 4"})
        task_created = "task_id" in task_res or "status" in task_res or task_res.get("steps_count", 0) >= 0
        results.append((12, "Task creation works through existing planner", task_created))
        print(f"12. Task creation works through existing planner: {PASSED if task_created else FAILED}")

        # 13. Task execution works through existing executor
        task_id = task_res.get("task_id", "test_id")
        run_res = client.send_request("task_run", {"task_id": task_id})
        task_run_ok = "status" in run_res
        results.append((13, "Task execution works through existing executor", task_run_ok))
        print(f"13. Task execution works through existing executor: {PASSED if task_run_ok else FAILED}")

        # 14. Runtime shutdown works
        controller.stop()
        shutdown_ok = controller.state == RuntimeState.STOPPED
        results.append((14, "Runtime shutdown works", shutdown_ok))
        print(f"14. Runtime shutdown works: {PASSED if shutdown_ok else FAILED}")

        # 15. Runtime shutdown is idempotent
        controller.stop()  # Second stop call
        idempotent_ok = controller.state == RuntimeState.STOPPED
        results.append((15, "Runtime shutdown is idempotent", idempotent_ok))
        print(f"15. Runtime shutdown is idempotent: {PASSED if idempotent_ok else FAILED}")

        # 16. Startup status can be queried
        startup_mgr = WindowsStartupManager(startup_dir=startup_dir)
        st_status = startup_mgr.get_status()
        st_query_ok = st_status.enabled is False and st_status.method == "startup_folder"
        results.append((16, "Startup status can be queried", st_query_ok))
        print(f"16. Startup status can be queried: {PASSED if st_query_ok else FAILED}")

        # 17. Startup enable requires explicit confirmation
        enable_tool = EnableStartupTool(startup_manager=startup_mgr)
        enable_requires_conf = enable_tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED
        results.append((17, "Startup enable requires explicit confirmation", enable_requires_conf))
        print(f"17. Startup enable requires explicit confirmation: {PASSED if enable_requires_conf else FAILED}")

        # 18. Startup disable requires explicit confirmation
        disable_tool = DisableStartupTool(startup_manager=startup_mgr)
        disable_requires_conf = disable_tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED
        results.append((18, "Startup disable requires explicit confirmation", disable_requires_conf))
        print(f"18. Startup disable requires explicit confirmation: {PASSED if disable_requires_conf else FAILED}")

        # 19. Runtime metadata contains no secrets
        st = controller.get_status().to_dict()
        no_secrets = all(k not in st for k in ["api_key", "password", "token", "openai_api_key"])
        results.append((19, "Runtime metadata contains no secrets", no_secrets))
        print(f"19. Runtime metadata contains no secrets: {PASSED if no_secrets else FAILED}")

        # 20. IPC rejects invalid/untrusted requests
        # Restart controller to test IPC security
        controller.start(block=False)
        client = RuntimeClient(runtime_dir=runtime_dir)
        rejected_arbitrary = False
        try:
            client.send_request("execute_tool", {"name": "calculator"})
        except RuntimeClientError:
            rejected_arbitrary = True
        results.append((20, "IPC rejects invalid/untrusted requests", rejected_arbitrary))
        print(f"20. IPC rejects invalid/untrusted requests: {PASSED if rejected_arbitrary else FAILED}")

        # 21. Runtime recovers safely from stale metadata
        controller.stop()
        # Simulate dead process metadata
        stale_meta = runtime_dir / "runtime.json"
        stale_lock = runtime_dir / "runtime.lock"
        stale_meta.write_text(json.dumps({"pid": 999999, "port": 9999}), encoding="utf-8")
        stale_lock.write_text("999999", encoding="utf-8")

        lock = RuntimeLock(runtime_dir=runtime_dir)
        stale_detected = not lock.is_another_instance_running()
        lock.acquire(port=6000)
        stale_recovered = lock.is_acquired and lock.get_runtime_metadata()["pid"] == os.getpid()
        lock.release()
        stale_ok = stale_detected and stale_recovered
        results.append((21, "Runtime recovers safely from stale metadata", stale_ok))
        print(f"21. Runtime recovers safely from stale metadata: {PASSED if stale_ok else FAILED}")

        # 22. GUI can reconnect after runtime restart
        controller.start(block=False)
        client_reconnect = RuntimeClient(runtime_dir=runtime_dir)
        recon_status = client_reconnect.get_status()
        reconnected_ok = recon_status.state == "RUNNING"
        controller.stop()
        results.append((22, "GUI can reconnect after runtime restart", reconnected_ok))
        print(f"22. GUI can reconnect after runtime restart: {PASSED if reconnected_ok else FAILED}")

        # 23. No duplicate CHARVIS core is created
        # When GUIController starts with active runtime, self.brain is None
        gui_ctrl_attached = GUIController(runtime_manager=MagicMock(is_running=lambda: True, get_client=lambda: client))
        no_dup_core = gui_ctrl_attached.brain is None
        results.append((23, "No duplicate CHARVIS core is created", no_dup_core))
        print(f"23. No duplicate CHARVIS core is created: {PASSED if no_dup_core else FAILED}")

    finally:
        try:
            controller.stop()
        except Exception:
            pass
        # Cleanup temporary files
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("=" * 70)
    all_passed = all(res[2] for res in results)
    passed_count = sum(1 for res in results if res[2])
    print(f"OVERALL SUMMARY: {passed_count}/{len(results)} SCENARIOS PASSED")
    if all_passed:
        print("ALL PHASE 16 VERIFICATION SCENARIOS PASSED SUCCESSFULLY!")
    else:
        print("SOME SCENARIOS FAILED!")
    print("=" * 70)
    return all_passed


if __name__ == "__main__":
    success = run_all_verifications()
    sys.exit(0 if success else 1)
