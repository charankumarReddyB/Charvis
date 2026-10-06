"""
Unit tests for browser controller lifecycle and leak prevention (Phase 17).
"""

from unittest.mock import MagicMock
import pytest
from browser.controller import BrowserController


def test_browser_controller_lifecycle_mocked():
    """Verify BrowserController properly closes pages and browser contexts."""
    controller = BrowserController()

    mock_page = MagicMock()
    mock_context = MagicMock()
    mock_browser = MagicMock()

    controller._current_page = mock_page
    controller._context = mock_context
    controller._browser = mock_browser
    controller._is_running = True

    controller.close()

    assert mock_page.close.called
    assert mock_context.close.called
    assert mock_browser.close.called
    assert not controller._is_running
    assert controller._current_page is None


def test_browser_controller_idempotent_close():
    """Verify calling close() multiple times is safe and idempotent."""
    controller = BrowserController()
    controller._is_running = False

    # Calling close on already stopped controller should not raise
    controller.close()
    controller.close()
