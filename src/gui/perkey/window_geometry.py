from __future__ import annotations

import tkinter as tk


def apply_perkey_editor_geometry(
    root: tk.Tk,
    *,
    num_rows: int,
    num_cols: int,
    key_margin: int,
    key_size: int,
    key_gap: int,
    right_panel_width: int,
    wheel_size: int,
) -> None:
    """Apply the initial window geometry for the per-key editor.

    This preserves the legacy sizing math from the original monolithic editor.
    """

    keyboard_w = (key_margin * 2) + (num_cols * key_size) + ((num_cols - 1) * key_gap)
    keyboard_h = (key_margin * 2) + (num_rows * key_size) + ((num_rows - 1) * key_gap)

    chrome_w = 16 * 2 + 16
    chrome_h = 16 * 2 + 80

    w0 = keyboard_w + right_panel_width + chrome_w
    h0 = max(keyboard_h + chrome_h, wheel_size + 420)

    screen_w = int(root.winfo_screenwidth())
    screen_h = int(root.winfo_screenheight())
    max_w = int(screen_w * 0.92)
    max_h = int(screen_h * 0.92)

    w = min(int(w0 * 1.5), max_w)
    h = min(int(h0 * 1.5), max_h)

    root.geometry(f"{w}x{h}")
    root.minsize(min(w0, max_w), min(h0, max_h))
