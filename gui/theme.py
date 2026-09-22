"""
Theme definitions, color tokens, and styling helpers for the CHARVIS Desktop GUI (Phase 15).
Provides a clean, modern dark theme by default, with accessible contrast and font scalings.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict

# Dark Theme Color Tokens
BG_DARK = "#18191c"          # Window main background
PANEL_BG = "#232428"         # Content panel background
SIDEBAR_BG = "#1e1f23"       # Navigation sidebar background
CARD_BG = "#2b2d31"          # Card / message bubble background
CARD_USER_BG = "#3b4252"     # User message bubble background
CARD_TOOL_BG = "#252b3b"     # Tool activity card background
INPUT_BG = "#313338"         # Text input box background

TEXT_MAIN = "#f2f3f5"        # Primary readable text
TEXT_MUTED = "#949ba4"       # Secondary / subtitle text
TEXT_DIM = "#6d7078"         # Timestamps and dim metadata
TEXT_USER = "#eceff4"        # User message text

ACCENT_BLUE = "#5865f2"      # Primary accent brand color
ACCENT_HOVER = "#4752c4"     # Button hover state
COLOR_SUCCESS = "#23a55a"    # Positive / completed state
COLOR_WARNING = "#f0b232"    # Warning / confirmation required state
COLOR_ERROR = "#f23f43"      # Error / denied / failed state
COLOR_INFO = "#5865f2"       # Info / neutral state

BORDER_COLOR = "#35373c"     # Primary borders
BORDER_SUBTLE = "#2f3136"    # Subtle dividers

# Fonts (Windows standard Segoe UI with fallback)
FONT_FAMILY = "Segoe UI"
FONT_TITLE = (FONT_FAMILY, 13, "bold")
FONT_HEADER = (FONT_FAMILY, 11, "bold")
FONT_BODY = (FONT_FAMILY, 10)
FONT_BODY_BOLD = (FONT_FAMILY, 10, "bold")
FONT_CAPTION = (FONT_FAMILY, 9)
FONT_CODE = ("Consolas", 9)

# Standardized aliases
TEXT_HINT = TEXT_DIM
ACCENT_PRIMARY = ACCENT_BLUE
ACCENT_SECONDARY = ACCENT_HOVER
ACCENT_SUCCESS = COLOR_SUCCESS
ACCENT_WARNING = COLOR_WARNING
ACCENT_DANGER = COLOR_ERROR
FONT_MAIN = FONT_BODY
FONT_BOLD = FONT_BODY_BOLD
FONT_SMALL = FONT_CAPTION

# Standardized Theme Dictionary
DARK_THEME: Dict[str, str] = {
    "bg_dark": BG_DARK,
    "panel_bg": PANEL_BG,
    "sidebar_bg": SIDEBAR_BG,
    "card_bg": CARD_BG,
    "card_user_bg": CARD_USER_BG,
    "card_tool_bg": CARD_TOOL_BG,
    "input_bg": INPUT_BG,
    "text_main": TEXT_MAIN,
    "text_muted": TEXT_MUTED,
    "text_dim": TEXT_DIM,
    "accent": ACCENT_BLUE,
    "accent_hover": ACCENT_HOVER,
    "success": COLOR_SUCCESS,
    "warning": COLOR_WARNING,
    "error": COLOR_ERROR,
    "border": BORDER_COLOR,
    "border_subtle": BORDER_SUBTLE,
}


def apply_theme(root: tk.Tk) -> ttk.Style:
    """
    Apply modern dark styling to Tkinter root and ttk widgets.
    """
    root.configure(bg=BG_DARK)

    style = ttk.Style(root)
    # Use 'clam' as the cross-platform modern base engine
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # Global widget styles
    style.configure(".", background=PANEL_BG, foreground=TEXT_MAIN, font=FONT_BODY)

    # Frame styles
    style.configure("TFrame", background=PANEL_BG)
    style.configure("Main.TFrame", background=BG_DARK)
    style.configure("Sidebar.TFrame", background=SIDEBAR_BG)
    style.configure("Card.TFrame", background=CARD_BG, relief="flat")
    style.configure("Input.TFrame", background=PANEL_BG)

    # Label styles
    style.configure("TLabel", background=PANEL_BG, foreground=TEXT_MAIN, font=FONT_BODY)
    style.configure("Sidebar.TLabel", background=SIDEBAR_BG, foreground=TEXT_MAIN, font=FONT_BODY)
    style.configure("SidebarTitle.TLabel", background=SIDEBAR_BG, foreground=TEXT_MAIN, font=FONT_TITLE)
    style.configure("Muted.TLabel", background=PANEL_BG, foreground=TEXT_MUTED, font=FONT_CAPTION)
    style.configure("SidebarMuted.TLabel", background=SIDEBAR_BG, foreground=TEXT_MUTED, font=FONT_CAPTION)
    style.configure("Header.TLabel", background=PANEL_BG, foreground=TEXT_MAIN, font=FONT_HEADER)
    style.configure("Card.TLabel", background=CARD_BG, foreground=TEXT_MAIN, font=FONT_BODY)

    # Button styles
    style.configure(
        "TButton",
        background=CARD_BG,
        foreground=TEXT_MAIN,
        font=FONT_BODY,
        borderwidth=1,
        relief="flat",
        padding=(10, 5),
    )
    style.map(
        "TButton",
        background=[("active", ACCENT_BLUE), ("disabled", BORDER_SUBTLE)],
        foreground=[("active", "#ffffff"), ("disabled", TEXT_DIM)],
    )

    style.configure(
        "Primary.TButton",
        background=ACCENT_BLUE,
        foreground="#ffffff",
        font=FONT_BODY_BOLD,
        borderwidth=0,
        padding=(12, 6),
    )
    style.map(
        "Primary.TButton",
        background=[("active", ACCENT_HOVER), ("disabled", BORDER_SUBTLE)],
        foreground=[("disabled", TEXT_DIM)],
    )

    style.configure(
        "Danger.TButton",
        background=COLOR_ERROR,
        foreground="#ffffff",
        font=FONT_BODY_BOLD,
        borderwidth=0,
        padding=(12, 6),
    )
    style.map("Danger.TButton", background=[("active", "#d83a3e")])

    style.configure(
        "Sidebar.TButton",
        background=SIDEBAR_BG,
        foreground=TEXT_MUTED,
        font=FONT_BODY_BOLD,
        borderwidth=0,
        padding=(12, 10),
        anchor="w",
    )
    style.map(
        "Sidebar.TButton",
        background=[("active", CARD_BG), ("selected", CARD_BG)],
        foreground=[("active", TEXT_MAIN), ("selected", TEXT_MAIN)],
    )

    # Progressbar
    style.configure(
        "TProgressbar",
        background=ACCENT_BLUE,
        troughcolor=CARD_BG,
        borderwidth=0,
        thickness=6,
    )

    # Scrollbar
    style.configure(
        "Vertical.TScrollbar",
        background=CARD_BG,
        troughcolor=PANEL_BG,
        borderwidth=0,
        arrowsize=12,
    )

    return style
