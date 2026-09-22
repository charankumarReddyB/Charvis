"""
CHARVIS GUI — Memory View Widget

Read-only viewer for CHARVIS persistent memory system:
- Filter and search memories
- Categorized view (user facts, preferences, system knowledge)
- Inspect memory keys, values, and confidence scores
- Refresh button to reload stored knowledge
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, List, Dict, Any

from gui.theme import (
    BG_DARK, PANEL_BG, CARD_BG, INPUT_BG,
    TEXT_MAIN, TEXT_MUTED, TEXT_HINT,
    ACCENT_PRIMARY, ACCENT_SECONDARY, ACCENT_SUCCESS, ACCENT_WARNING,
    BORDER_COLOR, FONT_MAIN, FONT_BOLD, FONT_CODE, FONT_SMALL
)
from gui.state import GUIState
from gui.controller import GUIController


class MemoryViewWidget(tk.Frame):
    """
    Read-only explorer for persistent and working memory.
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

        self._memories: List[Dict[str, Any]] = []
        self._build_ui()
        self.state.subscribe(self._on_state_change)
        self._refresh()

    def _build_ui(self) -> None:
        # Header / Action bar
        self.header_frame = tk.Frame(self, bg=PANEL_BG, height=44, padx=16, pady=8)
        self.header_frame.pack(side=tk.TOP, fill=tk.X)

        self.title_label = tk.Label(
            self.header_frame,
            text="Memory Explorer (Read-Only)",
            font=FONT_BOLD,
            fg=TEXT_MAIN,
            bg=PANEL_BG,
        )
        self.title_label.pack(side=tk.LEFT)

        self.refresh_btn = tk.Button(
            self.header_frame,
            text="Refresh",
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

        # Search Bar
        self.search_frame = tk.Frame(self, bg=CARD_BG, padx=12, pady=8)
        self.search_frame.pack(side=tk.TOP, fill=tk.X, padx=16, pady=(12, 8))

        tk.Label(
            self.search_frame,
            text="Search:",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=CARD_BG,
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.search_entry = tk.Entry(
            self.search_frame,
            font=FONT_MAIN,
            fg=TEXT_MAIN,
            bg=INPUT_BG,
            relief=tk.FLAT,
            bd=0,
            insertbackground=TEXT_MAIN,
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_memories())

        # Main Split Content: Left = Treeview, Right = Value Viewer
        self.paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=BORDER_COLOR, bd=0, sashwidth=4)
        self.paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

        # Left Column: Memory Keys / Items Table
        self.left_frame = tk.Frame(self.paned, bg=BG_DARK)
        self.paned.add(self.left_frame, minsize=320, stretch="always")

        self.tree = ttk.Treeview(
            self.left_frame,
            columns=("key", "category", "scope"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("key", text="Memory Key")
        self.tree.heading("category", text="Category")
        self.tree.heading("scope", text="Scope")

        self.tree.column("key", width=180, anchor="w")
        self.tree.column("category", width=90, anchor="center")
        self.tree.column("scope", width=70, anchor="center")

        self.tree_scroll = ttk.Scrollbar(self.left_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self._on_item_select)

        # Right Column: Memory Content Details
        self.right_frame = tk.Frame(self.paned, bg=PANEL_BG, padx=12, pady=12)
        self.paned.add(self.right_frame, minsize=260, stretch="always")

        self.detail_key = tk.Label(
            self.right_frame,
            text="Select a memory item to view details",
            font=FONT_BOLD,
            fg=TEXT_MAIN,
            bg=PANEL_BG,
            anchor="w",
        )
        self.detail_key.pack(fill=tk.X, pady=(0, 4))

        self.detail_meta = tk.Label(
            self.right_frame,
            text="",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=PANEL_BG,
            anchor="w",
        )
        self.detail_meta.pack(fill=tk.X, pady=(0, 8))

        self.val_text = tk.Text(
            self.right_frame,
            bg=CARD_BG,
            fg=TEXT_MAIN,
            font=FONT_CODE,
            relief=tk.FLAT,
            bd=0,
            wrap=tk.WORD,
            padx=10,
            pady=10,
            state=tk.DISABLED,
        )
        self.val_text.pack(fill=tk.BOTH, expand=True)

    def _refresh(self) -> None:
        """Fetch memories from controller."""
        self._memories = self.controller.get_memories()
        self._filter_memories()

    def _filter_memories(self) -> None:
        query = self.search_entry.get().strip().lower()
        self.tree.delete(*self.tree.get_children())

        for idx, item in enumerate(self._memories):
            key = str(item.get("key", ""))
            category = str(item.get("category", "general"))
            scope = str(item.get("scope", "persistent"))
            val = str(item.get("value", ""))

            if not query or (query in key.lower() or query in val.lower() or query in category.lower()):
                self.tree.insert("", tk.END, iid=str(idx), values=(key, category, scope))

    def _on_item_select(self, event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        idx = int(selection[0])
        if idx >= len(self._memories):
            return
        item = self._memories[idx]

        key = item.get("key", "Unknown")
        cat = item.get("category", "general")
        scope = item.get("scope", "persistent")
        conf = item.get("confidence", 1.0)
        val = item.get("value", "")

        self.detail_key.config(text=f"Key: {key}")
        self.detail_meta.config(text=f"Category: {cat} | Scope: {scope} | Confidence: {conf}")

        self.val_text.config(state=tk.NORMAL)
        self.val_text.delete("1.0", tk.END)
        self.val_text.insert(tk.END, str(val))
        self.val_text.config(state=tk.DISABLED)

    def _on_state_change(self, state: GUIState) -> None:
        # If view switched to MEMORY, refresh
        pass
