"""
Unit tests for CHARVIS Vision Tools and Router Integration.
Phase 11: Screenshot & OCR.
"""

from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image
import pytest

from core.safety import RiskLevel, SafetyManager
from tools.registry import ToolRegistry
from tools.router import ToolRouter
from tools.vision import (
    AnalyzeScreenRegionTool,
    AnalyzeScreenTool,
    CaptureRegionTool,
    CaptureScreenTool,
    CaptureScreenshotTool,
    DescribeScreenTool,
    FindTextOnScreenTool,
    FindVisualElementTool,
    GetScreenElementsTool,
    ReadRegionTextTool,
    ReadScreenTextTool,
    SaveScreenshotTool,
    get_ocr_engine,
    get_screenshot_engine,
    get_vision_analyzer,
    set_ocr_engine,
    set_screenshot_engine,
    set_vision_analyzer,
)
from vision.analyzer import VisionAnalyzer
from vision.models import OCRTextBlock, ScreenDescription, ScreenElement
from vision.ocr import MockOCRProvider
from vision.providers import MockVisionProvider
from vision.screenshot import ScreenshotEngine


@pytest.fixture
def fake_image() -> Image.Image:
    return Image.new("RGB", (1280, 720), color="white")


@pytest.fixture
def mock_engine(fake_image: Image.Image) -> ScreenshotEngine:
    engine = ScreenshotEngine(grabber=lambda **k: fake_image)
    return engine


@pytest.fixture
def mock_ocr() -> MockOCRProvider:
    return MockOCRProvider(
        default_text="CHARVIS TEST 123",
        blocks=[
            OCRTextBlock("CHARVIS", 99.0, 100, 200, 80, 25),
            OCRTextBlock("TEST", 95.0, 190, 200, 50, 25),
            OCRTextBlock("123", 90.0, 250, 200, 40, 25),
        ],
    )


class TestVisionToolDefinitions:
    """Verify tool metadata, names, schemas, and risk levels."""

    def test_tool_risk_levels(self):
        assert CaptureScreenshotTool().risk_level == RiskLevel.SAFE
        assert CaptureScreenTool().risk_level == RiskLevel.SAFE
        assert CaptureRegionTool().risk_level == RiskLevel.SAFE
        assert SaveScreenshotTool().risk_level == RiskLevel.CONFIRMATION_REQUIRED
        assert ReadScreenTextTool().risk_level == RiskLevel.SAFE
        assert ReadRegionTextTool().risk_level == RiskLevel.SAFE
        assert FindTextOnScreenTool().risk_level == RiskLevel.SAFE
        assert AnalyzeScreenTool().risk_level == RiskLevel.SAFE
        assert AnalyzeScreenRegionTool().risk_level == RiskLevel.SAFE
        assert FindVisualElementTool().risk_level == RiskLevel.SAFE
        assert DescribeScreenTool().risk_level == RiskLevel.SAFE
        assert GetScreenElementsTool().risk_level == RiskLevel.SAFE

    def test_tool_names(self):
        assert CaptureScreenshotTool().name == "capture_screenshot"
        assert CaptureScreenTool().name == "capture_screen"
        assert CaptureRegionTool().name == "capture_region"
        assert SaveScreenshotTool().name == "save_screenshot"
        assert ReadScreenTextTool().name == "read_screen_text"
        assert ReadRegionTextTool().name == "read_region_text"
        assert FindTextOnScreenTool().name == "find_text_on_screen"
        assert AnalyzeScreenTool().name == "analyze_screen"
        assert AnalyzeScreenRegionTool().name == "analyze_screen_region"
        assert FindVisualElementTool().name == "find_visual_element"
        assert DescribeScreenTool().name == "describe_screen"
        assert GetScreenElementsTool().name == "get_screen_elements"


class TestCaptureTools:
    """Tests for capture_screenshot, capture_screen, capture_region."""

    def test_capture_screenshot_success(self, mock_engine: ScreenshotEngine):
        tool = CaptureScreenshotTool(engine=mock_engine)
        res = tool.execute()

        assert res["success"] is True
        assert res["metadata"]["width"] == 1280
        assert res["metadata"]["height"] == 720
        assert "Captured primary desktop" in res["message"]

    def test_capture_screen_valid(self, mock_engine: ScreenshotEngine):
        tool = CaptureScreenTool(engine=mock_engine)
        res = tool.execute(monitor=0)

        assert res["success"] is True
        assert res["metadata"]["monitor"] == 0

    def test_capture_screen_invalid_monitor(self, mock_engine: ScreenshotEngine):
        tool = CaptureScreenTool(engine=mock_engine)
        res = tool.execute(monitor=-1)

        assert res["success"] is False
        assert "Invalid monitor" in res["error"]

    def test_capture_region_valid(self, mock_engine: ScreenshotEngine):
        tool = CaptureRegionTool(engine=mock_engine)
        res = tool.execute(x=50, y=50, width=400, height=300)

        assert res["success"] is True
        assert res["region"]["width"] == 400
        assert res["region"]["height"] == 300

    def test_capture_region_invalid_coordinates(self, mock_engine: ScreenshotEngine):
        tool = CaptureRegionTool(engine=mock_engine)
        res = tool.execute(x=-10, y=0, width=100, height=100)

        assert res["success"] is False
        assert "Invalid region coordinates" in res["error"]


