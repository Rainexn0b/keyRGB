#!/usr/bin/env python3
"""TUXEDO Control Center power profiles GUI.

This is a small Tkinter window that talks to the TUXEDO Control Center daemon
(`tccd`) via system DBus.

It is intentionally minimal: list profiles, show active profile, and allow
temporary activation (matching the TCC tray behavior).
"""

from __future__ import annotations

import logging
import os
import sys
import json

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from src.core.logging_utils import log_throttled
from src.gui.window_icon import apply_keyrgb_window_icon
from src.gui.theme import apply_clam_dark_theme
from src.gui.window_centering import center_window_on_screen
from src.gui.tcc_profile_editor import open_profile_json_editor
import src.core.tcc_power_profiles as tcc_power_profiles


logger = logging.getLogger(__name__)


class TccProfilesGUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("KeyRGB - Power Profiles")
        apply_keyrgb_window_icon(self.root)
        self.root.geometry("760x560")
        self.root.minsize(720, 520)
        self.root.resizable(True, True)

        apply_clam_dark_theme(self.root)

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
            height=9,
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

        btn_row_top = ttk.Frame(main)
        btn_row_top.pack(fill="x", pady=(16, 0))

        self.btn_activate = ttk.Button(btn_row_top, text="Activate Temporarily", command=self._on_activate)
        self.btn_activate.pack(side="left")

        self.btn_refresh = ttk.Button(btn_row_top, text="Refresh", command=self._refresh)
        self.btn_refresh.pack(side="left", padx=(8, 0))

        self.btn_close = ttk.Button(btn_row_top, text="Close", command=self.root.destroy)
        self.btn_close.pack(side="right")

        btn_row_bottom = ttk.Frame(main)
        btn_row_bottom.pack(fill="x", pady=(8, 0))

        self.btn_new = ttk.Button(btn_row_bottom, text="New…", command=self._on_new)
        self.btn_new.pack(side="left")

        self.btn_duplicate = ttk.Button(btn_row_bottom, text="Duplicate…", command=self._on_duplicate)
        self.btn_duplicate.pack(side="left", padx=(8, 0))

        self.btn_rename = ttk.Button(btn_row_bottom, text="Rename…", command=self._on_rename)
        self.btn_rename.pack(side="left", padx=(8, 0))

        self.btn_edit = ttk.Button(btn_row_bottom, text="Edit…", command=self._on_edit)
        self.btn_edit.pack(side="left", padx=(8, 0))

        self.btn_delete = ttk.Button(btn_row_bottom, text="Delete", command=self._on_delete)
        self.btn_delete.pack(side="left", padx=(8, 0))

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

        center_window_on_screen(self.root)

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

        self._update_crud_buttons()

    def _update_crud_buttons(self) -> None:
        idx = self._selected_index()
        if idx is None or idx < 0 or idx >= len(self._profiles):
            for b in (self.btn_duplicate, self.btn_rename, self.btn_edit, self.btn_delete):
                b.configure(state="disabled")
            return

        pid = self._profiles[idx].id
        is_legacy = pid.startswith("__legacy_")
        is_default_custom = pid == "__default_custom_profile__"

        can_edit = (not is_legacy) and tcc_power_profiles.is_custom_profile_id(pid)
        can_delete = (not is_legacy) and (not is_default_custom) and (not pid.startswith("__"))

        self.btn_duplicate.configure(state="normal" if can_edit else "disabled")
        self.btn_rename.configure(state="normal" if can_edit else "disabled")
        self.btn_edit.configure(state="normal" if can_edit else "disabled")
        self.btn_delete.configure(state="normal" if can_delete else "disabled")

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
        self._update_crud_buttons()

    def _on_new(self) -> None:
        name = simpledialog.askstring("New Profile", "Profile name:", parent=self.root)
        if name is None:
            return
        name = name.strip()
        if not name:
            return
        try:
            tcc_power_profiles.create_custom_profile(name)
            self._set_status("✓ Created")
        except Exception as exc:
            messagebox.showerror("Create failed", str(exc))
            return
        self._refresh()

    def _on_duplicate(self) -> None:
        idx = self._selected_index()
        if idx is None or idx < 0 or idx >= len(self._profiles):
            return
        src = self._profiles[idx]
        if src.id.startswith("__legacy_"):
            return
        name = simpledialog.askstring("Duplicate Profile", "New profile name:", parent=self.root)
        if name is None:
            return
        name = name.strip()
        if not name:
            return
        try:
            tcc_power_profiles.duplicate_custom_profile(src.id, name)
            self._set_status("✓ Duplicated")
        except Exception as exc:
            messagebox.showerror("Duplicate failed", str(exc))
            return
        self._refresh()

    def _on_rename(self) -> None:
        idx = self._selected_index()
        if idx is None or idx < 0 or idx >= len(self._profiles):
            return
        prof = self._profiles[idx]
        if prof.id.startswith("__legacy_"):
            return
        name = simpledialog.askstring("Rename Profile", "New name:", initialvalue=prof.name, parent=self.root)
        if name is None:
            return
        name = name.strip()
        if not name:
            return
        try:
            tcc_power_profiles.rename_custom_profile(prof.id, name)
            self._set_status("✓ Renamed")
        except Exception as exc:
            messagebox.showerror("Rename failed", str(exc))
            return
        self._refresh()

    def _on_delete(self) -> None:
        idx = self._selected_index()
        if idx is None or idx < 0 or idx >= len(self._profiles):
            return
        prof = self._profiles[idx]
        if prof.id.startswith("__"):
            return
        if not messagebox.askyesno("Delete Profile", f"Delete '{prof.name}'?", parent=self.root):
            return
        try:
            tcc_power_profiles.delete_custom_profile(prof.id)
            self._set_status("✓ Deleted")
        except Exception as exc:
            messagebox.showerror("Delete failed", str(exc))
            return
        self._refresh()

    def _on_edit(self) -> None:
        idx = self._selected_index()
        if idx is None or idx < 0 or idx >= len(self._profiles):
            return
        prof = self._profiles[idx]
        if prof.id.startswith("__legacy_"):
            return

        payload = None
        try:
            payload = tcc_power_profiles.get_custom_profile_payload(prof.id)
        except Exception:
            payload = None

        if not isinstance(payload, dict):
            messagebox.showerror("Edit failed", "Could not load editable profile payload from tccd.")
            return

        open_profile_json_editor(
            self.root,
            profile_name=prof.name,
            payload=payload,
            on_save=lambda obj: tcc_power_profiles.update_custom_profile(prof.id, obj),
            on_saved=lambda: (self._set_status("✓ Saved"), self._refresh()),
        )

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
        except Exception as exc:
            log_throttled(
                logger,
                "tcc_profiles.refresh_after_activate",
                interval_s=60,
                level=logging.DEBUG,
                msg="Failed to refresh profiles after activation",
                exc=exc,
            )

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    TccProfilesGUI().run()


if __name__ == "__main__":
    main()
