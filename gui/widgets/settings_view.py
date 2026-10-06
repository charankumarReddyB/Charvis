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
        self._build_runtime_card()
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

    def _build_runtime_card(self) -> None:
        """Card for Phase 16 Background Runtime and Windows Startup controls."""
        card = self._create_section_card("CHARVIS Runtime")
        self.runtime_card = card

        status = self.controller.get_runtime_status()
        is_online = getattr(status, "state", "STOPPED").upper() == "RUNNING"
        status_text = "ONLINE" if is_online else "OFFLINE"
        status_color = ACCENT_SUCCESS if is_online else TEXT_MUTED

        # Status row
        s_row = tk.Frame(card, bg=CARD_BG)
        s_row.pack(fill=tk.X, pady=3)
        tk.Label(s_row, text="Status", font=FONT_MAIN, fg=TEXT_MUTED, bg=CARD_BG, width=26, anchor="w").pack(side=tk.LEFT)
        self.runtime_status_lbl = tk.Label(s_row, text=status_text, font=FONT_BOLD, fg=status_color, bg=CARD_BG, anchor="w")
        self.runtime_status_lbl.pack(side=tk.LEFT)

        pid_val = str(getattr(status, "process_id", None) or "N/A")
        self._add_row(card, "Process ID (PID)", pid_val)

        uptime_secs = getattr(status, "uptime", 0.0)
        m, s = divmod(int(uptime_secs), 60)
        h, m = divmod(m, 60)
        uptime_str = f"{h:02d}:{m:02d}:{s:02d}"
        self._add_row(card, "Uptime", uptime_str)

        # Subsystem Health
        h_frame = tk.Frame(card, bg=CARD_BG)
        h_frame.pack(fill=tk.X, pady=(8, 4))
        tk.Label(h_frame, text="Subsystem Health:", font=FONT_MAIN, fg=TEXT_MUTED, bg=CARD_BG).pack(anchor="w")

        health_info = self.controller.get_runtime_health()
        subsystems = health_info.get("subsystems", {})

        icons_row = tk.Frame(card, bg=CARD_BG)
        icons_row.pack(fill=tk.X, pady=(2, 8))
        for sub_name in ["core", "planner", "memory", "voice", "browser", "ipc"]:
            sub_st = subsystems.get(sub_name, {}).get("status", "ok")
            color = ACCENT_SUCCESS if sub_st == "ok" else (ACCENT_WARNING if sub_st in {"unavailable", "disabled"} else "#f23f43")
            sub_lbl = tk.Label(
                icons_row,
                text=f"● {sub_name.capitalize()}",
                font=FONT_SMALL,
                fg=color,
                bg=CARD_BG,
                padx=6,
            )
            sub_lbl.pack(side=tk.LEFT)

        # Runtime Controls
        btn_row = tk.Frame(card, bg=CARD_BG)
        btn_row.pack(fill=tk.X, pady=(8, 12))

        tk.Button(
            btn_row,
            text="Start",
            font=FONT_SMALL,
            bg=ACCENT_PRIMARY,
            fg=TEXT_MAIN,
            padx=12,
            pady=4,
            relief=tk.FLAT,
            command=self._on_start_runtime,
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_row,
            text="Stop",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_MAIN,
            padx=12,
            pady=4,
            relief=tk.RIDGE,
            command=self._on_stop_runtime,
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_row,
            text="Restart",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_MAIN,
            padx=12,
            pady=4,
            relief=tk.RIDGE,
            command=self._on_restart_runtime,
        ).pack(side=tk.LEFT)

        # Windows Startup Sub-Section
        sep = tk.Frame(card, height=1, bg=BORDER_COLOR)
        sep.pack(fill=tk.X, pady=(8, 10))

        tk.Label(
            card,
            text="Windows Startup Integration",
            font=FONT_BOLD,
            fg=ACCENT_SECONDARY,
            bg=CARD_BG,
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 6))

        startup_st = self.controller.get_startup_status()
        startup_enabled = startup_st.get("enabled", False)
        st_state_text = "[ON]" if startup_enabled else "[OFF]"
        st_color = ACCENT_SUCCESS if startup_enabled else TEXT_MUTED

        st_row = tk.Frame(card, bg=CARD_BG)
        st_row.pack(fill=tk.X, pady=3)
        tk.Label(st_row, text="Start with Windows:", font=FONT_MAIN, fg=TEXT_MUTED, bg=CARD_BG, width=26, anchor="w").pack(side=tk.LEFT)
        self.startup_state_lbl = tk.Label(st_row, text=st_state_text, font=FONT_BOLD, fg=st_color, bg=CARD_BG, anchor="w")
        self.startup_state_lbl.pack(side=tk.LEFT)

        st_btn_row = tk.Frame(card, bg=CARD_BG)
        st_btn_row.pack(fill=tk.X, pady=(6, 4))

        tk.Button(
            st_btn_row,
            text="Enable",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_MAIN,
            padx=10,
            pady=3,
            relief=tk.RIDGE,
            command=self._on_enable_startup,
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            st_btn_row,
            text="Disable",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_MAIN,
            padx=10,
            pady=3,
            relief=tk.RIDGE,
            command=self._on_disable_startup,
        ).pack(side=tk.LEFT)

    def _on_start_runtime(self) -> None:
        self.controller.start_runtime()
        self._refresh()

    def _on_stop_runtime(self) -> None:
        self.controller.stop_runtime()
        self._refresh()

    def _on_restart_runtime(self) -> None:
        self.controller.restart_runtime()
        self._refresh()

    def _on_enable_startup(self) -> None:
        self.controller.enable_startup()
        self._refresh()

    def _on_disable_startup(self) -> None:
        self.controller.disable_startup()
        self._refresh()

    def _build_system_overview_card(self) -> None:
        card = self._create_section_card("System Overview")
        self.status_container = card
        self._add_row(card, "Application Name", self.settings.app_name)
        self._add_row(card, "Version", f"v{self.settings.app_version} (Phase 16: Background Runtime & Startup)")
        self._add_row(card, "Environment", self.settings.environment)
        self._add_row(card, "Registered Tools", "75 Active Tools")
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
        # Redraw cards safely
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self._build_runtime_card()
        self._build_system_overview_card()
        self._build_brain_card()
        self._build_safety_card()
        self._build_ui_card()