class TestSaveScreenshotTool:
    """Tests for save_screenshot tool."""

    def test_save_screenshot_to_sandbox(self, mock_engine: ScreenshotEngine, tmp_path: Path):
        tool = SaveScreenshotTool(engine=mock_engine, sandbox_root=tmp_path)

        res = tool.execute(filename="test_snap.png")
        assert res["success"] is True
        assert (tmp_path / "test_snap.png").exists()

    def test_save_screenshot_path_traversal_blocked(self, mock_engine: ScreenshotEngine, tmp_path: Path):
        tool = SaveScreenshotTool(engine=mock_engine, sandbox_root=tmp_path)

        res = tool.execute(filename="../escape.png")
        assert res["success"] is False
        assert "Security validation failed" in res["error"]


class TestReadScreenTextTools:
    """Tests for read_screen_text and read_region_text."""

    def test_read_screen_text(self, mock_engine: ScreenshotEngine, mock_ocr: MockOCRProvider):
        tool = ReadScreenTextTool(engine=mock_engine, ocr=mock_ocr)
        res = tool.execute()

        assert res["success"] is True
        assert res["full_text"] == "CHARVIS TEST 123"
        assert res["block_count"] == 3
        assert len(res["blocks"]) == 3

    def test_read_region_text(self, mock_engine: ScreenshotEngine, mock_ocr: MockOCRProvider):
        tool = ReadRegionTextTool(engine=mock_engine, ocr=mock_ocr)
        res = tool.execute(x=100, y=50, width=500, height=400)

        assert res["success"] is True
        assert res["region"]["x"] == 100
        # Check adjusted coordinates (offset by x=100, y=50)
        first_block = res["blocks"][0]
        assert first_block["x"] == 200  # 100 + 100
        assert first_block["y"] == 250  # 200 + 50


class TestFindTextOnScreenTool:
    """Tests for find_text_on_screen tool."""

    def test_find_exact_word(self, mock_engine: ScreenshotEngine, mock_ocr: MockOCRProvider):
        tool = FindTextOnScreenTool(engine=mock_engine, ocr=mock_ocr)
        res = tool.execute(text="TEST")

        assert res["success"] is True
        assert res["found"] is True
        assert res["match_count"] >= 1
        match = res["matches"][0]
        assert match["text"] == "TEST"
        assert match["x"] == 190
        assert match["y"] == 200

    def test_find_case_insensitive(self, mock_engine: ScreenshotEngine, mock_ocr: MockOCRProvider):
        tool = FindTextOnScreenTool(engine=mock_engine, ocr=mock_ocr)
        res = tool.execute(text="charvis")

        assert res["success"] is True
        assert res["found"] is True
        assert res["matches"][0]["text"] == "CHARVIS"

    def test_find_multi_word_phrase(self, mock_engine: ScreenshotEngine, mock_ocr: MockOCRProvider):
        tool = FindTextOnScreenTool(engine=mock_engine, ocr=mock_ocr)
        res = tool.execute(text="CHARVIS TEST")

        assert res["success"] is True
        assert res["found"] is True
        assert res["match_count"] >= 1
        phrase_match = [m for m in res["matches"] if m["text"] == "CHARVIS TEST"][0]
        assert phrase_match["x"] == 100
        assert phrase_match["y"] == 200
        assert phrase_match["width"] == 140  # 190+50 - 100

    def test_text_not_found(self, mock_engine: ScreenshotEngine, mock_ocr: MockOCRProvider):
        tool = FindTextOnScreenTool(engine=mock_engine, ocr=mock_ocr)
        res = tool.execute(text="NonExistentWordXYZ")

        assert res["success"] is True
        assert res["found"] is False
        assert res["match_count"] == 0
        assert "not found" in res["message"]


class TestVisionRouterIntegration:
    """Tests for ToolRouter routing of vision tools and SafetyManager enforcement."""

    def test_router_dispatches_safe_vision_tool(self, mock_engine: ScreenshotEngine):
        registry = ToolRegistry()
        registry.register(CaptureScreenshotTool(engine=mock_engine))
        router = ToolRouter(registry, SafetyManager())

        res = router.execute_tool("capture_screenshot", {})
        assert res.success is True
        assert res.data["metadata"]["width"] == 1280

    def test_router_enforces_confirmation_for_save_screenshot(self, mock_engine: ScreenshotEngine, tmp_path: Path):
        registry = ToolRegistry()
        registry.register(SaveScreenshotTool(engine=mock_engine, sandbox_root=tmp_path))
        router = ToolRouter(registry, SafetyManager())

        # Denied confirmation callback
        res_denied = router.execute_tool(
            "save_screenshot",
            {"filename": "snap.png"},
            confirmation_callback=lambda name, args, risk, msg=None: False,
        )
        assert res_denied.success is False
        assert "denied" in res_denied.error.lower()

        # Approved confirmation callback
        res_approved = router.execute_tool(
            "save_screenshot",
            {"filename": "snap.png"},
            confirmation_callback=lambda name, args, risk, msg=None: True,
        )
        assert res_approved.success is True
        assert (tmp_path / "snap.png").exists()


