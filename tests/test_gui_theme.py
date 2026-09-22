"""
Unit tests for CHARVIS GUI Theme (Phase 15).
"""

import pytest
import tkinter as tk
from gui.theme import (
    BG_DARK, PANEL_BG, SIDEBAR_BG, CARD_BG, INPUT_BG,
    TEXT_MAIN, TEXT_MUTED, TEXT_HINT,
    ACCENT_PRIMARY, ACCENT_SECONDARY, ACCENT_SUCCESS, ACCENT_WARNING, ACCENT_DANGER,
    BORDER_COLOR, FONT_FAMILY, FONT_MAIN, FONT_BOLD, apply_theme
)


def test_theme_color_tokens():
    colors = [
        BG_DARK, PANEL_BG, SIDEBAR_BG, CARD_BG, INPUT_BG,
        TEXT_MAIN, TEXT_MUTED, TEXT_HINT,
        ACCENT_PRIMARY, ACCENT_SECONDARY, ACCENT_SUCCESS, ACCENT_WARNING, ACCENT_DANGER,
        BORDER_COLOR
    ]
    for c in colors:
        assert isinstance(c, str)
        assert c.startswith("#")
        assert len(c) in (4, 7)


def test_theme_fonts():
    assert isinstance(FONT_FAMILY, str)
    assert len(FONT_MAIN) == 2
    assert len(FONT_BOLD) == 3
    assert FONT_BOLD[2] == "bold"


def test_apply_theme_on_root():
    root = tk.Tk()
    root.withdraw()
    try:
        style = apply_theme(root)
        assert style is not None
        assert style.theme_use() == "clam"
    finally:
        root.destroy()
