#!/usr/bin/env python3
"""TUXEDO Control Center power profiles GUI.

This is a small Tkinter window that talks to the TUXEDO Control Center daemon
(`tccd`) via system DBus.

It is intentionally minimal: list profiles, show active profile, and allow
temporary activation (matching the TCC tray behavior).
"""

from __future__ import annotations

import os
import sys

import tkinter as tk
from tkinter import messagebox, ttk

try:
    from src.core import tcc_power_profiles
except Exception:
    # Fallback for direct execution (e.g. `python src/gui/tcc_profiles.py`).
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from src.core import tcc_power_profiles


class TccProfilesGUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("KeyRGB - Power Profiles")
        self.root.geometry("520x360")
        self.root.resizable(False, False)

        style = ttk.Style()
        style.theme_use("clam")

        bg_color = "#2b2b2b"
        fg_color = "#e0e0e0"

        self.root.configure(bg=bg_color)
        style.configure("TFrame", background=bg_color)
        style.configure("TLabel", background=bg_color, foreground=fg_color)
        style.configure("TButton", background="#404040", foreground=fg_color)
        style.map("TButton", background=[("active", "#505050")])

        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)

        title = ttk.Label(main, text="Power Profiles (TCC)", font=("Sans", 14, "bold"))
        title.pack(anchor="w", pady=(0, 8))

        desc = ttk.Label(
            main,
            text=(
                "These profiles are provided by the TUXEDO Control Center daemon (tccd).\n"
                "Activation here is temporary (like the TCC tray menu)."
            ),
            font=("Sans", 9),
        )
        desc.pack(anchor="w", pady=(0, 12))

        list_frame = ttk.Frame(main)
        list_frame.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(
            list_frame,
            height=10,
            activestyle="dotbox",
            exportselection=False,
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scrollbar.set)

        self.profile_desc = ttk.Label(main, text="", font=("Sans", 9))
        self.profile_desc.pack(anchor="w", pady=(10, 0))

        btn_row = ttk.Frame(main)
        btn_row.pack(fill="x", pady=(16, 0))

        self.btn_activate = ttk.Button(btn_row, text="Activate Temporarily", command=self._on_activate)
        self.btn_activate.pack(side="left")

        self.btn_refresh = ttk.Button(btn_row, text="Refresh", command=self._refresh)
        self.btn_refresh.pack(side="left", padx=(8, 0))

        self.btn_close = ttk.Button(btn_row, text="Close", command=self.root.destroy)
        self.btn_close.pack(side="right")

        self.status = ttk.Label(main, text="", font=("Sans", 9))
        self.status.pack(anchor="w", pady=(8, 0))

        self._profiles: list[tcc_power_profiles.TccProfile] = []

        if not tcc_power_profiles.is_tccd_available():
            messagebox.showerror(
                "TCC daemon not available",
                "Could not talk to the TUXEDO Control Center daemon (tccd) over DBus.\n\n"
                "Make sure the backend is installed and running (system service), then try again.",
            )
            self.root.after(0, self.root.destroy)
            return

        self._refresh()

        # Center window.
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (self.root.winfo_width() // 2)
        y = (self.root.winfo_screenheight() // 2) - (self.root.winfo_height() // 2)
        self.root.geometry(f"+{x}+{y}")

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)
        if text:
            self.root.after(2000, lambda: self.status.configure(text=""))

    def _refresh(self) -> None:
        self.listbox.delete(0, tk.END)
        self._profiles = list(tcc_power_profiles.list_profiles() or [])
        active = tcc_power_profiles.get_active_profile()

        active_index: int | None = None
        for idx, prof in enumerate(self._profiles):
            label = prof.name
            if active is not None and active.id == prof.id:
                label = f"✓ {label}"
                active_index = idx
            self.listbox.insert(tk.END, label)

        if self._profiles:
            if active_index is None:
                active_index = 0
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(active_index)
            self.listbox.activate(active_index)
            self.listbox.see(active_index)
            self._update_desc(active_index)
            self.btn_activate.configure(state="normal")
        else:
            self.profile_desc.configure(text="No profiles returned by tccd.")
            self.btn_activate.configure(state="disabled")

    def _selected_index(self) -> int | None:
        sel = self.listbox.curselection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def _update_desc(self, index: int) -> None:
        if index < 0 or index >= len(self._profiles):
            self.profile_desc.configure(text="")
            return
        p = self._profiles[index]
        text = p.description.strip() if p.description else ""
        if text:
            self.profile_desc.configure(text=text)
        else:
            self.profile_desc.configure(text="")

    def _on_select(self, _evt=None) -> None:
        idx = self._selected_index()
        if idx is None:
            self.profile_desc.configure(text="")
            return
        self._update_desc(idx)

    def _on_activate(self) -> None:
        idx = self._selected_index()
        if idx is None:
            return
        if idx < 0 or idx >= len(self._profiles):
            return

        profile = self._profiles[idx]
        ok = False
        try:
            ok = tcc_power_profiles.set_temp_profile_by_id(profile.id)
        except Exception:
            ok = False

        if ok:
            self._set_status("✓ Activated")
        else:
            self._set_status("✗ Activation failed")

        # Refresh so the active checkmark follows what tccd reports.
        try:
            self._refresh()
        except Exception:
            pass

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    TccProfilesGUI().run()


if __name__ == "__main__":
    main()
