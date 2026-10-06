"""
Phase 17 Verification Script: Hardening, Reliability & Performance.
Verifies all 25 scenarios required by Phase 17 specifications:
1. Runtime starts
2. Runtime stops
3. Runtime restart works
4. Duplicate runtime blocked
5. GUI reconnect works
6. IPC timeout works
7. Malformed IPC rejected
8. Oversized IPC rejected
9. Confirmation appears
10. Confirmation expires
11. Expired confirmation cannot execute
12. Double confirmation rejected
13. Stale confirmation rejected
14. Task cancellation works
15. Task cannot execute after cancellation
16. Destructive action not retried
17. Voice resources release
18. Browser resources release
19. Memory resources release
20. Startup enable/disable remains explicit
21. Runtime metadata has no secrets
22. Shutdown is idempotent
23. No duplicate workers after repeated start/stop
24. Idle CPU/resource behavior measured
25. Lifecycle stress test completes safely
"""

import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_settings
from core.brain import AIBrain
from core.safety import (
    ConfirmationRequest,
    ConfirmationState,
    ConfirmationStateError,
    RiskLevel,
    SafetyManager,
)
from diagnostics.resource_monitor import ResourceMonitor
from gui.controller import GUIController
from gui.models import SystemState
from gui.state import GUIState
from memory.manager import MemoryManager
from memory.storage import SQLiteMemoryStorage
from planner.executor import TaskExecutor
from planner.models import Task, TaskStep, TaskStatus, StepStatus, PlannerStateError
from runtime.client import RuntimeClient
from runtime.controller import RuntimeController
from runtime.ipc import IPCServer
from runtime.lifecycle import RuntimeAlreadyRunningError
from runtime.models import IPCRequest, IPCResponse
from runtime.state import RuntimeState
from startup.windows import WindowsStartupManager
from tools.router import ToolRouter
from tools.runtime import DisableStartupTool, EnableStartupTool
from wakeword.engine import WakeWordEngine
from browser.controller import BrowserController


