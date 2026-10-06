"""
Navigation sidebar widget for CHARVIS Desktop GUI (Phase 15).
Switches views without destroying or mutating underlying state.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Optional

from config import get_settings
from gui.models import AppView, SystemState
from gui.state import GUIState
from gui.controller import GUIController
from gui.theme import (
    ACCENT_BLUE,
    BORDER_COLOR,
    CARD_BG,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CAPTION,
    FONT_TITLE,
    SIDEBAR_BG,
    TEXT_DIM,
    TEXT_MAIN,
    TEXT_MUTED,
)
from gui.widgets.status import StatusWidget


class SidebarWidget(ttk.Frame):
    """
    Left-hand vertical navigation bar for switching views and viewing system connectivity.
    """

    def __init__(
        self,
        parent: tk.Widget,
        state: Optional[GUIState] = None,
        controller: Optional[GUIController] = None,
        on_view_change: Optional[Callable[[AppView], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, style="Sidebar.TFrame", width=kwargs.pop("width", 220), **kwargs)
        self.state = state
        self.controller = controller
        self.on_view_change = on_view_change or (lambda v: None)
        self.view_buttons: Dict[AppView, tk.Button] = {}
        self.current_active_view = AppView.CHAT

        self._build_ui()

        if self.state:
            self.state.subscribe(self._on_state_change)

    def _build_ui(self) -> None:
        settings = get_settings()

        # 1. App Header
        header_frame = tk.Frame(self, bg=SIDEBAR_BG)
        header_frame.pack(fill=tk.X, padx=16, pady=(18, 16))

        title_label = tk.Label(
            header_frame,
            text=settings.app_name,
            font=FONT_TITLE,
            bg=SIDEBAR_BG,
            fg=TEXT_MAIN,
        )
        title_label.pack(side=tk.LEFT)

        version_label = tk.Label(
            header_frame,
            text=f"v{settings.app_version}",
            font=FONT_CAPTION,
            bg=CARD_BG,
            fg=TEXT_MUTED,
            padx=6,
            pady=2,
        )
        version_label.pack(side=tk.RIGHT)

        # Divider
        divider = tk.Frame(self, height=1, bg=BORDER_COLOR)
        divider.pack(fill=tk.X, padx=14, pady=(0, 14))

        # 2. Nav Items
        nav_items = [
            (AppView.ASSISTANT, "🤖  Assistant"),
            (AppView.CHAT, "💬  Chat"),
            (AppView.TASKS, "📋  Tasks"),
            (AppView.MEMORY, "🧠  Memory"),
            (AppView.SETTINGS, "⚙  Settings"),
        ]

        for view, label in nav_items:
            btn = tk.Button(
                self,
                text=label,
                font=FONT_BODY_BOLD,
                anchor="w",
                bg=SIDEBAR_BG,
                fg=TEXT_MUTED,
                activebackground=CARD_BG,
                activeforeground=TEXT_MAIN,
                bd=0,
                padx=14,
                pady=10,
                cursor="hand2",
                command=lambda v=view: self._select_view(v),
            )
            btn.pack(fill=tk.X, padx=10, pady=3)
            self.view_buttons[view] = btn

        # 3. Bottom Status Area
        status_frame = tk.Frame(self, bg=SIDEBAR_BG)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=14, pady=16)

        status_divider = tk.Frame(self, height=1, bg=BORDER_COLOR)
        status_divider.pack(side=tk.BOTTOM, fill=tk.X, padx=14, pady=(0, 10))

        status_heading = tk.Label(
            status_frame,
            text="SYSTEM STATUS",
            font=("Segoe UI", 8, "bold"),
            bg=SIDEBAR_BG,
            fg=TEXT_DIM,
        )
        status_heading.pack(anchor="w", pady=(0, 4))

        self.status_widget = StatusWidget(status_frame, state=self.state)
        self.status_widget.pack(anchor="w")

        # Initial selection state
        self._highlight_active()

    def _select_view(self, view: AppView) -> None:
        """Handle user tab selection."""
        self.current_active_view = view
        self._highlight_active()
        if self.state:
            self.state.set_current_view(view)
        self.on_view_change(view)

    def set_active_view(self, view: AppView) -> None:
        """Programmatically update active tab display."""
        self.current_active_view = view
        self._highlight_active()

    def _highlight_active(self) -> None:
        """Update button colors to reflect currently selected view."""
        for view, btn in self.view_buttons.items():
            if view == self.current_active_view:
                btn.config(bg=CARD_BG, fg=TEXT_MAIN)
            else:
                btn.config(bg=SIDEBAR_BG, fg=TEXT_MUTED)

    def _on_state_change(self, state: GUIState) -> None:
        if state.current_view != self.current_active_view:
            self.set_active_view(state.current_view)

    def update_system_status(self, status: SystemState, message: str = "") -> None:
        """Forward status update to the nested StatusWidget."""
        self.status_widget.update_status(status, message)
