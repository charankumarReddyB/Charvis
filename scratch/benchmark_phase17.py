"""
Phase 17 Benchmark Script: Performance & Diagnostics Baseline.
Measures real performance metrics on the actual running machine:
1. Startup time
2. Idle CPU
3. Idle memory
4. GUI launch / init time
5. Runtime launch time
6. Chat request latency (mock AI / fast path)
7. Task creation latency
8. IPC request latency
9. Shutdown time
"""

import json
import os
from pathlib import Path
import platform
import psutil
import socket
import sys
import tempfile
import time
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_settings
from core.brain import AIBrain
from diagnostics.metrics import SystemMetricsCollector
from gui.controller import GUIController
from gui.state import GUIState
from planner.models import Task, TaskStep
from runtime.client import RuntimeClient
from runtime.controller import RuntimeController
from runtime.state import RuntimeState


def run_benchmarks():
    print("=" * 60)
    print("CHARVIS PHASE 17 PERFORMANCE BENCHMARK")
    print("=" * 60)

    settings = get_settings()
    process = psutil.Process(os.getpid())
    collector = SystemMetricsCollector()

    # Environment
    python_ver = platform.python_version()
    windows_ver = platform.platform()
    cpu_info = platform.processor() or "x86_64"
    cpu_count = psutil.cpu_count(logical=True)
    total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
    charvis_ver = settings.app_version

    print(f"Python: {python_ver}")
    print(f"Windows: {windows_ver}")
    print(f"CPU: {cpu_info} ({cpu_count} logical cores)")
    print(f"RAM: {total_ram_gb:.2f} GB")
    print(f"CHARVIS Version: {charvis_ver}")
    print("-" * 60)

    # 1. Baseline Idle Memory & CPU
    time.sleep(0.5)
    idle_cpu = process.cpu_percent(interval=1.0)
    idle_mem_mb = process.memory_info().rss / (1024 * 1024)
    threads_count = process.num_threads()
    print(f"Idle CPU: {idle_cpu:.2f}%")
    print(f"Idle Memory: {idle_mem_mb:.2f} MB")
    print(f"Thread Count: {threads_count}")

    # 2. Runtime Launch & Shutdown Time (Repeated 5x)
    launch_times = []
    shutdown_times = []
    mock_brain = MagicMock()
    mock_brain.memory_manager = MagicMock()

    for i in range(5):
        with tempfile.TemporaryDirectory() as tmp_dir:
            r_dir = Path(tmp_dir) / "runtime"
            c = RuntimeController(brain=mock_brain, runtime_dir=r_dir)
            t0 = time.perf_counter()
            c.start(block=False)
            t1 = time.perf_counter()
            launch_times.append((t1 - t0) * 1000.0)

            t2 = time.perf_counter()
            c.stop()
            t3 = time.perf_counter()
            shutdown_times.append((t3 - t2) * 1000.0)

    avg_launch_ms = sum(launch_times) / len(launch_times)
    avg_shutdown_ms = sum(shutdown_times) / len(shutdown_times)
    print(f"Runtime Launch Time: avg {avg_launch_ms:.2f} ms (min: {min(launch_times):.2f} ms, max: {max(launch_times):.2f} ms)")
    print(f"Runtime Shutdown Time: avg {avg_shutdown_ms:.2f} ms (min: {min(shutdown_times):.2f} ms, max: {max(shutdown_times):.2f} ms)")

    # 3. GUI Initialization Time (Repeated 5x)
    gui_init_times = []
    for _ in range(5):
        mock_mgr = MagicMock()
        mock_mgr.is_running.return_value = False
        t0 = time.perf_counter()
        gui = GUIController(runtime_manager=mock_mgr)
        t1 = time.perf_counter()
        gui_init_times.append((t1 - t0) * 1000.0)
        gui.shutdown()

    avg_gui_init_ms = sum(gui_init_times) / len(gui_init_times)
    print(f"GUI Initialization Time: avg {avg_gui_init_ms:.2f} ms (min: {min(gui_init_times):.2f} ms, max: {max(gui_init_times):.2f} ms)")

    # 4. IPC Request Latency (Repeated 20x)
    with tempfile.TemporaryDirectory() as tmp_dir:
        r_dir = Path(tmp_dir) / "runtime"
        c = RuntimeController(brain=mock_brain, runtime_dir=r_dir)
        c.start(block=False)
        port = c.ipc_server.port
        token = c.session_token
        client = RuntimeClient(port=port, session_token=token)

        ipc_latencies = []
        for _ in range(20):
            t0 = time.perf_counter()
            resp = client.send_request("status")
            t1 = time.perf_counter()
            ipc_latencies.append((t1 - t0) * 1000.0)

        c.stop()

    avg_ipc_latency_ms = sum(ipc_latencies) / len(ipc_latencies)
    print(f"IPC Request Latency: avg {avg_ipc_latency_ms:.2f} ms (min: {min(ipc_latencies):.2f} ms, max: {max(ipc_latencies):.2f} ms)")

    # 5. Task Creation Latency (Repeated 100x)
    task_creation_times = []
    for i in range(100):
        t0 = time.perf_counter()
        steps = [
            TaskStep(order=1, tool_name="get_system_info"),
            TaskStep(order=2, tool_name="get_memory_usage"),
        ]
        task = Task(goal=f"Test benchmark task {i}", steps=steps)
        t1 = time.perf_counter()
        task_creation_times.append((t1 - t0) * 1000.0)

    avg_task_create_ms = sum(task_creation_times) / len(task_creation_times)
    print(f"Task Creation Latency: avg {avg_task_create_ms:.3f} ms (min: {min(task_creation_times):.3f} ms, max: {max(task_creation_times):.3f} ms)")

    # 6. Chat Request Latency (Local Fast-path / Mock Provider)
    brain = AIBrain()
    mock_provider = MagicMock()
    mock_provider.generate.return_value = MagicMock(content="Hello! How can I help you?", tool_calls=[])
    brain._provider = mock_provider

    chat_latencies = []
    for _ in range(20):
        t0 = time.perf_counter()
        resp = brain.process_user_message("hello")
        t1 = time.perf_counter()
        chat_latencies.append((t1 - t0) * 1000.0)

    avg_chat_ms = sum(chat_latencies) / len(chat_latencies)
    print(f"Chat Request Latency (Local): avg {avg_chat_ms:.2f} ms (min: {min(chat_latencies):.2f} ms, max: {max(chat_latencies):.2f} ms)")

    print("=" * 60)
    print("BENCHMARK COMPLETED SUCCESSFULLY")
    print("=" * 60)

    # Return structured results
    return {
        "environment": {
            "python": python_ver,
            "windows": windows_ver,
            "cpu": cpu_info,
            "cpu_cores": cpu_count,
            "ram_gb": round(total_ram_gb, 2),
            "version": charvis_ver,
        },
        "baseline": {
            "idle_cpu_percent": round(idle_cpu, 2),
            "idle_memory_mb": round(idle_mem_mb, 2),
            "threads_count": threads_count,
            "runtime_launch_ms": round(avg_launch_ms, 2),
            "runtime_shutdown_ms": round(avg_shutdown_ms, 2),
            "gui_init_ms": round(avg_gui_init_ms, 2),
            "ipc_latency_ms": round(avg_ipc_latency_ms, 2),
            "task_creation_ms": round(avg_task_create_ms, 3),
            "chat_latency_ms": round(avg_chat_ms, 2),
        }
    }


if __name__ == "__main__":
    results = run_benchmarks()
    # Write to a temporary json file for report integration
    with open("scratch/benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
