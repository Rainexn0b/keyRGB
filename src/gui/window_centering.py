from __future__ import annotations

import tkinter as tk


def center_window_on_screen(window: tk.Tk | tk.Toplevel) -> None:
    """Center a Tk window on screen after it has been sized via update_idletasks."""
    window.update_idletasks()
    x = (window.winfo_screenwidth() // 2) - (window.winfo_width() // 2)
    y = (window.winfo_screenheight() // 2) - (window.winfo_height() // 2)
    window.geometry(f"+{x}+{y}")
