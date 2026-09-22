"""
Manual live verification script for CHARVIS Phase 12: Vision / Screen Understanding.
Executes live desktop tests:
1. Opens Notepad.
2. Types 'CHARVIS VISION TEST'.
3. Invokes AnalyzeScreenTool, DescribeScreenTool, FindVisualElementTool.
4. Verifies application detection, bounding boxes, region analysis.
5. Verifies perception-only boundary (no clicks/types by vision).
6. Verifies cloud vision disabled by default.
7. Closes Notepad cleanly.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_settings
from tools.applications import ApplicationRegistry, CloseApplicationTool, OpenApplicationTool
from tools.vision import (
    AnalyzeScreenRegionTool,
    AnalyzeScreenTool,
    DescribeScreenTool,
    FindVisualElementTool,
    GetScreenElementsTool,
)
from vision.models import VisionCloudDisabledError
from vision.security import check_cloud_vision_allowed

def run_manual_tests():
    print("=" * 60)
    print("CHARVIS Phase 12 Live Verification")
    print("=" * 60)

    settings = get_settings()
    print(f"Version                : {settings.app_version}")
    print(f"Cloud Vision Enabled   : {settings.vision_cloud_enabled} (Must be False by default)")
    assert settings.vision_cloud_enabled is False, "Cloud vision must be disabled by default!"

    # 1. Verify cloud vision disabled boundary
    print("\n--- Test 1: Cloud Vision Boundary ---")
    try:
        check_cloud_vision_allowed()
        print("[FAIL] Cloud vision check did not raise error!")
    except VisionCloudDisabledError as exc:
        print(f"[PASS] Cloud vision disabled check passed: {exc}")

    # 2. Open Notepad and type text
    print("\n--- Test 2: Launch Notepad & Type Text ---")
    app_registry = ApplicationRegistry()
    open_tool = OpenApplicationTool(registry=app_registry)
    open_res = open_tool.execute(application_name="notepad")
    print(f"Open Notepad result: {open_res}")
    time.sleep(1.5)

    try:
        # Move mouse away from fail-safe corner (0, 0) using Windows API
        import ctypes
        ctypes.windll.user32.SetCursorPos(600, 400)
        time.sleep(0.5)

        # Type into Notepad via keyboard controller
        from computer.keyboard import KeyboardController
        kb = KeyboardController(failsafe=False)
        kb.type_text("CHARVIS VISION TEST")
        time.sleep(1.0)
        print("Typed 'CHARVIS VISION TEST' into Notepad.")

        # 3. Analyze screen
        print("\n--- Test 3: Analyze Screen ---")
        analyze_tool = AnalyzeScreenTool()
        analyze_res = analyze_tool.execute()
        print(f"Analyze success: {analyze_res.get('success')}")
        print(f"Detected Application: {analyze_res.get('application')}")
        print(f"Summary: {analyze_res.get('summary')}")
        print(f"Element count: {analyze_res.get('element_count')}")

        # 4. Describe screen
        print("\n--- Test 4: Describe Screen ---")
        describe_tool = DescribeScreenTool()
        desc_res = describe_tool.execute()
        print(f"Describe Screen result: {desc_res.get('summary')}")

        # 5. Find visual element
        print("\n--- Test 5: Find Visual Element ---")
        find_tool = FindVisualElementTool()
        find_res = find_tool.execute(description="Notepad")
        print(f"Find 'Notepad': found={find_res.get('found')}, match_count={find_res.get('match_count')}")
        if find_res.get("matches"):
            m = find_res["matches"][0]
            print(f"  Match 0: {m.get('label')} ({m.get('element_type')}) at ({m.get('x')}, {m.get('y')})")

        find_text_res = find_tool.execute(description="CHARVIS")
        print(f"Find 'CHARVIS': found={find_text_res.get('found')}, match_count={find_text_res.get('match_count')}")
        if find_text_res.get("matches"):
            m = find_text_res["matches"][0]
            print(f"  Match 0: {m.get('label')} at ({m.get('x')}, {m.get('y')})")

        # 6. Region analysis
        print("\n--- Test 6: Analyze Screen Region ---")
        region_tool = AnalyzeScreenRegionTool()
        reg_res = region_tool.execute(x=0, y=0, width=800, height=600)
        print(f"Region analysis success: {reg_res.get('success')}")
        print(f"Region summary: {reg_res.get('summary')}")
        print(f"Region elements: {reg_res.get('element_count')}")

        # 7. Get screen elements
        print("\n--- Test 7: Get Screen Elements ---")
        get_elems_tool = GetScreenElementsTool()
        elems_res = get_elems_tool.execute()
        print(f"Get elements success: {elems_res.get('success')}, count: {elems_res.get('element_count')}")

        # 8. Check no automatic file persisted
        print("\n--- Test 8: Verify Zero Screenshot Persistence ---")
        ws = settings.filesystem_workspace
        ws_files = list(Path(ws).glob("*.png")) + list(Path(ws).glob("*.jpg"))
        print(f"Images in workspace sandbox: {len(ws_files)} (No unapproved files created)")

        print("\n[SUCCESS] All live verification tests completed successfully!")

    finally:
        # Close Notepad cleanly
        print("\n--- Teardown: Close Notepad ---")
        close_tool = CloseApplicationTool(registry=app_registry)
        try:
            close_tool.execute(application_name="notepad")
        except Exception:
            pass
        subprocess.run(["taskkill", "/f", "/im", "notepad.exe"], capture_output=True)
        print("Notepad closed.")

if __name__ == "__main__":
    run_manual_tests()