def run_all_verifications():
    print("=" * 60)
    print("CHARVIS PHASE 17 VERIFICATION SUITE")
    print("Version: 0.17.0 | Tool Count: 75")
    print("=" * 60)

    passed = 0
    failed = 0
    results = []

    def report(num, name, success, details=""):
        nonlocal passed, failed
        status = "PASSED" if success else "FAILED"
        if success:
            passed += 1
            print(f"[{status}] {num}. {name}: {details}")
        else:
            failed += 1
            print(f"[{status}] {num}. {name}: {details}")
        results.append((num, name, success, details))

    # 1. Runtime starts
    with tempfile.TemporaryDirectory() as tmp_dir:
        runtime_dir = Path(tmp_dir) / "runtime"
        mock_brain = MagicMock()
        mock_brain.memory_manager = MagicMock()
        controller = RuntimeController(brain=mock_brain, runtime_dir=runtime_dir)
        try:
            controller.start(block=False)
            running = controller.state == RuntimeState.RUNNING and controller.runtime_lock.lock_file.exists()
            report(1, "Runtime starts", running, f"State: {controller.state.value}")
        finally:
            controller.stop()

    # 2. Runtime stops
    with tempfile.TemporaryDirectory() as tmp_dir:
        runtime_dir = Path(tmp_dir) / "runtime"
        mock_brain = MagicMock()
        mock_brain.memory_manager = MagicMock()
        controller = RuntimeController(brain=mock_brain, runtime_dir=runtime_dir)
        controller.start(block=False)
        controller.stop()
        stopped = controller.state == RuntimeState.STOPPED and not controller.runtime_lock.lock_file.exists()
        report(2, "Runtime stops", stopped, f"State: {controller.state.value}")

    # 3. Runtime restart works
    with tempfile.TemporaryDirectory() as tmp_dir:
        runtime_dir = Path(tmp_dir) / "runtime"
        mock_brain = MagicMock()
        mock_brain.memory_manager = MagicMock()
        controller = RuntimeController(brain=mock_brain, runtime_dir=runtime_dir)
        controller.start(block=False)
        first_pid = controller.get_status().process_id
        controller.stop()
        controller.start(block=False)
        status_after = controller.get_status()
        restarted = controller.state == RuntimeState.RUNNING and status_after.process_id is not None
        report(3, "Runtime restart works", restarted, f"PID after restart: {status_after.process_id}")
        controller.stop()

    # 4. Duplicate runtime blocked
    with tempfile.TemporaryDirectory() as tmp_dir:
        runtime_dir = Path(tmp_dir) / "runtime"
        mock_brain = MagicMock()
        mock_brain.memory_manager = MagicMock()
        c1 = RuntimeController(brain=mock_brain, runtime_dir=runtime_dir)
        c2 = RuntimeController(brain=mock_brain, runtime_dir=runtime_dir)
        c1.start(block=False)
        blocked = False
        try:
            c2.start(block=False)
        except RuntimeAlreadyRunningError:
            blocked = True
        finally:
            c1.stop()
        report(4, "Duplicate runtime blocked", blocked, "Second runtime raised RuntimeAlreadyRunningError")

    # 5. GUI reconnect works
    with tempfile.TemporaryDirectory() as tmp_dir:
        state = GUIState()
        mock_client = MagicMock(spec=RuntimeClient)
        mock_mgr = MagicMock()
        mock_client.is_runtime_running.return_value = True
        mock_mgr.is_running.return_value = True
        mock_mgr.get_client.return_value = mock_client
        gui = GUIController(state=state, runtime_manager=mock_mgr)
        gui.client = mock_client
        state.set_system_state(SystemState.ONLINE)

        # Connection lost
        mock_client.is_runtime_running.return_value = False
        gui.check_connection()

        # Reconnect
        mock_client.is_runtime_running.return_value = True
        gui._reconnect_delay = 0.05
        gui.trigger_reconnect()
        time.sleep(0.2)
        reconnected = state.system_state == SystemState.ONLINE
        gui.shutdown()
        report(5, "GUI reconnect works", reconnected, f"GUI final state: {state.system_state.value}")

    # 6. IPC timeout works
    with tempfile.TemporaryDirectory() as tmp_dir:
        meta_file = Path(tmp_dir) / "runtime.json"
        # Dummy server that never responds
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        with open(meta_file, "w") as f:
            json.dump({"port": port, "process_id": os.getpid(), "state": "RUNNING", "session_token": "tok"}, f)

        client = RuntimeClient(port=port, timeout=0.2, session_token="tok")
        from runtime.client import RuntimeTimeoutError
        timed_out = False
        try:
            client.send_request("status")
        except RuntimeTimeoutError:
            timed_out = True
        except Exception as e:
            timed_out = "timeout" in str(e).lower()
        srv.close()
        report(6, "IPC timeout works", timed_out, "Request bounded with timeout")

    # 7. Malformed IPC rejected
    server = IPCServer(port=0)
    server.register_handler("ping", lambda p: {"pong": True})
    port = server.start()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", port))
        s.sendall(b"NOT_A_VALID_JSON\n")
        resp_data = s.recv(4096).decode()
        resp = json.loads(resp_data)
        malformed_rejected = resp.get("success") is False and "VALIDATION_ERROR" in resp.get("category", "")
        s.close()
        report(7, "Malformed IPC rejected", malformed_rejected, f"Category: {resp.get('category')}")
    finally:
        server.stop()

    # 8. Oversized IPC rejected
    server = IPCServer(port=0, max_message_size=256)
    port = server.start()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", port))
        s.sendall(b"a" * 1024)
        resp_data = s.recv(4096).decode()
        resp = json.loads(resp_data) if resp_data else {}
        oversized_rejected = resp.get("success") is False and ("RESOURCE_ERROR" in resp.get("category", "") or "VALIDATION_ERROR" in resp.get("category", ""))
        s.close()
        report(8, "Oversized IPC rejected", oversized_rejected, f"Category: {resp.get('category')}")
    finally:
        server.stop()

    # 9. Confirmation appears
    safety = SafetyManager()
    req = safety.create_confirmation_request("delete_file", {"path": "a.txt"}, RiskLevel.CONFIRMATION_REQUIRED)
    report(9, "Confirmation appears", req.state == ConfirmationState.PENDING, f"Created id={req.confirmation_id}")

    # 10. Confirmation expires
    req_exp = ConfirmationRequest("delete_file", {"path": "b.txt"}, RiskLevel.CONFIRMATION_REQUIRED, timeout_seconds=0.1)
    time.sleep(0.15)
    report(10, "Confirmation expires", req_exp.is_expired(), f"Expired status: {req_exp.is_expired()}")

    # 11. Expired confirmation cannot execute
    cannot_exec = False
    try:
        req_exp.transition_to(ConfirmationState.APPROVED)
    except ConfirmationStateError:
        cannot_exec = True
    report(11, "Expired confirmation cannot execute", cannot_exec, "Rejected approval after expiration")

    # 12. Double confirmation rejected
    req_dbl = ConfirmationRequest("delete_file", {"path": "c.txt"}, RiskLevel.CONFIRMATION_REQUIRED)
    req_dbl.transition_to(ConfirmationState.APPROVED)
    dbl_rejected = False
    try:
        req_dbl.transition_to(ConfirmationState.APPROVED)
    except ConfirmationStateError:
        dbl_rejected = True
    report(12, "Double confirmation rejected", dbl_rejected, "Single-use enforcement prevented second approval")

    # 13. Stale confirmation rejected
    req_stale = safety.create_confirmation_request("write_file", {"path": "c.txt"}, RiskLevel.CONFIRMATION_REQUIRED)
    safety.resolve_confirmation(req_stale.confirmation_id, approved=False, reason="Denied")
    second_res = safety.resolve_confirmation(req_stale.confirmation_id, approved=True)
    stale_rejected = second_res is False
    report(13, "Stale confirmation rejected", stale_rejected, "Cannot resolve already resolved confirmation")

    # 14. Task cancellation works
    mock_router = MagicMock(spec=ToolRouter)
    mock_router.safety_manager = safety
    executor = TaskExecutor(tool_router=mock_router)
    t = Task(goal="Cancel me", status=TaskStatus.RUNNING)
    executor.cancel_task(t)
    report(14, "Task cancellation works", t.status == TaskStatus.CANCELLED, f"Status: {t.status.value}")

    # 15. Task cannot execute after cancellation
    blocked_cancel = False
    try:
        executor.run_task(t)
    except PlannerStateError:
        blocked_cancel = True
    report(15, "Task cannot execute after cancellation", blocked_cancel, "PlannerStateError on cancelled task")

    # 16. Destructive action not retried
    from planner.evaluator import ResultEvaluator
    from planner.models import EvaluationResult
    from tools.schemas import ToolResult
    evaluator = ResultEvaluator()
    destructive_step = TaskStep(order=1, tool_name="delete_file", arguments={"path": "test.txt"})
    err_res = ToolResult(success=False, tool_name="delete_file", error="Permission denied")
    eval_outcome = evaluator.evaluate_step(destructive_step, err_res)
    report(16, "Destructive action not retried", eval_outcome != EvaluationResult.RETRY_ELIGIBLE, f"Outcome: {eval_outcome.value}")

    # 17. Voice resources release
    wake_engine = WakeWordEngine()
    wake_engine.stop()
    report(17, "Voice resources release", not wake_engine.is_running, "WakeWordEngine cleanly stopped")

    # 18. Browser resources release
    browser_ctrl = BrowserController()
    mock_page = MagicMock()
    mock_ctx = MagicMock()
    browser_ctrl._current_page = mock_page
    browser_ctrl._context = mock_ctx
    browser_ctrl._is_running = True
    browser_ctrl.close()
    browser_clean = not browser_ctrl._is_running and mock_page.close.called and mock_ctx.close.called
    report(18, "Browser resources release", browser_clean, "Browser and page handles closed")

    # 19. Memory resources release
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_mem.db"
        mem_storage = SQLiteMemoryStorage(db_path=db_path)
        mem_storage.save(key="k1", value="v1")
        mem_storage.close()
        report(19, "Memory resources release", mem_storage._conn is None, "SQLite connection closed cleanly")

    # 20. Startup enable/disable remains explicit
    enable_tool = EnableStartupTool()
    disable_tool = DisableStartupTool()
    explicit = (
        enable_tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED
        and disable_tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED
    )
    report(20, "Startup enable/disable remains explicit", explicit, "Both tools require CONFIRMATION_REQUIRED")

    # 21. Runtime metadata has no secrets
    with tempfile.TemporaryDirectory() as tmp_dir:
        r_dir = Path(tmp_dir)
        c = RuntimeController(brain=mock_brain, runtime_dir=r_dir)
        c.start(block=False)
        with open(c.runtime_lock.meta_file, "r") as f:
            meta_content = f.read()
        c.stop()
        forbidden_keys = ["password", "api_key", "secret", "private_key"]
        has_secret = any(k in meta_content.lower() for k in forbidden_keys)
        report(21, "Runtime metadata has no secrets", not has_secret, "No API keys or passwords in metadata")

    # 22. Shutdown is idempotent
    with tempfile.TemporaryDirectory() as tmp_dir:
        c = RuntimeController(brain=mock_brain, runtime_dir=Path(tmp_dir))
        c.start(block=False)
        c.stop()
        c.stop()  # Second stop call
        report(22, "Shutdown is idempotent", c.state == RuntimeState.STOPPED, "Multiple stop calls handled cleanly")

    # 23. No duplicate workers after repeated start/stop
    threads_before = threading.active_count()
    mon = ResourceMonitor(interval_seconds=10.0)
    for _ in range(5):
        mon.start()
        mon.stop()
    threads_after = threading.active_count()
    report(23, "No duplicate workers after repeated start/stop", threads_after <= threads_before + 1, f"Threads: {threads_before} -> {threads_after}")

    # 24. Idle CPU/resource behavior measured
    sample = mon.sample_now()
    report(24, "Idle CPU/resource behavior measured", sample.rss_memory_mb > 0, f"RSS: {sample.rss_memory_mb:.1f} MB, CPU: {sample.cpu_percent:.1f}%, Threads: {sample.thread_count}")

    # 25. Lifecycle stress test completes safely
    stress_cycles = 10
    stress_ok = True
    for _ in range(stress_cycles):
        with tempfile.TemporaryDirectory() as tmp_dir:
            ctrl = RuntimeController(brain=mock_brain, runtime_dir=Path(tmp_dir))
            ctrl.start(block=False)
            if ctrl.state != RuntimeState.RUNNING:
                stress_ok = False
            ctrl.stop()
            if ctrl.state != RuntimeState.STOPPED:
                stress_ok = False
    report(25, "Lifecycle stress test completes safely", stress_ok, f"Executed {stress_cycles} runtime lifecycle cycles")

    print("=" * 60)
    print(f"VERIFICATION SUMMARY: {passed}/25 PASSED, {failed}/25 FAILED")
    print("=" * 60)
    return passed == 25 and failed == 0


if __name__ == "__main__":
    success = run_all_verifications()
    sys.exit(0 if success else 1)