class TestPhase12VisionTools:
    """Tests for the 5 screen understanding tools in Phase 12."""

    @pytest.fixture
    def mock_analyzer(self, fake_image: Image.Image) -> VisionAnalyzer:
        mock_screenshot = ScreenshotEngine(grabber=lambda **k: fake_image)
        mock_ocr = MockOCRProvider(default_text="Notepad Save Cancel Settings")
        mock_desc = ScreenDescription(
            screen_width=1280,
            screen_height=720,
            application="Notepad",
            title="Untitled - Notepad",
            elements=[
                ScreenElement(
                    element_type="button",
                    label="Settings",
                    text="Settings",
                    confidence=0.95,
                    x=1100,
                    y=20,
                    width=40,
                    height=30,
                ),
                ScreenElement(
                    element_type="button",
                    label="Save",
                    text="Save",
                    confidence=0.90,
                    x=80,
                    y=50,
                    width=50,
                    height=25,
                ),
            ],
            summary="Notepad window active with Settings and Save buttons.",
            confidence=0.92,
        )
        mock_provider = MockVisionProvider(default_description=mock_desc)
        return VisionAnalyzer(
            screenshot_engine=mock_screenshot,
            ocr_provider=mock_ocr,
            vision_provider=mock_provider,
        )

    def test_analyze_screen_tool(self, mock_analyzer: VisionAnalyzer):
        tool = AnalyzeScreenTool(analyzer=mock_analyzer)
        res = tool.execute(context="what application is open")

        assert res["success"] is True
        assert res["application"] == "Notepad"
        assert res["element_count"] == 2
        assert "Notepad" in res["summary"]

    def test_analyze_screen_region_tool(self, mock_analyzer: VisionAnalyzer):
        tool = AnalyzeScreenRegionTool(analyzer=mock_analyzer)
        res = tool.execute(x=50, y=50, width=400, height=300)

        assert res["success"] is True
        assert res["region"]["width"] == 400
        assert res["element_count"] == 2

    def test_analyze_screen_region_tool_invalid_coords(self, mock_analyzer: VisionAnalyzer):
        tool = AnalyzeScreenRegionTool(analyzer=mock_analyzer)
        res = tool.execute(x=-10, y=50, width=400, height=300)

        assert res["success"] is False
        assert "Invalid region coordinates" in res["error"]

    def test_find_visual_element_tool(self, mock_analyzer: VisionAnalyzer):
        tool = FindVisualElementTool(analyzer=mock_analyzer)
        res = tool.execute(description="Settings")

        assert res["success"] is True
        assert res["found"] is True
        assert res["match_count"] >= 1
        assert res["matches"][0]["label"] == "Settings"
        assert res["matches"][0]["x"] == 1100

    def test_describe_screen_tool(self, mock_analyzer: VisionAnalyzer):
        tool = DescribeScreenTool(analyzer=mock_analyzer)
        res = tool.execute()

        assert res["success"] is True
        assert "Notepad" in res["summary"]
        assert "Settings" in res["summary"]

    def test_get_screen_elements_tool(self, mock_analyzer: VisionAnalyzer):
        tool = GetScreenElementsTool(analyzer=mock_analyzer)
        res = tool.execute()

        assert res["success"] is True
        assert res["element_count"] == 2
        assert len(res["elements"]) == 2

    def test_router_executes_phase12_tools_without_confirmation(self, mock_analyzer: VisionAnalyzer):
        registry = ToolRegistry()
        registry.register(AnalyzeScreenTool(analyzer=mock_analyzer))
        registry.register(FindVisualElementTool(analyzer=mock_analyzer))
        registry.register(DescribeScreenTool(analyzer=mock_analyzer))
        registry.register(GetScreenElementsTool(analyzer=mock_analyzer))
        router = ToolRouter(registry, SafetyManager())

        # Safe tools should execute immediately without needing confirmation callback
        res_analyze = router.execute_tool("analyze_screen", {})
        assert res_analyze.success is True

        res_find = router.execute_tool("find_visual_element", {"description": "Settings"})
        assert res_find.success is True
        assert res_find.data["found"] is True

        res_desc = router.execute_tool("describe_screen", {})
        assert res_desc.success is True

        res_elements = router.execute_tool("get_screen_elements", {})
        assert res_elements.success is True
        assert res_elements.data["element_count"] == 2

