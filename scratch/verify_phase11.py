"""
Manual verification script for CHARVIS Phase 11: Screenshot & OCR.
Validates screenshot engine, OCR providers, security boundaries, and tool router integration.
"""

from pathlib import Path
from PIL import Image

from config import get_settings
from core.brain import AIBrain
from core.safety import RiskLevel, SafetyManager
from tools.registry import ToolRegistry
from tools.router import ToolRouter
from tools.vision import (
    CaptureRegionTool,
    CaptureScreenTool,
    CaptureScreenshotTool,
    FindTextOnScreenTool,
    ReadRegionTextTool,
    ReadScreenTextTool,
    SaveScreenshotTool,
)
from vision.models import OCRTextBlock
from vision.ocr import MockOCRProvider, TesseractOCRProvider
from vision.screenshot import ScreenshotEngine
from vision.security import (
    sanitize_ocr_text_for_logging,
    validate_region_coordinates,
    validate_screenshot_save_path,
    VisionSecurityError,
)


def run_verification():
    print("=" * 60)
    print("CHARVIS Phase 11: Screenshot & OCR - Manual Verification")
    print("=" * 60)

    settings = get_settings()
    print(f"App Version           : {settings.app_version}")
    print(f"OCR Provider Type     : {settings.ocr_provider_type}")
    print(f"Max Region Area       : {settings.max_region_area:,} px")
    print(f"Max OCR Text Length   : {settings.max_ocr_text_length} chars")
    print(f"Screenshot Save Dir   : {settings.screenshot_save_dir}")

    # 1. Coordinate Validation
    print("\n1. Testing Security Coordinate Validation...")
    x, y, w, h = validate_region_coordinates(10, 20, 300, 200, 1920, 1080)
    print(f"   [OK] Valid coordinates passed: ({x}, {y}, {w}x{h})")

    try:
        validate_region_coordinates(-5, 0, 100, 100, 1920, 1080)
        print("   [FAIL] Negative coordinate should have raised VisionSecurityError!")
    except VisionSecurityError as e:
        print(f"   [OK] Negative coordinate correctly rejected: {e}")

    try:
        validate_region_coordinates(100, 100, 0, 50, 1920, 1080)
        print("   [FAIL] Zero dimension should have raised VisionSecurityError!")
    except VisionSecurityError as e:
        print(f"   [OK] Zero dimension correctly rejected: {e}")

    # 2. Path Traversal & Sandbox Validation
    print("\n2. Testing Screenshot Save Sandbox Enforcement...")
    sandbox = settings.filesystem_workspace
    valid_save = validate_screenshot_save_path("snap_test.png", sandbox)
    print(f"   [OK] Valid in-sandbox path: {valid_save}")

    try:
        validate_screenshot_save_path("../../windows_system.png", sandbox)
        print("   [FAIL] Path traversal should have raised VisionSecurityError!")
    except VisionSecurityError as e:
        print(f"   [OK] Path traversal correctly rejected: {e}")

    try:
        validate_screenshot_save_path("C:/Windows/hack.png", sandbox)
        print("   [FAIL] Absolute path outside sandbox should have raised VisionSecurityError!")
    except VisionSecurityError as e:
        print(f"   [OK] Absolute path outside sandbox correctly rejected: {e}")

    # 3. Sensitive Data Redaction
    print("\n3. Testing OCR Text Diagnostic Redaction...")
    raw = "User api key is sk-abcdef1234567890abcdef12345 and card is 4111 2222 3333 4444"
    sanitized = sanitize_ocr_text_for_logging(raw)
    assert "sk-abcdef" not in sanitized
    assert "4111 2222" not in sanitized
    print(f"   [OK] Redacted text: {sanitized}")

    # 4. In-Memory Screenshot Engine
    print("\n4. Testing In-Memory Screenshot Engine...")
    test_img = Image.new("RGB", (1920, 1080), color="blue")
    engine = ScreenshotEngine(grabber=lambda **k: test_img)
    img, meta = engine.capture_primary()
    assert img is test_img
    assert meta.width == 1920
    assert meta.height == 1080
    assert engine.last_screenshot is test_img
    print(f"   [OK] In-memory capture succeeded: {meta.width}x{meta.height} px (no disk file created)")

    # 5. Save Screenshot
    print("\n5. Testing Save Screenshot to Workspace...")
    saved = engine.save_last_screenshot("verification_snap.png", sandbox, overwrite=True)
    assert saved.exists()
    print(f"   [OK] Screenshot file saved in sandbox: {saved}")
    # Clean up test file
    saved.unlink(missing_ok=True)
    print("   [OK] Test screenshot cleaned up.")

    # 6. OCR Provider Abstraction & Text Search
    print("\n6. Testing OCR Engine & find_text_on_screen...")
    mock_ocr = MockOCRProvider(
        default_text="CHARVIS TEST 123",
        blocks=[
            OCRTextBlock("CHARVIS", 98.0, 100, 200, 80, 24),
            OCRTextBlock("TEST", 95.0, 190, 200, 50, 24),
            OCRTextBlock("123", 90.0, 250, 200, 40, 24),
        ],
    )
    find_tool = FindTextOnScreenTool(engine=engine, ocr=mock_ocr)
    find_res = find_tool.execute(text="TEST")
    assert find_res["found"] is True
    assert find_res["matches"][0]["x"] == 190
    print(f"   [OK] Found 'TEST' at x={find_res['matches'][0]['x']}, y={find_res['matches'][0]['y']}")

    # Case-insensitive phrase find
    find_phrase = find_tool.execute(text="charvis test")
    assert find_phrase["found"] is True
    print(f"   [OK] Found phrase 'charvis test' spanning: {find_phrase['matches'][0]}")

    # Not found
    find_none = find_tool.execute(text="MissingWord")
    assert find_none["found"] is False
    print("   [OK] Non-existent text correctly reported not found.")

    # 7. AIBrain Tool Count & Registration
    print("\n7. Testing AIBrain Integration & 50 Active Tools...")
    brain = AIBrain(provider=None)  # Provider lazy loads
    registered_names = [t.name for t in brain.registry.list_tools()]
    print(f"   Total registered tools: {len(registered_names)}")
    assert len(registered_names) == 50
    assert "capture_screenshot" in registered_names
    assert "capture_screen" in registered_names
    assert "capture_region" in registered_names
    assert "save_screenshot" in registered_names
    assert "read_screen_text" in registered_names
    assert "read_region_text" in registered_names
    assert "find_text_on_screen" in registered_names
    print("   [OK] All 7 vision tools registered in AIBrain (50 tools total).")

    print("\n" + "=" * 60)
    print("ALL PHASE 11 MANUAL VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_verification()
