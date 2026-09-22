"""
CHARVIS GUI — Task Panel Widget

Monitor and control multi-step task execution:
- Task list with status badges
- Step-by-step plan breakdown with progress tracking
- Interactive execution controls (Run, Pause, Resume, Cancel)
- Live activity & execution log viewer
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, List, Dict, Any

from gui.theme import (
    BG_DARK, PANEL_BG, CARD_BG, INPUT_BG,
    TEXT_MAIN, TEXT_MUTED, TEXT_HINT,
    ACCENT_PRIMARY, ACCENT_SECONDARY, ACCENT_SUCCESS, ACCENT_WARNING, ACCENT_DANGER,
    BORDER_COLOR, FONT_MAIN, FONT_BOLD, FONT_CODE, FONT_SMALL, FONT_TITLE
)
from gui.models import TaskDisplayItem
from gui.state import GUIState
from gui.controller import GUIController


class TaskPanelWidget(tk.Frame):
    """
    Multi-step Task Planner monitor and control interface.
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

        self._build_ui()
        self.state.subscribe(self._on_state_change)
        # Trigger initial load of tasks
        self.controller.load_tasks()

    def _build_ui(self) -> None:
        # Header / Action bar
        self.header_frame = tk.Frame(self, bg=PANEL_BG, height=44, padx=16, pady=8)
        self.header_frame.pack(side=tk.TOP, fill=tk.X)

        self.title_label = tk.Label(
            self.header_frame,
            text="Multi-Step Task Planner",
            font=FONT_BOLD,
            fg=TEXT_MAIN,
            bg=PANEL_BG,
        )
        self.title_label.pack(side=tk.LEFT)

        self.refresh_btn = tk.Button(
            self.header_frame,
            text="Refresh Tasks",
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
            command=self.controller.load_tasks,
        )
        self.refresh_btn.pack(side=tk.RIGHT)

        # Plan Creation Bar
        self.create_frame = tk.Frame(self, bg=CARD_BG, padx=12, pady=8)
        self.create_frame.pack(side=tk.TOP, fill=tk.X, padx=16, pady=(12, 6))

        tk.Label(
            self.create_frame,
            text="Create Plan:",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=CARD_BG,
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.prompt_entry = tk.Entry(
            self.create_frame,
            font=FONT_MAIN,
            fg=TEXT_MAIN,
            bg=INPUT_BG,
            relief=tk.FLAT,
            bd=0,
            insertbackground=TEXT_MAIN,
        )
        self.prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 8))
        self.prompt_entry.bind("<Return>", lambda e: self._on_create_plan())

        self.create_btn = tk.Button(
            self.create_frame,
            text="Generate Plan",
            font=FONT_SMALL,
            fg="#ffffff",
            bg=ACCENT_PRIMARY,
            activebackground=ACCENT_SECONDARY,
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._on_create_plan,
        )
        self.create_btn.pack(side=tk.RIGHT)

        # Main Split Content: Left = Tasks List & Steps, Right = Logs & Controls
        self.paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=BORDER_COLOR, bd=0, sashwidth=4)
        self.paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=16, pady=(6, 16))

        # Left Column: Tasks and Steps
        self.left_col = tk.Frame(self.paned, bg=BG_DARK)
        self.paned.add(self.left_col, minsize=320, stretch="always")

        # Active Task Card
        self.active_card = tk.Frame(self.left_col, bg=CARD_BG, padx=12, pady=12)
        self.active_card.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        self.active_title = tk.Label(
            self.active_card,
            text="No Active Task",
            font=FONT_BOLD,
            fg=TEXT_MAIN,
            bg=CARD_BG,
            anchor="w",
        )
        self.active_title.pack(fill=tk.X)

        self.active_status = tk.Label(
            self.active_card,
            text="Status: Idle",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=CARD_BG,
            anchor="w",
        )
        self.active_status.pack(fill=tk.X, pady=(2, 6))

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            self.active_card,
            variable=self.progress_var,
            maximum=100.0,
            style="Horizontal.TProgressbar",
        )
        self.progress_bar.pack(fill=tk.X, pady=(2, 8))

        # Control Buttons
        self.ctrl_btn_frame = tk.Frame(self.active_card, bg=CARD_BG)
        self.ctrl_btn_frame.pack(fill=tk.X)

        self.btn_run = tk.Button(
            self.ctrl_btn_frame,
            text="Run Plan",
            font=FONT_SMALL,
            fg="#ffffff",
            bg=ACCENT_SUCCESS,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self.controller.run_active_task,
        )
        self.btn_run.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_pause = tk.Button(
            self.ctrl_btn_frame,
            text="Pause",
            font=FONT_SMALL,
            fg="#ffffff",
            bg=ACCENT_WARNING,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self.controller.pause_active_task,
        )
        self.btn_pause.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_resume = tk.Button(
            self.ctrl_btn_frame,
            text="Resume",
            font=FONT_SMALL,
            fg="#ffffff",
            bg=ACCENT_PRIMARY,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self.controller.resume_active_task,
        )
        self.btn_resume.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_cancel = tk.Button(
            self.ctrl_btn_frame,
            text="Cancel",
            font=FONT_SMALL,
            fg="#ffffff",
            bg=ACCENT_DANGER,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self.controller.cancel_active_task,
        )
        self.btn_cancel.pack(side=tk.LEFT)

        # Steps Treeview / List
        self.steps_label = tk.Label(
            self.left_col,
            text="Task Steps",
            font=FONT_BOLD,
            fg=TEXT_MAIN,
            bg=BG_DARK,
            anchor="w",
        )
        self.steps_label.pack(fill=tk.X, pady=(4, 4))

        self.steps_frame = tk.Frame(self.left_col, bg=PANEL_BG)
        self.steps_frame.pack(fill=tk.BOTH, expand=True)

        self.steps_tree = ttk.Treeview(
            self.steps_frame,
            columns=("idx", "tool", "desc", "status"),
            show="headings",
            selectmode="browse",
        )
        self.steps_tree.heading("idx", text="#")
        self.steps_tree.heading("tool", text="Tool")
        self.steps_tree.heading("desc", text="Description")
        self.steps_tree.heading("status", text="Status")

        self.steps_tree.column("idx", width=36, anchor="center")
        self.steps_tree.column("tool", width=110, anchor="w")
        self.steps_tree.column("desc", width=180, anchor="w")
        self.steps_tree.column("status", width=90, anchor="center")

        self.steps_scroll = ttk.Scrollbar(self.steps_frame, orient=tk.VERTICAL, command=self.steps_tree.yview)
        self.steps_tree.configure(yscrollcommand=self.steps_scroll.set)
        self.steps_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.steps_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Right Column: Execution Logs
        self.right_col = tk.Frame(self.paned, bg=BG_DARK)
        self.paned.add(self.right_col, minsize=280, stretch="always")

        self.log_header = tk.Label(
            self.right_col,
            text="Execution Log",
            font=FONT_BOLD,
            fg=TEXT_MAIN,
            bg=BG_DARK,
            anchor="w",
        )
        self.log_header.pack(fill=tk.X, pady=(0, 4))

        self.log_frame = tk.Frame(self.right_col, bg=PANEL_BG)
        self.log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_scroll = ttk.Scrollbar(self.log_frame, orient=tk.VERTICAL)
        self.log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(
            self.log_frame,
            bg=PANEL_BG,
            fg=TEXT_MAIN,
            font=FONT_CODE,
            relief=tk.FLAT,
            bd=0,
            wrap=tk.WORD,
            padx=10,
            pady=10,
            yscrollcommand=self.log_scroll.set,
            state=tk.DISABLED,
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_scroll.config(command=self.log_text.yview)

    def _on_create_plan(self) -> None:
        prompt = self.prompt_entry.get().strip()
        if not prompt:
            return
        self.prompt_entry.delete(0, tk.END)
        self.controller.create_task(prompt)

    def _on_state_change(self, state: GUIState) -> None:
        # Update Active Task Card
        active = state.active_task
        if active:
            self.active_title.config(text=f"Task: {active.task_id} — {active.goal}")
            self.active_status.config(
                text=f"Status: {active.status.upper()} | Completed: {active.completed_steps}/{active.total_steps}"
            )
            pct = (active.completed_steps / active.total_steps * 100.0) if active.total_steps > 0 else 0.0
            self.progress_var.set(pct)

            # Update Steps Tree
            self.steps_tree.delete(*self.steps_tree.get_children())
            for idx, step in enumerate(active.steps, start=1):
                tool = step.get("tool_name", "-")
                desc = step.get("description", "")
                st = step.get("status", "pending")
                self.steps_tree.insert("", tk.END, values=(idx, tool, desc, st))
        else:
            self.active_title.config(text="No Active Task")
            self.active_status.config(text="Status: Idle")
            self.progress_var.set(0.0)
            self.steps_tree.delete(*self.steps_tree.get_children())

        # Update Logs
        logs = state.task_logs
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        for line in logs:
            self.log_text.insert(tk.END, f"{line}\n")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)
