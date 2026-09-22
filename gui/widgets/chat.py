"""
CHARVIS GUI — Chat View Widget

Scrollable conversation transcript displaying user messages, assistant responses,
tool actions/results, and system notifications with clean visual cards.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable
from datetime import datetime

from gui.theme import (
    BG_DARK, PANEL_BG, CARD_BG, INPUT_BG,
    TEXT_MAIN, TEXT_MUTED, TEXT_HINT,
    ACCENT_PRIMARY, ACCENT_SECONDARY, ACCENT_SUCCESS, ACCENT_WARNING, ACCENT_DANGER,
    BORDER_COLOR, FONT_MAIN, FONT_BOLD, FONT_CODE, FONT_SMALL
)
from gui.models import ChatMessage
from gui.state import GUIState
from gui.controller import GUIController
from gui.widgets.input_bar import InputBarWidget


class ChatViewWidget(tk.Frame):
    """
    Main Chat view containing:
    - Top action bar (Clear chat, message count)
    - Scrollable canvas/text frame with formatted message cards
    - Integrated InputBarWidget at the bottom
    """

    def __init__(
        self,
        parent: tk.Widget,
        state: GUIState,
        controller: GUIController,
        on_voice_requested: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(parent, bg=BG_DARK, **kwargs)
        self.state = state
        self.controller = controller
        self.on_voice_requested = on_voice_requested

        self._build_ui()
        self.state.subscribe(self._on_state_change)

    def _build_ui(self) -> None:
        # Header / Action bar
        self.header_frame = tk.Frame(self, bg=PANEL_BG, height=44, padx=16, pady=8)
        self.header_frame.pack(side=tk.TOP, fill=tk.X)

        self.title_label = tk.Label(
            self.header_frame,
            text="Conversation",
            font=FONT_BOLD,
            fg=TEXT_MAIN,
            bg=PANEL_BG,
        )
        self.title_label.pack(side=tk.LEFT)

        self.count_label = tk.Label(
            self.header_frame,
            text="0 messages",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=PANEL_BG,
        )
        self.count_label.pack(side=tk.LEFT, padx=(12, 0))

        self.clear_btn = tk.Button(
            self.header_frame,
            text="Clear History",
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
            command=self._on_clear_click,
        )
        self.clear_btn.pack(side=tk.RIGHT)

        # Bottom Input Bar
        self.input_bar = InputBarWidget(
            self,
            on_send=self._on_send_message,
            on_voice=self.on_voice_requested,
        )
        self.input_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Message Scroll Area (Text widget acting as rich message display)
        self.content_frame = tk.Frame(self, bg=BG_DARK)
        self.content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.scrollbar = ttk.Scrollbar(self.content_frame, orient=tk.VERTICAL)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.chat_display = tk.Text(
            self.content_frame,
            bg=BG_DARK,
            fg=TEXT_MAIN,
            font=FONT_MAIN,
            wrap=tk.WORD,
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=16,
            yscrollcommand=self.scrollbar.set,
            state=tk.DISABLED,
            cursor="arrow",
        )
        self.chat_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.chat_display.yview)

        self._configure_tags()

    def _configure_tags(self) -> None:
        """Configure styles/tags for the rich text transcript."""
        self.chat_display.tag_configure("user_header", font=FONT_BOLD, foreground=ACCENT_PRIMARY)
        self.chat_display.tag_configure("assistant_header", font=FONT_BOLD, foreground=ACCENT_SECONDARY)
        self.chat_display.tag_configure("system_header", font=FONT_BOLD, foreground=ACCENT_WARNING)
        self.chat_display.tag_configure("tool_header", font=FONT_BOLD, foreground=ACCENT_SUCCESS)
        self.chat_display.tag_configure("error_header", font=FONT_BOLD, foreground=ACCENT_DANGER)

        self.chat_display.tag_configure("timestamp", font=FONT_SMALL, foreground=TEXT_MUTED)
        self.chat_display.tag_configure("body", font=FONT_MAIN, foreground=TEXT_MAIN, spacing1=4, spacing3=8)
        self.chat_display.tag_configure("code_body", font=FONT_CODE, foreground="#a6e22e", background=CARD_BG, spacing1=4, spacing3=6)
        self.chat_display.tag_configure("muted_body", font=FONT_SMALL, foreground=TEXT_HINT, spacing1=2, spacing3=6)
        self.chat_display.tag_configure("divider", font=FONT_SMALL, foreground=BORDER_COLOR)

    def _on_send_message(self, text: str) -> None:
        if not text.strip():
            return
        self.controller.send_user_message(text)

    def _on_clear_click(self) -> None:
        self.state.clear_messages()

    def _on_state_change(self, state: GUIState) -> None:
        """Render updated messages if message list changed."""
        messages = state.messages
        self.count_label.config(text=f"{len(messages)} message{'s' if len(messages) != 1 else ''}")

        # Update input bar enabled status based on is_busy
        if state.is_busy:
            self.input_bar.set_enabled(False)
        else:
            self.input_bar.set_enabled(True)

        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)

        if not messages:
            self.chat_display.insert(
                tk.END,
                "\n\n  Welcome to CHARVIS Desktop Assistant.\n\n"
                "  Type a message below or click the microphone to begin.\n"
                "  Switch views using the sidebar to monitor tasks, memory, and settings.\n",
                ("muted_body",)
            )
            self.chat_display.config(state=tk.DISABLED)
            return

        for msg in messages:
            time_str = msg.timestamp.strftime("%H:%M:%S")

            if msg.role == "user":
                header_tag = "user_header"
                role_label = "You"
            elif msg.role == "assistant":
                header_tag = "assistant_header"
                role_label = "CHARVIS"
            elif msg.role == "tool":
                header_tag = "tool_header"
                role_label = f"Tool: {msg.metadata.get('tool_name', 'action')}"
            elif msg.role == "error":
                header_tag = "error_header"
                role_label = "Error"
            else:
                header_tag = "system_header"
                role_label = "System"

            self.chat_display.insert(tk.END, f"{role_label} ", (header_tag,))
            self.chat_display.insert(tk.END, f"  {time_str}\n", ("timestamp",))

            body_tag = "code_body" if msg.role == "tool" else "body"
            self.chat_display.insert(tk.END, f"{msg.content}\n", (body_tag,))
            self.chat_display.insert(tk.END, "―" * 48 + "\n\n", ("divider",))

        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
