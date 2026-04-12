from __future__ import annotations

from collections.abc import Callable
import json
import logging

import tkinter as tk
from tkinter import messagebox, ttk

from src.core.utils.logging_utils import log_throttled
from src.gui.utils.window_geometry import compute_centered_window_geometry


logger = logging.getLogger(__name__)
_PROFILE_SAVE_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_EDITOR_GEOMETRY_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)


def open_profile_json_editor(
    parent: tk.Misc,
    *,
    profile_name: str,
    payload: dict,
    on_save: Callable[[dict], None],
    on_saved: Callable[[], None],
) -> None:
    win = tk.Toplevel(parent)
    win.title(f"Edit Profile - {profile_name}")
    win.minsize(560, 360)

    frame = ttk.Frame(win, padding=12)
    frame.pack(fill="both", expand=True)

    info = ttk.Label(
        frame,
        text=(
            "Edit the profile JSON. Saving will update tccd's on-disk profiles and may prompt for admin permissions.\n"
            "Tip: keep the 'id' field unchanged."
        ),
        font=("Sans", 9),
        justify="left",
        wraplength=640,
    )
    info.pack(anchor="w", pady=(0, 8))

    def _sync_info_wrap(_event=None) -> None:
        try:
            width = int(frame.winfo_width())
            if width <= 1:
                return
            info.configure(wraplength=max(240, width - 24))
        except _EDITOR_GEOMETRY_ERRORS:
            return

    frame.bind("<Configure>", _sync_info_wrap)
    win.after(0, _sync_info_wrap)

    text = tk.Text(frame, wrap="none", height=18)
    text.pack(fill="both", expand=True)

    yscroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    yscroll.place(in_=text, relx=1.0, rely=0, relheight=1.0, anchor="ne")
    text.configure(yscrollcommand=yscroll.set)

    xscroll = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
    xscroll.pack(fill="x")
    text.configure(xscrollcommand=xscroll.set)

    text.insert("1.0", json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    btns = ttk.Frame(frame)
    btns.pack(fill="x", pady=(10, 0))

    try:
        win.update_idletasks()
        win.geometry(
            compute_centered_window_geometry(
                win,
                content_height_px=int(frame.winfo_reqheight()),
                content_width_px=int(frame.winfo_reqwidth()),
                footer_height_px=0,
                chrome_padding_px=36,
                default_w=720,
                default_h=520,
                screen_ratio_cap=0.95,
            )
        )
    except _EDITOR_GEOMETRY_ERRORS:
        pass

    def _save() -> None:
        raw = text.get("1.0", "end").strip()
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            messagebox.showerror("Invalid JSON", str(exc), parent=win)
            return
        if not isinstance(obj, dict):
            messagebox.showerror("Invalid JSON", "Top-level JSON must be an object", parent=win)
            return
        try:
            on_save(obj)
        except _PROFILE_SAVE_ERRORS as exc:
            log_throttled(
                logger,
                "tcc_profile_editor.on_save",
                interval_s=60,
                level=logging.WARNING,
                msg="Failed to save edited TCC profile JSON",
                exc=exc,
            )
            messagebox.showerror("Save failed", str(exc), parent=win)
            return
        win.destroy()
        on_saved()

    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right", padx=(0, 8))
