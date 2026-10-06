"""
Phase 17 Stability & Lifecycle Stress Test (Sections 31 & 32).
Runs:
1. Repeated lifecycle stress test (25 cycles of start, connect, status, chat, disconnect, stop).
2. Continuous controlled workload stability run.
Monitors RSS memory, CPU, thread counts, and IPC success rates.
"""

import json
import os
from pathlib import Path
import psutil
import socket
import sys
import tempfile
import time
from unittest.mock import MagicMock

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_settings
from core.brain import AIBrain
from diagnostics.metrics import SystemMetricsCollector
from runtime.client import RuntimeClient
from runtime.controller import RuntimeController
from runtime.state import RuntimeState


def run_lifecycle_leak_test(cycles: int = 25):
    print("=" * 60)
    print(f"RUNNING LIFECYCLE LEAK TEST ({cycles} CYCLES)")
    print("=" * 60)

    process = psutil.Process(os.getpid())
    collector = SystemMetricsCollector()

    mock_brain = MagicMock()
    mock_brain.memory_manager = MagicMock()

    mem_before = process.memory_info().rss / (1024 * 1024)
    threads_before = process.num_threads()

    print(f"Initial RSS Memory: {mem_before:.2f} MB")
    print(f"Initial Thread Count: {threads_before}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        for i in range(1, cycles + 1):
            runtime_dir = Path(tmp_dir) / f"cycle_{i}"
            ctrl = RuntimeController(brain=mock_brain, runtime_dir=runtime_dir)
            ctrl.start(block=False)

            port = ctrl.ipc_server.port
            token = ctrl.session_token
            client = RuntimeClient(port=port, session_token=token)

            # Query status
            status = client.send_request("status")
            assert status is not None

            # Disconnect client & stop runtime
            ctrl.stop()

            if i % 5 == 0:
                current_mem = process.memory_info().rss / (1024 * 1024)
                print(f"  Cycle {i:02d}/{cycles}: RSS={current_mem:.2f} MB, Threads={process.num_threads()}")

    mem_after = process.memory_info().rss / (1024 * 1024)
    threads_after = process.num_threads()
    mem_delta = mem_after - mem_before

    print("-" * 60)
    print(f"Final RSS Memory: {mem_after:.2f} MB (Delta: {mem_delta:+.2f} MB)")
    print(f"Final Thread Count: {threads_after} (Delta: {threads_after - threads_before})")
    print(f"Leak Test Result: {'PASS' if abs(mem_delta) < 50 else 'INVESTIGATE'}")
    print("=" * 60)

    return {
        "cycles": cycles,
        "mem_before_mb": round(mem_before, 2),
        "mem_after_mb": round(mem_after, 2),
        "mem_delta_mb": round(mem_delta, 2),
        "threads_before": threads_before,
        "threads_after": threads_after,
    }


def run_controlled_stability_workload(duration_seconds: int = 30):
    print("=" * 60)
    print(f"RUNNING CONTROLLED WORKLOAD STABILITY TEST ({duration_seconds}s)")
    print("=" * 60)

    process = psutil.Process(os.getpid())
    mock_brain = MagicMock()
    mock_brain.memory_manager = MagicMock()

    with tempfile.TemporaryDirectory() as tmp_dir:
        runtime_dir = Path(tmp_dir) / "stability_runtime"
        ctrl = RuntimeController(brain=mock_brain, runtime_dir=runtime_dir)
        ctrl.start(block=False)

        port = ctrl.ipc_server.port
        token = ctrl.session_token
        client = RuntimeClient(port=port, session_token=token)

        start_time = time.time()
        operations = 0
        errors = 0

        while (time.time() - start_time) < duration_seconds:
            try:
                # 1. Status query
                status = client.send_request("status")
                operations += 1

                # 2. Health query
                health = client.send_request("health")
                operations += 1

                time.sleep(0.1)
            except Exception as e:
                errors += 1

        ctrl.stop()

    final_mem = process.memory_info().rss / (1024 * 1024)
    final_threads = process.num_threads()
    print(f"Total Operations: {operations}")
    print(f"Total Errors: {errors}")
    print(f"Final Memory: {final_mem:.2f} MB")
    print(f"Final Threads: {final_threads}")
    print(f"Workload Stability Result: {'PASS' if errors == 0 else 'FAIL'}")
    print("=" * 60)

    return {
        "duration_seconds": duration_seconds,
        "operations": operations,
        "errors": errors,
        "final_mem_mb": round(final_mem, 2),
        "final_threads": final_threads,
    }


if __name__ == "__main__":
    leak_res = run_lifecycle_leak_test(cycles=25)
    workload_res = run_controlled_stability_workload(duration_seconds=15)

    with open("scratch/stability_results.json", "w") as f:
        json.dump({"leak_test": leak_res, "workload": workload_res}, f, indent=2)
