"""Tests for Browser Automation Tools (Phase 10).

Verifies tool metadata, schema definitions, dynamic risk classification,
sensitive field masking, confirmation enforcement via SafetyManager, and ToolRouter integration.
"""

from unittest.mock import MagicMock
import pytest

from core.brain import AIBrain
from core.safety import RiskLevel, SafetyManager
from tools.browser import (
    ClickElementTool,
    CloseBrowserTool,
    GetCurrentUrlTool,
    GetPageInfoTool,
    GoBackTool,
    GoForwardTool,
    NavigateBrowserTool,
    OpenBrowserTool,
    ReloadPageTool,
    TypeIntoElementTool,
    set_browser_controller,
)
from tools.registry import ToolRegistry
from tools.router import ToolRouter
from browser.controller import BrowserController
from browser.models import PageInfo


@pytest.fixture
def mock_browser_controller():
    """Create a mock BrowserController."""
    ctrl = MagicMock(spec=BrowserController)
    ctrl.is_running.return_value = True
    ctrl.current_url.return_value = "https://example.com/checkout"
    ctrl.page_title.return_value = "Checkout Page"
    ctrl.get_page_info.return_value = PageInfo(
        url="https://example.com/checkout",
        title="Checkout Page",
        visible_text="Review your order before proceeding.",
    )
    ctrl.open_url.return_value = PageInfo(
        url="https://example.com",
        title="Example Domain",
        visible_text="Example Domain Content",
    )
    ctrl.click.return_value = True
    ctrl.type_text.return_value = True
    ctrl.go_back.return_value = True
    ctrl.go_forward.return_value = True
    ctrl.reload.return_value = True
    return ctrl


@pytest.fixture(autouse=True)
def cleanup_active_browser():
    """Reset shared browser controller after each test."""
    yield
    set_browser_controller(None)


def test_browser_tools_registration_in_brain() -> None:
    """Verify all 10 browser tools are properly registered in AIBrain."""
    brain = AIBrain()
    expected_tools = [
        "open_browser",
        "navigate_browser",
        "get_page_info",
        "click_element",
        "type_into_element",
        "go_back",
        "go_forward",
        "reload_page",
        "get_current_url",
        "close_browser",
    ]
    tool_names = [t.name for t in brain.registry.list_tools()]
    for name in expected_tools:
        assert name in tool_names, f"Tool '{name}' missing from AIBrain registry"


def test_open_browser_tool(mock_browser_controller) -> None:
    """Verify OpenBrowserTool execution."""
    tool = OpenBrowserTool(controller=mock_browser_controller)
    assert tool.name == "open_browser"
    assert tool.risk_level == RiskLevel.SAFE

    result = tool.execute()
    assert result["success"] is True
    mock_browser_controller.start.assert_called_once()


def test_navigate_browser_tool_valid_and_invalid(mock_browser_controller) -> None:
    """Verify NavigateBrowserTool validates URL and executes."""
    tool = NavigateBrowserTool(controller=mock_browser_controller)
    assert tool.name == "navigate_browser"
    assert tool.risk_level == RiskLevel.SAFE

    # Valid HTTPS URL
    res_valid = tool.execute(url="https://example.com")
    assert res_valid["success"] is True
    assert res_valid["url"] == "https://example.com"

    # Blocked local file URL
    res_invalid = tool.execute(url="file:///C:/Windows/System32/cmd.exe")
    assert res_invalid["success"] is False
    assert "prohibited" in res_invalid["error"].lower()


def test_get_page_info_tool(mock_browser_controller) -> None:
    """Verify GetPageInfoTool returns page details."""
    tool = GetPageInfoTool(controller=mock_browser_controller)
    result = tool.execute()
    assert result["success"] is True
    assert result["url"] == "https://example.com/checkout"
    assert result["title"] == "Checkout Page"
    assert "Review your order" in result["visible_text"]


