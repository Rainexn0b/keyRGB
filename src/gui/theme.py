from __future__ import annotations

import tkinter as tk
from tkinter import ttk


_BG_COLOR = "#2b2b2b"
_FG_COLOR = "#e0e0e0"


def apply_clam_dark_theme(
    root: tk.Misc,
    *,
    include_checkbuttons: bool = False,
    map_checkbutton_state: bool = False,
) -> tuple[str, str]:
    """Apply the common KeyRGB dark ttk theme.

    This centralizes styling so individual windows stay small and consistent.
    Returns (bg_color, fg_color).

    The goal is to preserve existing visuals; keep changes minimal.
    """

    style = ttk.Style()
    style.theme_use("clam")

    bg_color = _BG_COLOR
    fg_color = _FG_COLOR

    try:
        root.configure(bg=bg_color)
    except Exception:
        pass

    style.configure("TFrame", background=bg_color)
    style.configure("TLabel", background=bg_color, foreground=fg_color)
    style.configure("TButton", background="#404040", foreground=fg_color)
    style.map("TButton", background=[("active", "#505050")])

    if include_checkbuttons:
        style.configure("TCheckbutton", background=bg_color, foreground=fg_color)
        if map_checkbutton_state:
            style.map(
                "TCheckbutton",
                background=[("disabled", bg_color), ("active", bg_color)],
                foreground=[("disabled", "#777777"), ("!disabled", fg_color)],
            )

    return bg_color, fg_color
