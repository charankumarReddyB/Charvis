"""
Status indicator widget for CHARVIS Desktop GUI (Phase 15).
Displays dual symbol and textual status representation.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from gui.models import STATE_DISPLAY_MAP, SystemState
from gui.theme import FONT_BODY_BOLD, FONT_CAPTION, PANEL_BG, TEXT_MUTED
from gui.state import GUIState


class StatusWidget(ttk.Frame):
    """
    Renders the active operational status of the CHARVIS system.
    Avoids relying on color alone by combining visual symbols, status labels, and descriptions.
    """

    def __init__(
        self,
        parent: tk.Widget,
        state: Optional[GUIState] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, style="TFrame", **kwargs)
        self.state = state

        self.symbol_label = tk.Label(
            self,
            text="●",
            font=("Segoe UI", 12),
            bg=PANEL_BG,
            fg="#23a55a",
        )
        self.symbol_label.pack(side=tk.LEFT, padx=(0, 6))

        self.text_label = ttk.Label(
            self,
            text="IDLE",
            font=FONT_BODY_BOLD,
        )
        self.text_label.pack(side=tk.LEFT)

        self.sub_label = ttk.Label(
            self,
            text="",
            style="Muted.TLabel",
        )
        self.sub_label.pack(side=tk.LEFT, padx=(10, 0))

        if self.state:
            self.state.subscribe(self._on_state_change)
            self.update_status(self.state.system_state, self.state.status_message)

    def _on_state_change(self, state: GUIState) -> None:
        self.update_status(state.system_state, state.status_message)

    def update_status(self, status: SystemState, message: str = "") -> None:
        """Update displayed symbol, status text, and descriptive subtitle."""
        info = STATE_DISPLAY_MAP.get(
            status,
            {"symbol": "●", "text": getattr(status, "value", str(status)).upper(), "color": TEXT_MUTED},
        )
        self.symbol_label.config(text=info["symbol"], fg=info["color"])
        self.text_label.config(text=info["text"])
        self.sub_label.config(text=message if message and message != info["text"] else "")
