"""
CHARVIS GUI — Desktop Application Main Window (CharvisApp)

Root window coordinator for CHARVIS Tkinter GUI:
- Dark theme styling and responsive layout
- View switching (Chat, Multi-step Tasks, Memory Explorer, Settings)
- Thread-safe queue polling for background worker updates
- Seamless safety confirmation dialog integration
- Graceful shutdown handling
"""

import sys
import queue
import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any, Callable

from config import get_settings
from gui.theme import apply_theme, BG_DARK, PANEL_BG, BORDER_COLOR
from gui.models import AppView, ConfirmationRequest
from gui.state import GUIState
from gui.controller import GUIController
from gui.widgets.sidebar import SidebarWidget
from gui.widgets.chat import ChatViewWidget
from gui.widgets.task_panel import TaskPanelWidget
from gui.widgets.memory_view import MemoryViewWidget
from gui.widgets.settings_view import SettingsViewWidget
from gui.widgets.confirmation import ConfirmationDialog

logger = logging.getLogger("charvis.gui")


class CharvisApp:
    """
    Main CHARVIS Desktop Application.
    """

    def __init__(self, root: Optional[tk.Tk] = None):
        self.settings = get_settings()
        self._owns_root = root is None
        self.root = root or tk.Tk()

        # Thread-safe UI dispatch queue
        self._ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()

        # Core State & Controller
        self.state = GUIState()
        self.controller = GUIController(
            state=self.state,
            ui_dispatcher=self.dispatch_ui,
        )

        # Active dialog tracker
        self._active_dialog: Optional[ConfirmationDialog] = None

        # Setup GUI
        self._setup_window()
        self._build_layout()

        # Register state listener for view switching & confirmation dialogs
        self.state.subscribe(self._on_state_change)

        # Start queue polling
        self._poll_queue()

        # Handle window close protocol
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_window(self) -> None:
        self.root.title(self.settings.gui_window_title)
        w = self.settings.gui_window_width
        h = self.settings.gui_window_height
        self.root.minsize(840, 520)

        # Center on primary screen
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            pos_x = max(0, (sw - w) // 2)
            pos_y = max(0, (sh - h) // 2)
            self.root.geometry(f"{w}x{h}+{pos_x}+{pos_y}")
        except Exception:
            self.root.geometry(f"{w}x{h}")

        self.root.configure(bg=BG_DARK)
        apply_theme(self.root)

    def _build_layout(self) -> None:
        # Main shell container
        self.shell = tk.Frame(self.root, bg=BG_DARK)
        self.shell.pack(fill=tk.BOTH, expand=True)

        # Left Sidebar
        self.sidebar = SidebarWidget(
            self.shell,
            state=self.state,
            controller=self.controller,
            on_view_change=self.switch_view,
            width=230,
        )
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)

        # Border separator
        self.separator = tk.Frame(self.shell, bg=BORDER_COLOR, width=1)
        self.separator.pack(side=tk.LEFT, fill=tk.Y)

        # Right Content View Deck
        self.deck = tk.Frame(self.shell, bg=BG_DARK)
        self.deck.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Initialize Views
        self.views: Dict[AppView, tk.Widget] = {
            AppView.CHAT: ChatViewWidget(
                self.deck,
                state=self.state,
                controller=self.controller,
                on_voice_requested=self._on_voice_requested,
            ),
            AppView.TASKS: TaskPanelWidget(
                self.deck,
                state=self.state,
                controller=self.controller,
            ),
            AppView.MEMORY: MemoryViewWidget(
                self.deck,
                state=self.state,
                controller=self.controller,
            ),
            AppView.SETTINGS: SettingsViewWidget(
                self.deck,
                state=self.state,
                controller=self.controller,
            ),
        }

        # Pack initial view
        self._current_view_widget: Optional[tk.Widget] = None
        self.switch_view(self.state.current_view)

    def switch_view(self, view: AppView) -> None:
        """Switch the visible view in the view deck."""
        if self._current_view_widget is not None:
            self._current_view_widget.pack_forget()

        target_widget = self.views.get(view)
        if target_widget:
            target_widget.pack(fill=tk.BOTH, expand=True)
            self._current_view_widget = target_widget
            self.state.set_current_view(view)

    def _on_voice_requested(self) -> None:
        """User clicked voice input button."""
        self.controller.start_voice_input()

    def dispatch_ui(self, callback: Callable[[], None]) -> None:
        """
        Thread-safe dispatch from background worker threads to the Tkinter event loop.
        """
        self._ui_queue.put(callback)

    def _poll_queue(self) -> None:
        """Process all queued UI callbacks on the main thread."""
        while not self._ui_queue.empty():
            try:
                callback = self._ui_queue.get_nowait()
                callback()
            except queue.Empty:
                break
            except Exception as err:
                logger.error("Error executing queued UI callback: %s", err, exc_info=True)

        poll_ms = max(20, self.settings.gui_poll_interval_ms)
        try:
            self.root.after(poll_ms, self._poll_queue)
        except Exception:
            pass  # Window being closed

    def _on_state_change(self, state: GUIState) -> None:
        """Handle global state transitions, such as confirmation requests."""
        # Handle pending confirmation modal
        if state.pending_confirmation and self._active_dialog is None:
            self._show_confirmation_dialog(state.pending_confirmation)
        elif not state.pending_confirmation and self._active_dialog is not None:
            try:
                self._active_dialog.destroy()
            except Exception:
                pass
            self._active_dialog = None

    def _show_confirmation_dialog(self, request: ConfirmationRequest) -> None:
        """Display the modal security confirmation dialog."""
        try:
            dialog = ConfirmationDialog(self.root, request)
            self._active_dialog = dialog
            dialog.wait_window()
        except Exception as err:
            logger.error("Error showing confirmation dialog: %s", err)
            request.deny()
        finally:
            self._active_dialog = None
            self.state.clear_confirmation()

    def on_close(self) -> None:
        """Clean shutdown when closing the desktop window."""
        try:
            self.controller.shutdown()
        except Exception as err:
            logger.warning("Error during controller shutdown: %s", err)

        if self._owns_root:
            try:
                self.root.destroy()
            except Exception:
                pass

    def run(self) -> None:
        """Start the Tkinter event loop."""
        self.root.mainloop()
