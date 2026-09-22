"""Tests for BrowserController Subsystem (Phase 10).

Verifies controller lifecycle (start/stop/reuse), navigation, locators, bounded visible text,
timeout errors, download protection, and absence of raw JS execution capabilities.
"""

from unittest.mock import MagicMock, patch
import pytest

from browser.controller import BrowserController
from browser.models import (
    BrowserError,
    BrowserSecurityError,
    BrowserTimeoutError,
    PageInfo,
)


@pytest.fixture
def mock_controller(tmp_path):
    """Create a BrowserController with mocked Playwright internals."""
    ctrl = BrowserController(user_data_dir=tmp_path / "test_profile", headless=True)

    # Mock internal Playwright objects
    mock_page = MagicMock()
    mock_page.url = "https://example.com"
    mock_page.title.return_value = "Example Domain"
    mock_page.inner_text.return_value = "This domain is for use in illustrative examples in documents."

    mock_context = MagicMock()
    mock_context.pages = [mock_page]

    mock_playwright = MagicMock()
    mock_playwright.chromium.launch_persistent_context.return_value = mock_context

    ctrl._playwright = mock_playwright
    ctrl._context = mock_context
    ctrl._page = mock_page
    ctrl._is_running = True

    return ctrl


def test_browser_controller_initial_state(tmp_path) -> None:
    """Verify clean initial state before start() is called."""
    ctrl = BrowserController(user_data_dir=tmp_path / "profile")
    assert ctrl.is_running() is False
    assert ctrl.current_url() == ""
    assert ctrl.page_title() == ""
    assert ctrl.get_visible_text() == ""


def test_browser_controller_start_and_stop_lifecycle(tmp_path) -> None:
    """Verify start() launches Playwright and stop() cleans up resources."""
    with patch("playwright.sync_api.sync_playwright") as mock_pw_init:
        mock_driver = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_context.pages = [mock_page]
        mock_driver.chromium.launch_persistent_context.return_value = mock_context
        mock_pw_init.return_value.start.return_value = mock_driver

        ctrl = BrowserController(user_data_dir=tmp_path / "profile", headless=True)
        assert ctrl.is_running() is False

        ctrl.start()
        assert ctrl.is_running() is True
        mock_driver.chromium.launch_persistent_context.assert_called_once()

        # Session reuse: calling start again does not relaunch
        ctrl.start()
        assert mock_driver.chromium.launch_persistent_context.call_count == 1

        ctrl.stop()
        assert ctrl.is_running() is False
        mock_page.close.assert_called_once()
        mock_context.close.assert_called_once()
        mock_driver.stop.assert_called_once()


def test_browser_open_url_success(mock_controller) -> None:
    """Verify open_url validates URL, calls page.goto, and returns PageInfo."""
    info = mock_controller.open_url("https://example.com")
    assert isinstance(info, PageInfo)
    assert info.url == "https://example.com"
    assert info.title == "Example Domain"
    assert "illustrative examples" in info.visible_text
    mock_controller._page.goto.assert_called_once()


def test_browser_open_url_rejects_disallowed_schemes(mock_controller) -> None:
    """CRITICAL SECURITY: Verify open_url rejects file:// and javascript: before reaching Playwright."""
    with pytest.raises(BrowserSecurityError):
        mock_controller.open_url("file:///etc/hosts")

    with pytest.raises(BrowserSecurityError):
        mock_controller.open_url("javascript:void(0)")

    # Playwright goto must never have been called
    assert mock_controller._page.goto.call_count == 0


def test_browser_navigation_timeout(mock_controller) -> None:
    """Verify navigation timeout raises BrowserTimeoutError."""
    mock_controller._page.goto.side_effect = Exception("Timeout 30000ms exceeded while navigating")

    with pytest.raises(BrowserTimeoutError, match="timed out"):
        mock_controller.open_url("https://example.com/slow")


def test_visible_text_length_limit(mock_controller) -> None:
    """Verify visible page text is bounded and truncated to prevent context overflow."""
    long_text = "word " * 2000  # 10,000 characters
    mock_controller._page.inner_text.return_value = long_text

    result = mock_controller.get_visible_text(max_length=500)
    assert len(result) <= 600
    assert "[Content truncated]" in result


def test_click_handling(mock_controller) -> None:
    """Verify click targets the locator and handles empty selectors."""
    # Empty selector rejected
    with pytest.raises(BrowserError, match="cannot be empty"):
        mock_controller.click("")

    # Valid click
    assert mock_controller.click("button#submit") is True
    mock_controller._page.locator.assert_called_with("button#submit")


def test_typing_handling(mock_controller) -> None:
    """Verify type_text calls fill on locator and rejects empty selectors."""
    with pytest.raises(BrowserError, match="cannot be empty"):
        mock_controller.type_text("", "sample text")

    assert mock_controller.type_text("input#search", "Hello CHARVIS") is True
    mock_controller._page.locator.assert_called_with("input#search")


def test_history_navigation_and_reload(mock_controller) -> None:
    """Verify go_back, go_forward, and reload invoke page methods."""
    assert mock_controller.go_back() is True
    mock_controller._page.go_back.assert_called_once()

    assert mock_controller.go_forward() is True
    mock_controller._page.go_forward.assert_called_once()

    assert mock_controller.reload() is True
    mock_controller._page.reload.assert_called_once()


def test_take_screenshot(mock_controller) -> None:
    """Verify take_screenshot captures browser viewport bytes."""
    mock_controller._page.screenshot.return_value = b"\x89PNGmockbytes"
    data = mock_controller.take_screenshot()
    assert data == b"\x89PNGmockbytes"
    mock_controller._page.screenshot.assert_called_once()


def test_download_cancellation_handler(mock_controller) -> None:
    """CRITICAL SECURITY: Verify download events are cancelled."""
    mock_download = MagicMock()
    mock_controller._handle_blocked_download(mock_download)
    mock_download.cancel.assert_called_once()


def test_no_arbitrary_javascript_execution_methods() -> None:
    """CRITICAL SECURITY: Verify BrowserController provides NO evaluate_javascript or run_js methods."""
    ctrl = BrowserController()
    assert not hasattr(ctrl, "evaluate_javascript")
    assert not hasattr(ctrl, "execute_script")
    assert not hasattr(ctrl, "run_js")
    assert not hasattr(ctrl, "eval")


def test_no_credential_or_cookie_harvesting_methods() -> None:
    """CRITICAL PRIVACY: Verify BrowserController provides NO cookie scraping or credential export methods."""
    ctrl = BrowserController()
    assert not hasattr(ctrl, "get_cookies")
    assert not hasattr(ctrl, "extract_credentials")
    assert not hasattr(ctrl, "dump_session")
