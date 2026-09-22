"""CHARVIS Browser Automation Tools.

Provides 10 controlled browser automation tools for web navigation, element interaction,
page inspection, and session management with strict security guardrails.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.safety import RiskLevel
from logger import get_logger
from tools.base import BaseTool
from tools.schemas import ToolParameter, ToolSchema
from browser.controller import BrowserController
from browser.models import BrowserError, BrowserSecurityError, BrowserTimeoutError
from browser.security import (
    classify_click_risk,
    is_sensitive_input,
    sanitize_sensitive_value,
    validate_browser_url,
)

logger = get_logger(__name__)

# Global shared BrowserController instance
_ACTIVE_BROWSER: Optional[BrowserController] = None


def get_browser_controller() -> BrowserController:
    """Retrieve or create the active singleton BrowserController instance."""
    global _ACTIVE_BROWSER
    if _ACTIVE_BROWSER is None:
        _ACTIVE_BROWSER = BrowserController()
    return _ACTIVE_BROWSER


def set_browser_controller(controller: Optional[BrowserController]) -> None:
    """Explicitly configure the active BrowserController (useful for testing/mocking)."""
    global _ACTIVE_BROWSER
    _ACTIVE_BROWSER = controller


class OpenBrowserTool(BaseTool):
    """Tool to start the CHARVIS-controlled browser session."""

    def __init__(self, controller: Optional[BrowserController] = None) -> None:
        self._controller = controller

    @property
    def name(self) -> str:
        return "open_browser"

    @property
    def description(self) -> str:
        return (
            "Start the CHARVIS-controlled browser session using an isolated profile. "
            "Reuses the session if already active."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        ctrl = self._controller or get_browser_controller()
        try:
            ctrl.start()
            return {
                "success": True,
                "message": "Controlled browser session is active.",
                "url": ctrl.current_url(),
            }
        except Exception as err:
            return {"success": False, "error": f"Failed to start browser: {err}"}


class NavigateBrowserTool(BaseTool):
    """Tool to navigate the browser to a validated HTTP or HTTPS URL."""

    def __init__(self, controller: Optional[BrowserController] = None) -> None:
        self._controller = controller

    @property
    def name(self) -> str:
        return "navigate_browser"

    @property
    def description(self) -> str:
        return (
            "Navigate the controlled browser to a destination URL. "
            "Strictly accepts 'http://' and 'https://' URLs. Rejects 'file://', "
            "'javascript:', 'data:', and local file navigation."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="url",
                    param_type="string",
                    description="The destination webpage URL (e.g. 'https://example.com')",
                    required=True,
                )
            ],
        )

    def execute(self, url: str, **kwargs: Any) -> Dict[str, Any]:
        ctrl = self._controller or get_browser_controller()
        try:
            validated_url = validate_browser_url(url)
            page_info = ctrl.open_url(validated_url)
            return {
                "success": True,
                "url": page_info.url,
                "title": page_info.title,
                "visible_text_preview": page_info.visible_text[:300] if page_info.visible_text else "",
            }
        except (BrowserSecurityError, BrowserTimeoutError, BrowserError) as err:
            return {"success": False, "error": str(err)}
        except Exception as err:
            return {"success": False, "error": f"Navigation failed: {err}"}


class GetPageInfoTool(BaseTool):
    """Tool to inspect current URL, title, and bounded visible page text."""

    def __init__(self, controller: Optional[BrowserController] = None) -> None:
        self._controller = controller

    @property
    def name(self) -> str:
        return "get_page_info"

    @property
    def description(self) -> str:
        return (
            "Retrieve current page information including URL, page title, and "
            "a bounded summary of visible human-readable text on the page."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        ctrl = self._controller or get_browser_controller()
        if not ctrl.is_running():
            return {
                "success": False,
                "error": "Browser session is not running. Call open_browser first.",
            }
        page_info = ctrl.get_page_info()
        return {
            "success": True,
            "url": page_info.url,
            "title": page_info.title,
            "visible_text": page_info.visible_text,
        }


class ClickElementTool(BaseTool):
    """Tool to click a page element identified by selector or accessible name."""

    def __init__(self, controller: Optional[BrowserController] = None) -> None:
        self._controller = controller

    @property
    def name(self) -> str:
        return "click_element"

    @property
    def description(self) -> str:
        return (
            "Click a webpage element using a CSS selector or accessible text locator. "
            "Actions matching purchases, checkouts, payments, bookings, or data deletion "
            "automatically require human confirmation."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    def get_risk_level(self, arguments: Dict[str, Any]) -> RiskLevel:
        selector = str(arguments.get("selector", ""))
        return classify_click_risk(selector)

    def get_confirmation_message(self, arguments: Dict[str, Any]) -> str:
        selector = arguments.get("selector", "")
        ctrl = self._controller or get_browser_controller()
        domain = ctrl.current_url()
        return f"Clicking high-impact target '{selector}' on {domain} may trigger an external transaction, message, or deletion."

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="selector",
                    param_type="string",
                    description="CSS selector, text locator (e.g. 'text=Submit'), or ID of element to click",
                    required=True,
                )
            ],
        )

    def execute(self, selector: str, **kwargs: Any) -> Dict[str, Any]:
        ctrl = self._controller or get_browser_controller()
        if not ctrl.is_running():
            return {"success": False, "error": "Browser is not running."}
        try:
            ctrl.click(selector)
            return {"success": True, "message": f"Clicked element '{selector}'."}
        except Exception as err:
            return {"success": False, "error": str(err)}


class TypeIntoElementTool(BaseTool):
    """Tool to type text into an input field or text area on the web page."""

    def __init__(self, controller: Optional[BrowserController] = None) -> None:
        self._controller = controller

    @property
    def name(self) -> str:
        return "type_into_element"

    @property
    def description(self) -> str:
        return (
            "Type text into a webpage form field. Sensitive fields (passwords, OTPs, "
            "credit cards, CVVs, tokens) require confirmation and are redacted in outputs."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    def get_risk_level(self, arguments: Dict[str, Any]) -> RiskLevel:
        selector = str(arguments.get("selector", ""))
        if is_sensitive_input(selector):
            return RiskLevel.CONFIRMATION_REQUIRED
        return RiskLevel.SAFE

    def get_confirmation_message(self, arguments: Dict[str, Any]) -> str:
        selector = arguments.get("selector", "")
        ctrl = self._controller or get_browser_controller()
        return f"Entering sensitive information into '{selector}' on {ctrl.current_url()}."

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="selector",
                    param_type="string",
                    description="CSS selector or locator for the input element",
                    required=True,
                ),
                ToolParameter(
                    name="text",
                    param_type="string",
                    description="Text value to enter into the field",
                    required=True,
                ),
            ],
        )

    def execute(self, selector: str, text: str, **kwargs: Any) -> Dict[str, Any]:
        ctrl = self._controller or get_browser_controller()
        if not ctrl.is_running():
            return {"success": False, "error": "Browser is not running."}

        is_sensitive = is_sensitive_input(selector)
        display_text = sanitize_sensitive_value(text) if is_sensitive else text

        try:
            ctrl.type_text(selector, text)
            return {
                "success": True,
                "message": f"Entered text into '{selector}'.",
                "value": display_text,
            }
        except Exception as err:
            return {"success": False, "error": str(err)}


class GoBackTool(BaseTool):
    """Tool to navigate back in browser history."""

    def __init__(self, controller: Optional[BrowserController] = None) -> None:
        self._controller = controller

    @property
    def name(self) -> str:
        return "go_back"

    @property
    def description(self) -> str:
        return "Navigate backward to the previous page in the browser history."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(name=self.name, description=self.description, parameters=[])

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        ctrl = self._controller or get_browser_controller()
        if not ctrl.is_running():
            return {"success": False, "error": "Browser is not running."}
        success = ctrl.go_back()
        return {
            "success": success,
            "current_url": ctrl.current_url(),
            "message": "Navigated back." if success else "Could not navigate back.",
        }


class GoForwardTool(BaseTool):
    """Tool to navigate forward in browser history."""

    def __init__(self, controller: Optional[BrowserController] = None) -> None:
        self._controller = controller

    @property
    def name(self) -> str:
        return "go_forward"

    @property
    def description(self) -> str:
        return "Navigate forward to the next page in the browser history."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(name=self.name, description=self.description, parameters=[])

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        ctrl = self._controller or get_browser_controller()
        if not ctrl.is_running():
            return {"success": False, "error": "Browser is not running."}
        success = ctrl.go_forward()
        return {
            "success": success,
            "current_url": ctrl.current_url(),
            "message": "Navigated forward." if success else "Could not navigate forward.",
        }


class ReloadPageTool(BaseTool):
    """Tool to reload/refresh the current page."""

    def __init__(self, controller: Optional[BrowserController] = None) -> None:
        self._controller = controller

    @property
    def name(self) -> str:
        return "reload_page"

    @property
    def description(self) -> str:
        return "Reload/refresh the current browser page."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(name=self.name, description=self.description, parameters=[])

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        ctrl = self._controller or get_browser_controller()
        if not ctrl.is_running():
            return {"success": False, "error": "Browser is not running."}
        success = ctrl.reload()
        return {
            "success": success,
            "current_url": ctrl.current_url(),
            "message": "Page reloaded." if success else "Could not reload page.",
        }


class GetCurrentUrlTool(BaseTool):
    """Tool to query current active page URL."""

    def __init__(self, controller: Optional[BrowserController] = None) -> None:
        self._controller = controller

    @property
    def name(self) -> str:
        return "get_current_url"

    @property
    def description(self) -> str:
        return "Retrieve the current active browser webpage URL."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(name=self.name, description=self.description, parameters=[])

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        ctrl = self._controller or get_browser_controller()
        if not ctrl.is_running():
            return {"success": False, "error": "Browser is not running."}
        return {"success": True, "url": ctrl.current_url()}


class CloseBrowserTool(BaseTool):
    """Tool to close the CHARVIS-controlled browser session."""

    def __init__(self, controller: Optional[BrowserController] = None) -> None:
        self._controller = controller

    @property
    def name(self) -> str:
        return "close_browser"

    @property
    def description(self) -> str:
        return "Close the active CHARVIS-controlled browser session."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(name=self.name, description=self.description, parameters=[])

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        ctrl = self._controller or get_browser_controller()
        if not ctrl.is_running():
            return {"success": True, "message": "Browser session was already stopped."}
        ctrl.stop()
        return {"success": True, "message": "Controlled browser session closed."}