def test_click_element_dynamic_risk_and_confirmation(mock_browser_controller) -> None:
    """CRITICAL SECURITY: Verify ordinary clicks are SAFE while high-impact actions require confirmation."""
    tool = ClickElementTool(controller=mock_browser_controller)

    # Ordinary link click -> SAFE
    assert tool.get_risk_level({"selector": "a.nav-link"}) == RiskLevel.SAFE

    # Purchase button click -> CONFIRMATION_REQUIRED
    assert tool.get_risk_level({"selector": "button#purchase-now"}) == RiskLevel.CONFIRMATION_REQUIRED
    assert tool.get_risk_level({"selector": "#submit-payment"}) == RiskLevel.CONFIRMATION_REQUIRED
    assert tool.get_risk_level({"selector": "button.delete-account"}) == RiskLevel.CONFIRMATION_REQUIRED

    confirm_msg = tool.get_confirmation_message({"selector": "button#purchase-now"})
    assert "purchase-now" in confirm_msg
    assert "transaction" in confirm_msg.lower() or "external" in confirm_msg.lower()


def test_type_into_element_sensitive_detection_and_redaction(mock_browser_controller) -> None:
    """CRITICAL PRIVACY: Verify sensitive typing requires confirmation and masks value in results."""
    tool = TypeIntoElementTool(controller=mock_browser_controller)

    # Ordinary search typing -> SAFE
    assert tool.get_risk_level({"selector": "input#search"}) == RiskLevel.SAFE
    res_ordinary = tool.execute(selector="input#search", text="weather in San Francisco")
    assert res_ordinary["success"] is True
    assert res_ordinary["value"] == "weather in San Francisco"

    # Sensitive password typing -> CONFIRMATION_REQUIRED and REDACTED
    assert tool.get_risk_level({"selector": "input#user_password"}) == RiskLevel.CONFIRMATION_REQUIRED
    res_sensitive = tool.execute(selector="input#user_password", text="MySecretPassword123")
    assert res_sensitive["success"] is True
    # Plaintext secret MUST NOT be present in tool output
    assert res_sensitive["value"] == "***REDACTED***"
    assert "MySecretPassword123" not in str(res_sensitive)


def test_safety_manager_blocks_denied_sensitive_action(mock_browser_controller) -> None:
    """CRITICAL SECURITY: Verify SafetyManager halts execution when confirmation is denied."""
    registry = ToolRegistry()
    safety = SafetyManager()
    router = ToolRouter(registry=registry, safety_manager=safety)

    tool = ClickElementTool(controller=mock_browser_controller)
    registry.register(tool)

    # User denies confirmation
    denying_callback = MagicMock(return_value=False)

    result = router.execute_tool(
        tool_name="click_element",
        arguments={"selector": "button#purchase-now"},
        confirmation_callback=denying_callback,
    )

    assert result.success is False
    assert "denied" in result.error.lower()
    # Browser click MUST NOT have been called
    assert mock_browser_controller.click.call_count == 0


def test_history_and_reload_tools(mock_browser_controller) -> None:
    """Verify go_back, go_forward, reload_page, and get_current_url tools."""
    back_tool = GoBackTool(controller=mock_browser_controller)
    assert back_tool.execute()["success"] is True

    fwd_tool = GoForwardTool(controller=mock_browser_controller)
    assert fwd_tool.execute()["success"] is True

    reload_tool = ReloadPageTool(controller=mock_browser_controller)
    assert reload_tool.execute()["success"] is True

    url_tool = GetCurrentUrlTool(controller=mock_browser_controller)
    assert url_tool.execute()["url"] == "https://example.com/checkout"


def test_close_browser_tool(mock_browser_controller) -> None:
    """Verify CloseBrowserTool calls controller stop."""
    tool = CloseBrowserTool(controller=mock_browser_controller)
    result = tool.execute()
    assert result["success"] is True
    mock_browser_controller.stop.assert_called_once()
