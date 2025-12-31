from __future__ import annotations

from collections.abc import Callable
import json

import tkinter as tk
from tkinter import messagebox, ttk


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
    win.geometry("720x520")
    win.minsize(640, 420)

    frame = ttk.Frame(win, padding=12)
    frame.pack(fill="both", expand=True)

    info = ttk.Label(
        frame,
        text=(
            "Edit the profile JSON. Saving will update tccd's on-disk profiles and may prompt for admin permissions.\n"
            "Tip: keep the 'id' field unchanged."
        ),
        font=("Sans", 9),
    )
    info.pack(anchor="w", pady=(0, 8))

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

    def _save() -> None:
        raw = text.get("1.0", "end").strip()
        try:
            obj = json.loads(raw)
        except Exception as exc:
            messagebox.showerror("Invalid JSON", str(exc), parent=win)
            return
        if not isinstance(obj, dict):
            messagebox.showerror("Invalid JSON", "Top-level JSON must be an object", parent=win)
            return
        try:
            on_save(obj)
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc), parent=win)
            return
        win.destroy()
        on_saved()

    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right", padx=(0, 8))
