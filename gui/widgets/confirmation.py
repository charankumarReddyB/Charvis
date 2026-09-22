"""
CHARVIS GUI — Security Confirmation Dialog

Modal confirmation dialog invoked when a tool operation requires human approval
as enforced by the SafetyManager.
Provides clear risk level badges, parameter inspectability, and explicit Confirm / Deny actions.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from gui.theme import (
    BG_DARK, PANEL_BG, CARD_BG, INPUT_BG,
    TEXT_MAIN, TEXT_MUTED, TEXT_HINT,
    ACCENT_PRIMARY, ACCENT_SECONDARY, ACCENT_SUCCESS, ACCENT_WARNING, ACCENT_DANGER,
    BORDER_COLOR, FONT_MAIN, FONT_BOLD, FONT_CODE, FONT_SMALL, FONT_TITLE
)
from gui.models import ConfirmationRequest


class ConfirmationDialog(tk.Toplevel):
    """
    Modal security confirmation popup for sensitive tool actions.
    """

    def __init__(self, parent: tk.Widget, request: ConfirmationRequest):
        super().__init__(parent)
        self.request = request

        self.title("CHARVIS Security Confirmation")
        self.geometry("520x400")
        self.resizable(False, False)
        self.configure(bg=BG_DARK)

        # Make modal
        self.transient(parent)
        self.grab_set()

        self._center_window(parent)
        self._build_ui()

        # Handle window close (X button) as cancellation/deny
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _center_window(self, parent: tk.Widget) -> None:
        self.update_idletasks()
        try:
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()

            dialog_w = 520
            dialog_h = 400

            pos_x = parent_x + (parent_w - dialog_w) // 2
            pos_y = parent_y + (parent_h - dialog_h) // 2
            self.geometry(f"{dialog_w}x{dialog_h}+{pos_x}+{pos_y}")
        except Exception:
            pass

    def _build_ui(self) -> None:
        # Header banner
        header = tk.Frame(self, bg=PANEL_BG, padx=20, pady=16)
        header.pack(side=tk.TOP, fill=tk.X)

        title_label = tk.Label(
            header,
            text="⚠️ Security Confirmation Required",
            font=FONT_TITLE,
            fg=ACCENT_WARNING,
            bg=PANEL_BG,
        )
        title_label.pack(anchor="w")

        subtitle = tk.Label(
            header,
            text="The assistant is requesting permission to execute an action.",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=PANEL_BG,
        )
        subtitle.pack(anchor="w", pady=(4, 0))

        # Main details container
        body = tk.Frame(self, bg=BG_DARK, padx=20, pady=16)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Tool name and risk badge
        meta_row = tk.Frame(body, bg=BG_DARK)
        meta_row.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            meta_row,
            text="Tool:",
            font=FONT_BOLD,
            fg=TEXT_MUTED,
            bg=BG_DARK,
        ).pack(side=tk.LEFT)

        tk.Label(
            meta_row,
            text=f" {self.request.tool_name}",
            font=FONT_BOLD,
            fg=TEXT_MAIN,
            bg=BG_DARK,
        ).pack(side=tk.LEFT)

        # Risk badge
        risk = self.request.risk_level.upper()
        risk_color = ACCENT_DANGER if risk in ("HIGH", "CRITICAL") else (ACCENT_WARNING if risk == "MEDIUM" else ACCENT_SUCCESS)

        badge = tk.Label(
            meta_row,
            text=f" {risk} RISK ",
            font=FONT_SMALL,
            fg="#ffffff",
            bg=risk_color,
            padx=6,
            pady=2,
        )
        badge.pack(side=tk.RIGHT)

        # Message / Details
        msg_box = tk.Label(
            body,
            text=self.request.message or "Please confirm whether you want to authorize this operation.",
            font=FONT_MAIN,
            fg=TEXT_MAIN,
            bg=CARD_BG,
            justify=tk.LEFT,
            wraplength=470,
            padx=12,
            pady=10,
        )
        msg_box.pack(fill=tk.X, pady=(0, 10))

        # Parameters / Arguments inspection box
        tk.Label(
            body,
            text="Parameters:",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_DARK,
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))

        param_frame = tk.Frame(body, bg=CARD_BG)
        param_frame.pack(fill=tk.BOTH, expand=True)

        param_scroll = ttk.Scrollbar(param_frame, orient=tk.VERTICAL)
        param_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        param_text = tk.Text(
            param_frame,
            bg=CARD_BG,
            fg=TEXT_MAIN,
            font=FONT_CODE,
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=8,
            wrap=tk.WORD,
            yscrollcommand=param_scroll.set,
        )
        param_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        param_scroll.config(command=param_text.yview)

        # Filter out potential secret keys from inspection view for safety
        clean_params = {}
        for k, v in self.request.arguments.items():
            if any(secret_term in k.lower() for secret_term in ("key", "token", "password", "secret")):
                clean_params[k] = "******** [REDACTED]"
            else:
                clean_params[k] = v

        import json
        try:
            formatted_params = json.dumps(clean_params, indent=2, default=str)
        except Exception:
            formatted_params = str(clean_params)

        param_text.insert(tk.END, formatted_params)
        param_text.config(state=tk.DISABLED)

        # Action Buttons
        button_row = tk.Frame(self, bg=PANEL_BG, padx=20, pady=12)
        button_row.pack(side=tk.BOTTOM, fill=tk.X)

        cancel_btn = tk.Button(
            button_row,
            text="Cancel / Deny",
            font=FONT_BOLD,
            fg="#ffffff",
            bg=ACCENT_DANGER,
            activebackground="#b91c1c",
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._on_cancel,
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(8, 0))

        confirm_btn = tk.Button(
            button_row,
            text="Confirm / Allow",
            font=FONT_BOLD,
            fg="#ffffff",
            bg=ACCENT_SUCCESS,
            activebackground="#15803d",
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._on_confirm,
        )
        confirm_btn.pack(side=tk.RIGHT)

    def _on_confirm(self) -> None:
        self.request.approve()
        self.grab_release()
        self.destroy()

    def _on_cancel(self) -> None:
        self.request.deny()
        self.grab_release()
        self.destroy()
