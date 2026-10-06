"""CHARVIS Browser Controller Layer.

Manages the Playwright Chromium browser lifecycle, persistent profile context,
page navigation, safe element interaction, and download blocking.
"""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any, Dict, Optional

from config import Settings, get_settings
from logger import get_logger
from browser.models import (
    BrowserError,
    BrowserNotRunningError,
    BrowserSecurityError,
    BrowserTimeoutError,
    PageInfo,
)
from browser.security import validate_browser_url

logger = get_logger(__name__)


class BrowserController:
    """Controls an isolated, persistent Playwright Chromium browser instance."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        user_data_dir: Optional[Path] = None,
        headless: Optional[bool] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.user_data_dir = (
            Path(user_data_dir) if user_data_dir else self.settings.browser_user_data_dir
        )
        self.headless = (
            headless if headless is not None else self.settings.browser_headless
        )

        self._playwright: Optional[object] = None
        self._context: Optional[object] = None
        self._page: Optional[object] = None
        self._is_running: bool = False

    def is_running(self) -> bool:
        """Return True if the browser session is active and responsive."""
        return self._is_running and self._page is not None

    def start(self) -> None:
        """Launch the persistent browser context and initialize the primary page."""
        if self.is_running():
            logger.debug("Browser is already running; reusing active session.")
            return

        logger.info(
            "Starting controlled browser (profile: %s, headless: %s)",
            self.user_data_dir,
            self.headless,
        )

        try:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()

            # Ensure profile directory exists
            self.user_data_dir.mkdir(parents=True, exist_ok=True)

            nav_timeout_ms = int(self.settings.browser_navigation_timeout * 1000)
            action_timeout_ms = int(self.settings.browser_action_timeout * 1000)

            # Launch persistent Chromium context with download rejection
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=self.headless,
                accept_downloads=False,
                viewport={"width": 1280, "height": 800},
            )

            # Cancel any downloads that might be triggered
            self._context.on("download", lambda download: self._handle_blocked_download(download))

            # Set default timeouts
            self._context.set_default_navigation_timeout(nav_timeout_ms)
            self._context.set_default_timeout(action_timeout_ms)

            # Reuse or create primary page
            pages = self._context.pages
            if pages:
                self._page = pages[0]
            else:
                self._page = self._context.new_page()

            self._is_running = True
            logger.info("Controlled browser session started successfully.")

        except ImportError as err:
            self.stop()
            raise BrowserError(
                f"Playwright is not installed or available in this environment: {err}"
            ) from err
        except Exception as err:
            self.stop()
            logger.exception("Failed to start browser instance: %s", err)
            raise BrowserError(f"Could not launch controlled browser: {err}") from err

    def _handle_blocked_download(self, download: object) -> None:
        """Safely cancel and log blocked download events."""
        try:
            logger.warning("Download event intercepted and blocked for security.")
            if hasattr(download, "cancel"):
                download.cancel()
        except Exception as err:
            logger.debug("Error while cancelling download: %s", err)

    @property
    def _current_page(self) -> Optional[object]:
        return self._page

    @_current_page.setter
    def _current_page(self, val: Optional[object]) -> None:
        self._page = val

    def close(self) -> None:
        """Alias for stop() to support standard lifecycle closing."""
        self.stop()

    def stop(self) -> None:
        """Close page, context, and Playwright driver resources."""
        logger.info("Stopping controlled browser session.")
        try:
            if self._page is not None:
                try:
                    self._page.close()
                except Exception:
                    pass
                self._page = None

            if self._context is not None:
                try:
                    self._context.close()
                except Exception:
                    pass
                self._context = None

            if hasattr(self, "_browser") and getattr(self, "_browser") is not None:
                try:
                    self._browser.close()
                except Exception:
                    pass
                self._browser = None

            if self._playwright is not None:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None

        finally:
            self._is_running = False
            logger.info("Browser session stopped cleanly.")

    def _ensure_active(self) -> object:
        """Ensure the browser is running and return the active page."""
        if not self.is_running() or self._page is None:
            self.start()
        return self._page

    def open_url(self, url: str) -> PageInfo:
        """Validate destination URL and navigate the browser page.

        Args:
            url: Destination URL (must be http:// or https://).

        Returns:
            PageInfo: Updated page status and visible content.

        Raises:
            BrowserSecurityError: If URL scheme is disallowed.
            BrowserTimeoutError: If page load times out.
            BrowserError: On general navigation failure.
        """
        validated_url = validate_browser_url(url)
        page = self._ensure_active()

        logger.info("Navigating browser to: '%s'", validated_url)
        try:
            response = page.goto(
                validated_url,
                wait_until="domcontentloaded",
                timeout=int(self.settings.browser_navigation_timeout * 1000),
            )

            # Check if navigation redirected to an unsupported scheme
            current = page.url
            validate_browser_url(current, allow_about_blank=True)

            status_code = response.status if response else None
            return self.get_page_info(status_code=status_code)

        except BrowserSecurityError:
            raise
        except Exception as err:
            err_str = str(err).lower()
            if "timeout" in err_str:
                logger.error("Navigation timeout reached for '%s'", validated_url)
                raise BrowserTimeoutError(f"Navigation to '{validated_url}' timed out.") from err
            logger.error("Navigation failure for '%s': %s", validated_url, err)
            raise BrowserError(f"Failed to navigate to '{validated_url}': {err}") from err

    def current_url(self) -> str:
        """Return the current active page URL."""
        if not self.is_running() or self._page is None:
            return ""
        return str(self._page.url)

    def page_title(self) -> str:
        """Return the current page title."""
        if not self.is_running() or self._page is None:
            return ""
        try:
            return str(self._page.title())
        except Exception:
            return ""

    def get_visible_text(self, max_length: Optional[int] = None) -> str:
        """Extract rendered visible page text, bounded to prevent context overflow."""
        limit = max_length or self.settings.browser_page_text_limit
        if not self.is_running() or self._page is None:
            return ""

        try:
            # inner_text on body captures human-visible text without script/style tags
            raw_text = self._page.inner_text("body")
            if not raw_text:
                return ""
            # Normalize whitespace
            cleaned = " ".join(raw_text.split())
            if len(cleaned) > limit:
                return cleaned[:limit] + " ... [Content truncated]"
            return cleaned
        except Exception as err:
            logger.debug("Could not extract body text: %s", err)
            return ""

    def get_page_info(self, status_code: Optional[int] = None) -> PageInfo:
        """Capture a snapshot of the current page state."""
        return PageInfo(
            url=self.current_url(),
            title=self.page_title(),
            visible_text=self.get_visible_text(),
            status_code=status_code,
        )

    def click(self, selector: str) -> bool:
        """Click a webpage element identified by selector or accessible text."""
        if not selector or not selector.strip():
            raise BrowserError("Selector cannot be empty.")

        page = self._ensure_active()
        clean_selector = selector.strip()
        logger.info("Clicking element: '%s'", clean_selector)

        try:
            locator = page.locator(clean_selector).first
            locator.click(timeout=int(self.settings.browser_action_timeout * 1000))
            return True
        except Exception as err:
            err_str = str(err).lower()
            if "timeout" in err_str:
                raise BrowserTimeoutError(f"Timeout clicking element '{clean_selector}'.") from err
            raise BrowserError(f"Failed to click element '{clean_selector}': {err}") from err

    def type_text(self, selector: str, text: str, clear_first: bool = True) -> bool:
        """Type text into a webpage form field."""
        if not selector or not selector.strip():
            raise BrowserError("Selector cannot be empty.")

        page = self._ensure_active()
        clean_selector = selector.strip()

        try:
            locator = page.locator(clean_selector).first
            if clear_first:
                locator.fill(text, timeout=int(self.settings.browser_action_timeout * 1000))
            else:
                locator.type(text, timeout=int(self.settings.browser_action_timeout * 1000))
            return True
        except Exception as err:
            err_str = str(err).lower()
            if "timeout" in err_str:
                raise BrowserTimeoutError(f"Timeout typing into element '{clean_selector}'.") from err
            raise BrowserError(f"Failed to type into element '{clean_selector}': {err}") from err

    def go_back(self) -> bool:
        """Navigate back in the browser history."""
        page = self._ensure_active()
        try:
            page.go_back(wait_until="domcontentloaded")
            return True
        except Exception as err:
            logger.warning("Browser go_back failed: %s", err)
            return False

    def go_forward(self) -> bool:
        """Navigate forward in the browser history."""
        page = self._ensure_active()
        try:
            page.go_forward(wait_until="domcontentloaded")
            return True
        except Exception as err:
            logger.warning("Browser go_forward failed: %s", err)
            return False

    def reload(self) -> bool:
        """Reload the current webpage."""
        page = self._ensure_active()
        try:
            page.reload(wait_until="domcontentloaded")
            return True
        except Exception as err:
            logger.warning("Browser reload failed: %s", err)
            return False

    def take_screenshot(self, path: Optional[str] = None) -> bytes:
        """Capture a controlled screenshot of the active browser viewport only.

        Note: Confined strictly to the browser viewport; does NOT capture the desktop.
        """
        page = self._ensure_active()
        try:
            screenshot_bytes = page.screenshot(path=path)
            return screenshot_bytes
        except Exception as err:
            raise BrowserError(f"Failed to capture browser screenshot: {err}") from err
