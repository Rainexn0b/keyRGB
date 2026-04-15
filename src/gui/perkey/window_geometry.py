from __future__ import annotations

import tkinter as tk

from src.gui.utils.window_geometry import compute_centered_window_geometry


_GEOMETRY_SYNC_ERRORS = (RuntimeError, tk.TclError, TypeError, ValueError)


def compute_perkey_editor_min_content_size(
    *,
    num_rows: int,
    num_cols: int,
    key_margin: int,
    key_size: int,
    key_gap: int,
    right_panel_width: int,
    wheel_size: int,
) -> tuple[int, int]:
    keyboard_w = (key_margin * 2) + (num_cols * key_size) + ((num_cols - 1) * key_gap)
    keyboard_h = (key_margin * 2) + (num_rows * key_size) + ((num_rows - 1) * key_gap)

    chrome_w = 16 * 2 + 16
    chrome_h = 16 * 2 + 80

    width_px = keyboard_w + right_panel_width + chrome_w
    # Right panel height includes the wheel + controls/buttons beneath it.
    # Keep a bit of slack so bottom buttons don't get clipped on common DPI/font combos.
    height_px = max(keyboard_h + chrome_h, wheel_size + 480)
    return int(width_px), int(height_px)


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

    w0, h0 = compute_perkey_editor_min_content_size(
        num_rows=num_rows,
        num_cols=num_cols,
        key_margin=key_margin,
        key_size=key_size,
        key_gap=key_gap,
        right_panel_width=right_panel_width,
        wheel_size=wheel_size,
    )

    screen_w = int(root.winfo_screenwidth())
    screen_h = int(root.winfo_screenheight())
    max_w = int(screen_w * 0.92)
    max_h = int(screen_h * 0.92)

    geometry = compute_centered_window_geometry(
        root,
        content_height_px=h0,
        content_width_px=w0,
        footer_height_px=0,
        chrome_padding_px=0,
        default_w=int(w0 * 1.5),
        default_h=int(h0 * 1.5),
        screen_ratio_cap=0.92,
    )

    root.geometry(geometry)
    root.minsize(min(w0, max_w), min(h0, max_h))


def fit_perkey_editor_geometry_to_content(
    root: tk.Tk,
    *,
    min_content_width_px: int,
    min_content_height_px: int,
) -> None:
    """Fit the per-key editor window to the real Tk-requested content size."""

    try:
        root.update_idletasks()

        requested_width = max(int(min_content_width_px), int(root.winfo_reqwidth()))
        measured_height = int(root.winfo_reqheight())
        requested_height = measured_height if measured_height > 0 else int(min_content_height_px)

        screen_w = int(root.winfo_screenwidth())
        screen_h = int(root.winfo_screenheight())
        max_w = int(screen_w * 0.92)
        max_h = int(screen_h * 0.92)

        geometry = compute_centered_window_geometry(
            root,
            content_height_px=requested_height,
            content_width_px=requested_width,
            footer_height_px=0,
            chrome_padding_px=0,
            default_w=requested_width,
            default_h=requested_height,
            screen_ratio_cap=0.92,
        )
        root.geometry(geometry)
        root.minsize(min(requested_width, max_w), min(requested_height, max_h))
    except _GEOMETRY_SYNC_ERRORS:
        return
