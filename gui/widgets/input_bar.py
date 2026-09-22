"""
Input bar widget for CHARVIS Desktop GUI (Phase 15).
Provides multiline input, Send, Enter/Shift+Enter shortcuts, and voice capture button.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from gui.theme import (
    ACCENT_BLUE,
    ACCENT_HOVER,
    BORDER_COLOR,
    CARD_BG,
    COLOR_WARNING,
    FONT_BODY,
    FONT_BODY_BOLD,
    INPUT_BG,
    PANEL_BG,
    TEXT_DIM,
    TEXT_MAIN,
    TEXT_MUTED,
)


class InputBarWidget(ttk.Frame):
    """
    Bottom message input container supporting multiline editing, Send, and Voice commands.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_send: Callable[[str], None],
        on_voice: Optional[Callable[[], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, style="Input.TFrame", **kwargs)
        self.on_send = on_send
        self.on_voice = on_voice or (lambda: None)
        self._disabled = False

        self._build_ui()

    def _build_ui(self) -> None:
        # Container frame with border
        input_container = tk.Frame(
            self,
            bg=INPUT_BG,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            bd=0,
        )
        input_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=(8, 14))

        # 1. Multiline Text Input
        self.text_input = tk.Text(
            input_container,
            height=3,
            wrap=tk.WORD,
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            insertbackground=TEXT_MAIN,
            font=FONT_BODY,
            bd=0,
            padx=10,
            pady=8,
            relief="flat",
        )
        self.text_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Keybindings
        self.text_input.bind("<Return>", self._on_enter_pressed)
        self.text_input.bind("<Shift-Return>", self._on_shift_enter_pressed)

        # 2. Action buttons container (right side of input box)
        btn_box = tk.Frame(input_container, bg=INPUT_BG)
        btn_box.pack(side=tk.RIGHT, fill=tk.Y, padx=8, pady=8)

        # Microphone Button
        self.voice_btn = tk.Button(
            btn_box,
            text="🎤 Voice",
            font=FONT_BODY_BOLD,
            bg=CARD_BG,
            fg=TEXT_MUTED,
            activebackground=ACCENT_BLUE,
            activeforeground="#ffffff",
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._handle_voice,
        )
        self.voice_btn.pack(side=tk.LEFT, padx=(0, 6))

        # Send Button
        self.send_btn = tk.Button(
            btn_box,
            text="Send",
            font=FONT_BODY_BOLD,
            bg=ACCENT_BLUE,
            fg="#ffffff",
            activebackground=ACCENT_HOVER,
            activeforeground="#ffffff",
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._handle_send,
        )
        self.send_btn.pack(side=tk.LEFT)

    def _on_enter_pressed(self, event: tk.Event) -> str:
        """Send message on Return key."""
        if not (event.state & 0x0001):  # Shift not held
            self._handle_send()
            return "break"  # Prevent inserting newline
        return ""

    def _on_shift_enter_pressed(self, event: tk.Event) -> str:
        """Allow newline insertion on Shift+Return."""
        return ""

    def _handle_send(self) -> None:
        """Extract text and invoke send callback."""
        if self._disabled:
            return
        text = self.text_input.get("1.0", tk.END).strip()
        if text:
            self.text_input.delete("1.0", tk.END)
            self.on_send(text)

    def _on_send_click(self) -> None:
        self._handle_send()

    def _handle_voice(self) -> None:
        """Invoke voice capture callback."""
        if self._disabled:
            return
        self.on_voice()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable input components."""
        self.set_processing(not enabled)
        self.text_input.config(state=tk.NORMAL if enabled else tk.DISABLED)

    def set_processing(self, processing: bool) -> None:
        """Disable or enable buttons when AI is thinking."""
        self._disabled = processing
        if processing:
            self.send_btn.config(state=tk.DISABLED, bg=CARD_BG, fg=TEXT_DIM)
            self.voice_btn.config(state=tk.DISABLED, fg=TEXT_DIM)
        else:
            self.send_btn.config(state=tk.NORMAL, bg=ACCENT_BLUE, fg="#ffffff")
            self.voice_btn.config(state=tk.NORMAL, bg=CARD_BG, fg=TEXT_MUTED)

    def set_listening(self, listening: bool) -> None:
        """Reflect microphone recording state visually."""
        if listening:
            self.voice_btn.config(bg=COLOR_WARNING, fg="#18191c", text="Listening...")
        else:
            self.voice_btn.config(bg=CARD_BG, fg=TEXT_MUTED, text="🎤 Voice")
