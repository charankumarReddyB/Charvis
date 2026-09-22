"""
CHARVIS GUI — Settings View Widget

System configuration, status overview, and environment inspection.
Read-only display that strictly masks secrets and credentials.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, Any

from gui.theme import (
    BG_DARK, PANEL_BG, CARD_BG, INPUT_BG,
    TEXT_MAIN, TEXT_MUTED, TEXT_HINT,
    ACCENT_PRIMARY, ACCENT_SECONDARY, ACCENT_SUCCESS, ACCENT_WARNING,
    BORDER_COLOR, FONT_MAIN, FONT_BOLD, FONT_CODE, FONT_SMALL, FONT_TITLE
)
from gui.state import GUIState
from gui.controller import GUIController
from config import get_settings


class SettingsViewWidget(tk.Frame):
    """
    Read-only settings and system diagnosis dashboard.
    """

    def __init__(
        self,
        parent: tk.Widget,
        state: GUIState,
        controller: GUIController,
        **kwargs
    ):
        super().__init__(parent, bg=BG_DARK, **kwargs)
        self.state = state
        self.controller = controller
        self.settings = get_settings()

        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        # Header / Action bar
        self.header_frame = tk.Frame(self, bg=PANEL_BG, height=44, padx=16, pady=8)
        self.header_frame.pack(side=tk.TOP, fill=tk.X)

        self.title_label = tk.Label(
            self.header_frame,
            text="Settings & System Status",
            font=FONT_BOLD,
            fg=TEXT_MAIN,
            bg=PANEL_BG,
        )
        self.title_label.pack(side=tk.LEFT)

        self.refresh_btn = tk.Button(
            self.header_frame,
            text="Refresh Status",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=CARD_BG,
            activebackground=PANEL_BG,
            activeforeground=TEXT_MAIN,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._refresh,
        )
        self.refresh_btn.pack(side=tk.RIGHT)

        # Scrollable container for setting cards
        self.scroll_canvas = tk.Canvas(self, bg=BG_DARK, bd=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.scroll_canvas.yview)
        self.scroll_frame = tk.Frame(self.scroll_canvas, bg=BG_DARK)

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
        )
        self.scroll_canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=16, pady=16)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Build setting sections
        self._build_system_overview_card()
        self._build_brain_card()
        self._build_safety_card()
        self._build_ui_card()

    def _create_section_card(self, title: str) -> tk.Frame:
        card = tk.Frame(self.scroll_frame, bg=CARD_BG, padx=16, pady=14)
        card.pack(fill=tk.X, pady=(0, 14))

        tk.Label(
            card,
            text=title,
            font=FONT_BOLD,
            fg=ACCENT_PRIMARY,
            bg=CARD_BG,
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 10))

        return card

    def _add_row(self, parent: tk.Widget, label: str, value: str, is_masked: bool = False) -> None:
        row = tk.Frame(parent, bg=CARD_BG)
        row.pack(fill=tk.X, pady=3)

        tk.Label(
            row,
            text=label,
            font=FONT_MAIN,
            fg=TEXT_MUTED,
            bg=CARD_BG,
            width=26,
            anchor="w",
        ).pack(side=tk.LEFT)

        display_val = "••••••••••••••••" if is_masked and value else value
        val_fg = TEXT_HINT if is_masked else TEXT_MAIN

        tk.Label(
            row,
            text=display_val,
            font=FONT_CODE if is_masked else FONT_MAIN,
            fg=val_fg,
            bg=CARD_BG,
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _build_system_overview_card(self) -> None:
        card = self._create_section_card("System Overview")
        self.status_container = card
        self._add_row(card, "Application Name", self.settings.app_name)
        self._add_row(card, "Version", f"v{self.settings.app_version} (Phase 15: Desktop GUI)")
        self._add_row(card, "Environment", self.settings.environment)
        self._add_row(card, "Registered Tools", "68 Active Tools")
        self._add_row(card, "Operating System", "Windows (NT)")

    def _build_brain_card(self) -> None:
        card = self._create_section_card("AI Brain & LLM")
        self._add_row(card, "Provider", self.settings.ai_provider.upper())
        self._add_row(card, "Active Model", self.settings.ai_model)
        self._add_row(card, "API Key Configured", "Yes" if self.settings.is_api_key_configured else "No (Mock / Not configured)")
        self._add_row(card, "API Key (Masked)", self.settings.openai_api_key or "", is_masked=True)

    def _build_safety_card(self) -> None:
        card = self._create_section_card("Safety & Permissions")
        self._add_row(card, "Confirmation Mode", "GUI Modal Interactive")
        self._add_row(card, "Dangerous Operations", "Strict SafetyManager Enforcement")
        self._add_row(card, "Audit Logging", "Active (logs/charvis.log)")

    def _build_ui_card(self) -> None:
        card = self._create_section_card("Desktop GUI Configuration")
        self._add_row(card, "Theme", self.settings.gui_theme.capitalize())
        self._add_row(card, "Window Dimensions", f"{self.settings.gui_window_width} x {self.settings.gui_window_height}")
        self._add_row(card, "Poll Interval", f"{self.settings.gui_poll_interval_ms} ms")
        self._add_row(card, "Framework", "Tkinter + ttk (Native)")

    def _refresh(self) -> None:
        status_info = self.controller.get_system_status()
        # Can refresh any dynamic metrics if needed
