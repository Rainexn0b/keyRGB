from __future__ import annotations

import tkinter as tk


def compute_centered_window_geometry(
    root: tk.Tk,
    *,
    content_height_px: int,
    content_width_px: int,
    footer_height_px: int,
    chrome_padding_px: int = 40,
    default_w: int = 1100,
    default_h: int = 850,
    screen_ratio_cap: float = 0.95,
) -> str:
    """Return a Tk geometry string '{w}x{h}+{x}+{y}' centered on screen.

    Inputs are expressed in pixels as reported by Tk (winfo_*).
    """

    screen_w = int(root.winfo_screenwidth())
    screen_h = int(root.winfo_screenheight())

    total_req_h = int(content_height_px) + int(footer_height_px) + int(chrome_padding_px)

    max_w = int(screen_w * float(screen_ratio_cap))
    max_h = int(screen_h * float(screen_ratio_cap))

    width = min(max(int(content_width_px), int(default_w)), max_w)
    height = min(max(int(total_req_h), int(default_h)), max_h)

    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2)

    return f"{width}x{height}+{x}+{y}"
