from __future__ import annotations

import os
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

    # Optional DPI/font robustness smoke-testing.
    # Tk uses a global scaling factor; allowing override makes it easy to validate
    # layout behavior at 125%/150% without changing system settings.
    scaling_raw = os.environ.get("KEYRGB_TK_SCALING")
    if scaling_raw:
        try:
            scaling = float(scaling_raw)
            if scaling > 0:
                root.tk.call("tk", "scaling", scaling)
        except Exception:
            pass

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

    # Container widgets
    style.configure("TLabelframe", background=bg_color, foreground=fg_color)
    style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color)
    style.configure("TRadiobutton", background=bg_color, foreground=fg_color)

    # Common input widgets (avoid bright default field backgrounds)
    field_bg = "#3a3a3a"
    style.configure("TEntry", fieldbackground=field_bg, foreground=fg_color)
    style.configure("TCombobox", fieldbackground=field_bg, foreground=fg_color)
    style.configure("TSpinbox", fieldbackground=field_bg, foreground=fg_color)

    # Sliders/scrollbars often have light troughs by default.
    style.configure("TScale", background=bg_color, troughcolor=field_bg)
    style.configure("TScrollbar", background=bg_color, troughcolor=field_bg)

    if include_checkbuttons:
        style.configure("TCheckbutton", background=bg_color, foreground=fg_color)
        if map_checkbutton_state:
            style.map(
                "TCheckbutton",
                background=[("disabled", bg_color), ("active", bg_color)],
                foreground=[("disabled", "#777777"), ("!disabled", fg_color)],
            )

    # Match disabled look across other selectable widgets.
    style.map(
        "TRadiobutton",
        background=[("disabled", bg_color), ("active", bg_color)],
        foreground=[("disabled", "#777777"), ("!disabled", fg_color)],
    )

    return bg_color, fg_color
