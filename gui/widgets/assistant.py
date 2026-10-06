"""
Assistant View Widget for CHARVIS (Phase 19).
Compact, clean, responsive assistant surface communicating:
- Activation status (Ready, Listening, Thinking, Speaking, Paused, Error, Offline)
- Dynamic Activate / Stop Listening button
- User command & assistant response with sensitive secret redaction
- Multi-step task planner progress integration
- Wake word & hotkey status indicators
- Compact mode support
"""

import re
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional

from activation.models import ActivationSource, ActivationState
from config import get_settings
from gui.controller import GUIController
from gui.models import SystemState, TaskDisplayItem
from gui.state import GUIState
from gui.theme import (
    ACCENT_BLUE,
    ACCENT_HOVER,
    BG_DARK,
    BORDER_COLOR,
    BORDER_SUBTLE,
    CARD_BG,
    COLOR_ERROR,
    COLOR_SUCCESS,
    COLOR_WARNING,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CAPTION,
    FONT_CODE,
    FONT_HEADER,
    FONT_TITLE,
    PANEL_BG,
    TEXT_DIM,
    TEXT_MAIN,
    TEXT_MUTED,
)
from logger import SensitiveDataFilter, get_logger

logger = get_logger("CHARVIS.GUI.Assistant")


def redact_display_text(text: Optional[str]) -> str:
    """Sanitize secrets, passwords, tokens, and keys from UI display."""
    if not text:
        return ""
    data_filter = SensitiveDataFilter()
    sanitized = re.sub(r'(?i)\bbearer\s+[a-zA-Z0-9_\-\.]{10,}\b', 'Bearer [REDACTED]', text)
    for pattern, replacement in data_filter.PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class AssistantViewWidget(ttk.Frame):
    """
    Dedicated compact assistant view for CHARVIS.
    Can operate in standard view or standalone compact assistant window.
    """

    def __init__(
        self,
        parent: tk.Widget,
        state: Optional[GUIState] = None,
        controller: Optional[GUIController] = None,
        on_toggle_compact: Optional[Callable[[], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, style="Panel.TFrame", **kwargs)
        self.state = state
        self.controller = controller
        self.on_toggle_compact = on_toggle_compact
        self.settings = get_settings()

        # Animation pulse state
        self._pulse_state = False
        self._pulse_job: Optional[str] = None

        # Build UI layout
        self._build_ui()

        # State subscriptions
        if self.state:
            self.state.subscribe(self._on_state_change)

        if self.controller and hasattr(self.controller, "activation_manager"):
            self.controller.activation_manager.add_listener(self._on_activation_session)

        # Start lightweight pulse loop
        self._start_pulse()

    def _build_ui(self) -> None:
        """Construct the compact assistant visual elements."""
        self.configure(style="Panel.TFrame")

        # Top Header Bar
        self.header_bar = tk.Frame(self, bg=PANEL_BG)
        self.header_bar.pack(fill=tk.X, padx=18, pady=(14, 10))

        title_frame = tk.Frame(self.header_bar, bg=PANEL_BG)
        title_frame.pack(side=tk.LEFT)

        self.title_lbl = tk.Label(
            title_frame,
            text=self.settings.app_name,
            font=FONT_TITLE,
            bg=PANEL_BG,
            fg=TEXT_MAIN,
        )
        self.title_lbl.pack(side=tk.LEFT)

        self.badge_lbl = tk.Label(
            title_frame,
            text="Assistant",
            font=FONT_CAPTION,
            bg=CARD_BG,
            fg=TEXT_MUTED,
            padx=6,
            pady=1,
        )
        self.badge_lbl.pack(side=tk.LEFT, padx=8)

        # Header right actions
        header_actions = tk.Frame(self.header_bar, bg=PANEL_BG)
        header_actions.pack(side=tk.RIGHT)

        # Wake Word Toggle Badge
        self.wakeword_btn = tk.Button(
            header_actions,
            text="○ Wake Word OFF",
            font=FONT_CAPTION,
            bg=CARD_BG,
            fg=TEXT_DIM,
            activebackground=PANEL_BG,
            activeforeground=TEXT_MAIN,
            bd=0,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._toggle_wake_word,
        )
        self.wakeword_btn.pack(side=tk.LEFT, padx=4)

        # Compact Mode Toggle
        if self.on_toggle_compact:
            self.compact_btn = tk.Button(
                header_actions,
                text="⤡ Compact",
                font=FONT_CAPTION,
                bg=CARD_BG,
                fg=TEXT_MUTED,
                activebackground=PANEL_BG,
                activeforeground=TEXT_MAIN,
                bd=0,
                padx=8,
                pady=2,
                cursor="hand2",
                command=self.on_toggle_compact,
            )
            self.compact_btn.pack(side=tk.LEFT, padx=4)

        # Divider
        divider = tk.Frame(self, height=1, bg=BORDER_COLOR)
        divider.pack(fill=tk.X, padx=18, pady=(0, 14))

        # Main Scrollable / Stack Container
        content_container = tk.Frame(self, bg=PANEL_BG)
        content_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        # 1. Primary Status Card
        self.status_card = tk.Frame(content_container, bg=CARD_BG, bd=1, relief=tk.SOLID)
        self.status_card.pack(fill=tk.X, pady=(0, 12), ipady=12)

        self.status_orb_label = tk.Label(
            self.status_card,
            text="●",
            font=("Segoe UI", 28),
            bg=CARD_BG,
            fg=COLOR_SUCCESS,
        )
        self.status_orb_label.pack(pady=(4, 0))

        self.status_title_label = tk.Label(
            self.status_card,
            text="Ready",
            font=FONT_HEADER,
            bg=CARD_BG,
            fg=TEXT_MAIN,
        )
        self.status_title_label.pack(pady=(2, 2))

        self.status_sub_label = tk.Label(
            self.status_card,
            text="How can I help you?",
            font=FONT_BODY,
            bg=CARD_BG,
            fg=TEXT_MUTED,
        )
        self.status_sub_label.pack(pady=(0, 6))

        # 2. Main Microphone Activation Button
        btn_frame = tk.Frame(content_container, bg=PANEL_BG)
        btn_frame.pack(fill=tk.X, pady=(0, 12))

        self.action_btn = tk.Button(
            btn_frame,
            text="🎤 Activate",
            font=FONT_BODY_BOLD,
            bg=ACCENT_BLUE,
            fg=TEXT_MAIN,
            activebackground=ACCENT_HOVER,
            activeforeground=TEXT_MAIN,
            bd=0,
            pady=12,
            cursor="hand2",
            command=self._on_action_button_clicked,
        )
        self.action_btn.pack(fill=tk.X)

        self.hotkey_hint = tk.Label(
            btn_frame,
            text="Global Hotkey: Ctrl + Alt + Space",
            font=FONT_CAPTION,
            bg=PANEL_BG,
            fg=TEXT_DIM,
        )
        self.hotkey_hint.pack(pady=(4, 0))

        # 3. Speech & Response Deck
        self.speech_card = tk.Frame(content_container, bg=CARD_BG, bd=1, relief=tk.SOLID)
        self.speech_card.pack(fill=tk.X, pady=(0, 12), ipady=8, ipadx=10)

        # Command row
        cmd_row = tk.Frame(self.speech_card, bg=CARD_BG)
        cmd_row.pack(fill=tk.X, padx=10, pady=(4, 2))

        tk.Label(
            cmd_row,
            text="YOU:",
            font=FONT_CAPTION,
            bg=CARD_BG,
            fg=ACCENT_BLUE,
            width=8,
            anchor="w",
        ).pack(side=tk.LEFT)

        self.command_lbl = tk.Label(
            cmd_row,
            text="(No recent command)",
            font=FONT_BODY,
            bg=CARD_BG,
            fg=TEXT_MAIN,
            anchor="w",
            wraplength=480,
            justify=tk.LEFT,
        )
        self.command_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Divider inside speech card
        tk.Frame(self.speech_card, height=1, bg=BORDER_SUBTLE).pack(fill=tk.X, padx=10, pady=6)

        # Response row
        resp_row = tk.Frame(self.speech_card, bg=CARD_BG)
        resp_row.pack(fill=tk.X, padx=10, pady=(2, 4))

        tk.Label(
            resp_row,
            text="CHARVIS:",
            font=FONT_CAPTION,
            bg=CARD_BG,
            fg=COLOR_SUCCESS,
            width=8,
            anchor="w",
        ).pack(side=tk.LEFT)

        self.response_lbl = tk.Label(
            resp_row,
            text="(Waiting for prompt)",
            font=FONT_BODY,
            bg=CARD_BG,
            fg=TEXT_MUTED,
            anchor="w",
            wraplength=480,
            justify=tk.LEFT,
        )
        self.response_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 4. Multi-step Task / Planner Progress Card (hidden by default)
        self.task_card = tk.Frame(content_container, bg=CARD_BG, bd=1, relief=tk.SOLID)
        self.task_header_lbl = tk.Label(
            self.task_card,
            text="TASK PROGRESS",
            font=("Segoe UI", 8, "bold"),
            bg=CARD_BG,
            fg=TEXT_DIM,
            anchor="w",
        )
        self.task_goal_lbl = tk.Label(
            self.task_card,
            text="",
            font=FONT_BODY_BOLD,
            bg=CARD_BG,
            fg=TEXT_MAIN,
            anchor="w",
        )
        self.task_progress_lbl = tk.Label(
            self.task_card,
            text="",
            font=FONT_CAPTION,
            bg=CARD_BG,
            fg=ACCENT_BLUE,
            anchor="w",
        )
        self.task_steps_box = tk.Frame(self.task_card, bg=CARD_BG)

        # 5. Quick Text Input Bar (Keyboard fallback)
        input_container = tk.Frame(self, bg=PANEL_BG)
        input_container.pack(fill=tk.X, side=tk.BOTTOM, padx=18, pady=(0, 14))

        self.input_entry = tk.Entry(
            input_container,
            font=FONT_BODY,
            bg=CARD_BG,
            fg=TEXT_MAIN,
            insertbackground=TEXT_MAIN,
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=ACCENT_BLUE,
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0, 8))
        self.input_entry.bind("<Return>", lambda e: self._on_send_text())

        self.send_btn = tk.Button(
            input_container,
            text="Send",
            font=FONT_BODY_BOLD,
            bg=CARD_BG,
            fg=TEXT_MAIN,
            activebackground=PANEL_BG,
            activeforeground=TEXT_MAIN,
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._on_send_text,
        )
        self.send_btn.pack(side=tk.RIGHT)

        # Initialize visual status
        self._update_ui_state()

    # ==========================================================================
    # State & Visual Updates
    # ==========================================================================
    def _update_ui_state(self) -> None:
        """Refresh labels and button based on current GUI and activation state."""
        sys_state = self.state.system_state if self.state else SystemState.READY
        is_listening = self.state.is_listening if self.state else False
        is_processing = self.state.is_processing if self.state else False

        # Check activation session state if controller has activation manager
        act_state = ActivationState.INACTIVE
        if self.controller and hasattr(self.controller, "activation_manager"):
            act_state = self.controller.activation_manager.current_state

        if is_listening or act_state == ActivationState.LISTENING:
            self._set_state_display(
                orb="🎤",
                orb_color=COLOR_WARNING,
                title="Listening...",
                sub="I'm listening",
                btn_text="⏹ Stop Listening",
                btn_bg=COLOR_ERROR,
            )
        elif is_processing or act_state == ActivationState.PROCESSING:
            self._set_state_display(
                orb="🧠",
                orb_color=ACCENT_BLUE,
                title="Thinking...",
                sub="Processing your request",
                btn_text="⚙ Processing...",
                btn_bg=CARD_BG,
                btn_state=tk.DISABLED,
            )
        elif sys_state == SystemState.SPEAKING or act_state == ActivationState.SPEAKING:
            self._set_state_display(
                orb="🔊",
                orb_color=ACCENT_BLUE,
                title="Speaking...",
                sub="Speaking response",
                btn_text="⏹ Stop Speaking",
                btn_bg=COLOR_WARNING,
            )
        elif sys_state == SystemState.PAUSED:
            self._set_state_display(
                orb="⏸",
                orb_color=TEXT_MUTED,
                title="Paused",
                sub="CHARVIS is paused",
                btn_text="🎤 Activate",
                btn_bg=ACCENT_BLUE,
            )
        elif sys_state in (SystemState.OFFLINE, SystemState.DISCONNECTED):
            self._set_state_display(
                orb="○",
                orb_color=TEXT_DIM,
                title="Offline",
                sub="Runtime unavailable",
                btn_text="🎤 Activate",
                btn_bg=CARD_BG,
            )
        elif sys_state == SystemState.ERROR or act_state == ActivationState.ERROR:
            self._set_state_display(
                orb="✕",
                orb_color=COLOR_ERROR,
                title="Error",
                sub="Something went wrong",
                btn_text="🎤 Activate",
                btn_bg=ACCENT_BLUE,
            )
        else:
            # READY
            self._set_state_display(
                orb="●",
                orb_color=COLOR_SUCCESS,
                title="Ready",
                sub="How can I help you?",
                btn_text="🎤 Activate",
                btn_bg=ACCENT_BLUE,
            )

        # Refresh wake word status badge
        if self.controller and hasattr(self.controller, "activation_manager"):
            mgr = self.controller.activation_manager
            ww_active = bool(mgr.wake_word_engine and getattr(mgr.wake_word_engine, "is_running", lambda: False)())
            if ww_active:
                self.wakeword_btn.config(text="● Wake Word ON", fg=COLOR_SUCCESS)
            else:
                self.wakeword_btn.config(text="○ Wake Word OFF", fg=TEXT_DIM)

        # Update task progress card
        self._update_task_card()

    def _set_state_display(
        self,
        orb: str,
        orb_color: str,
        title: str,
        sub: str,
        btn_text: str,
        btn_bg: str,
        btn_state: str = tk.NORMAL,
    ) -> None:
        """Update status card labels and main activation button."""
        try:
            self.status_orb_label.config(text=orb, fg=orb_color)
            self.status_title_label.config(text=title)
            self.status_sub_label.config(text=sub)
            self.action_btn.config(text=btn_text, bg=btn_bg, state=btn_state)
        except Exception:
            pass

    def _update_task_card(self) -> None:
        """Render multi-step task progress if an active task exists."""
        if not self.state or not self.state.active_task:
            if self.task_card.winfo_manager():
                self.task_card.pack_forget()
            return

        task: TaskDisplayItem = self.state.active_task
        if not self.task_card.winfo_manager():
            self.task_card.pack(fill=tk.X, pady=(0, 12), ipady=6, ipadx=10, before=self.speech_card)
            self.task_header_lbl.pack(fill=tk.X, padx=10, pady=(4, 2))
            self.task_goal_lbl.pack(fill=tk.X, padx=10, pady=(0, 2))
            self.task_progress_lbl.pack(fill=tk.X, padx=10, pady=(0, 6))
            self.task_steps_box.pack(fill=tk.X, padx=10, pady=(0, 4))

        self.task_goal_lbl.config(text=redact_display_text(task.goal))
        self.task_progress_lbl.config(text=f"Progress: Step {task.current_step} of {task.total_steps}")

        # Render compact step list
        for child in self.task_steps_box.winfo_children():
            child.destroy()

        for idx, step in enumerate(task.steps[:5]):
            step_num = idx + 1
            step_name = redact_display_text(step.get("description", step.get("tool", f"Step {step_num}")))
            status = step.get("status", "pending").lower()

            if status in ("completed", "done", "success"):
                bullet = "●"
                b_color = COLOR_SUCCESS
            elif step_num == task.current_step or status in ("executing", "running"):
                bullet = "→"
                b_color = ACCENT_BLUE
            elif status in ("waiting_confirmation", "confirmation_required"):
                bullet = "⚠️"
                b_color = COLOR_WARNING
            else:
                bullet = "○"
                b_color = TEXT_DIM

            step_line = tk.Frame(self.task_steps_box, bg=CARD_BG)
            step_line.pack(fill=tk.X, pady=1)

            tk.Label(
                step_line,
                text=bullet,
                font=FONT_CAPTION,
                bg=CARD_BG,
                fg=b_color,
                width=2,
            ).pack(side=tk.LEFT)

            tk.Label(
                step_line,
                text=step_name,
                font=FONT_CAPTION,
                bg=CARD_BG,
                fg=TEXT_MAIN if step_num == task.current_step else TEXT_MUTED,
                anchor="w",
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

    # ==========================================================================
    # Event Handlers
    # ==========================================================================
    def _on_action_button_clicked(self) -> None:
        """Handle user clicking the primary dynamic activation button."""
        if not self.controller:
            return

        is_listening = self.state.is_listening if self.state else False
        act_state = ActivationState.INACTIVE
        if hasattr(self.controller, "activation_manager"):
            act_state = self.controller.activation_manager.current_state

        if is_listening or act_state == ActivationState.LISTENING:
            logger.info("Assistant UI: User requested to stop listening.")
            self.controller.cancel_activation("User clicked Stop Listening")
        elif act_state == ActivationState.SPEAKING:
            logger.info("Assistant UI: User requested to stop speaking.")
            self.controller.cancel_activation("User clicked Stop Speaking")
        else:
            logger.info("Assistant UI: User requested microphone activation.")
            self.controller.request_activation(ActivationSource.GUI)

    def _toggle_wake_word(self) -> None:
        """Toggle the wake-word engine on/off."""
        if not self.controller or not hasattr(self.controller, "activation_manager"):
            return

        mgr = self.controller.activation_manager
        ww_active = bool(mgr.wake_word_engine and getattr(mgr.wake_word_engine, "is_running", lambda: False)())
        if ww_active:
            mgr.disable_wake_word()
        else:
            mgr.enable_wake_word()

        self._update_ui_state()

    def _on_send_text(self) -> None:
        """Submit text from quick input field."""
        text = self.input_entry.get().strip()
        if not text or not self.controller:
            return

        self.input_entry.delete(0, tk.END)
        self.set_command_display(text)
        self.controller.send_user_message(text)

    def set_command_display(self, command_text: str) -> None:
        """Update displayed user command with secret redaction."""
        clean = redact_display_text(command_text)
        try:
            self.command_lbl.config(text=f'"{clean}"' if clean else "(No recent command)")
        except Exception:
            pass

    def set_response_display(self, response_text: str) -> None:
        """Update displayed assistant response with secret redaction."""
        clean = redact_display_text(response_text)
        try:
            self.response_lbl.config(text=clean if clean else "(Waiting for prompt)")
        except Exception:
            pass

    def _on_state_change(self, state: GUIState) -> None:
        """React to global GUIState changes."""
        try:
            if not self.winfo_exists():
                return
            if state.messages:
                last_user = next((m for m in reversed(state.messages) if m.is_user), None)
                if last_user:
                    self.set_command_display(last_user.content)

                last_asst = next((m for m in reversed(state.messages) if m.is_charvis), None)
                if last_asst:
                    self.set_response_display(last_asst.content)

            self._update_ui_state()
        except Exception:
            pass

    def _on_activation_session(self, session: Any) -> None:
        """React to ActivationManager session updates."""
        try:
            if not self.winfo_exists():
                return
            if hasattr(session, "command_text") and session.command_text:
                self.set_command_display(session.command_text)
            if hasattr(session, "response_text") and session.response_text:
                self.set_response_display(session.response_text)

            self._update_ui_state()
        except Exception:
            pass

    # ==========================================================================
    # Lightweight Non-Blocking UI Pulse Animation
    # ==========================================================================
    def _start_pulse(self) -> None:
        """Schedule subtle non-blocking indicator pulse without busy-waiting."""
        self._pulse_tick()

    def _pulse_tick(self) -> None:
        """Lightweight visual pulse for active listening/processing states."""
        try:
            if not self.winfo_exists():
                return
            is_listening = self.state.is_listening if self.state else False
            is_processing = self.state.is_processing if self.state else False

            if is_listening or is_processing:
                self._pulse_state = not self._pulse_state
                accent_color = COLOR_WARNING if is_listening else ACCENT_BLUE
                dim_color = CARD_BG
                new_bg = accent_color if self._pulse_state else dim_color
                try:
                    self.status_card.config(highlightbackground=new_bg, highlightthickness=1)
                except Exception:
                    pass
            else:
                try:
                    self.status_card.config(highlightthickness=0)
                except Exception:
                    pass

            self._pulse_job = self.after(500, self._pulse_tick)
        except Exception:
            pass

    def destroy(self) -> None:
        """Clean up pulse timer on widget destruction."""
        if self._pulse_job:
            try:
                self.after_cancel(self._pulse_job)
            except Exception:
                pass
            self._pulse_job = None
        super().destroy()
