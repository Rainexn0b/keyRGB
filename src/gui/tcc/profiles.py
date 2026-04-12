#!/usr/bin/env python3
"""TUXEDO Control Center power profiles GUI.

This is a small Tkinter window that talks to the TUXEDO Control Center daemon
(`tccd`) via system DBus.

It is intentionally minimal: list profiles, show active profile, and allow
temporary activation (matching the TCC tray behavior).
"""

from __future__ import annotations

import logging

import tkinter as tk
from tkinter import messagebox, ttk

from src.core.utils.logging_utils import log_throttled
from src.core.power.tcc_profiles.models import is_builtin_profile_id
from src.gui.utils.window_icon import apply_keyrgb_window_icon
from src.gui.theme import apply_clam_theme
from src.gui.utils.window_geometry import compute_centered_window_geometry
from src.gui.tcc._profile_actions import (
    create_profile,
    delete_profile,
    duplicate_profile,
    edit_profile,
    rename_profile,
)
import src.core.power.tcc_profiles as tcc_power_profiles


logger = logging.getLogger(__name__)


_SELECTION_INDEX_ERRORS = (IndexError, TypeError, ValueError)
_TCC_PROFILE_WRITE_ERRORS = (tcc_power_profiles.TccProfileWriteError,)
_TCC_RUNTIME_BOUNDARY_ERRORS = (OSError, RuntimeError, TypeError, ValueError)
_TCC_REFRESH_BOUNDARY_ERRORS = _TCC_RUNTIME_BOUNDARY_ERRORS + (AttributeError, tk.TclError)
_GEOMETRY_APPLY_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)
_WRAP_SYNC_ERRORS = (RuntimeError, tk.TclError, TypeError, ValueError)


class TccProfilesGUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("KeyRGB - Power Profiles")
        apply_keyrgb_window_icon(self.root)
        self.root.minsize(620, 460)
        self.root.resizable(True, True)

        apply_clam_theme(self.root)

        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        self._main_frame = main
        self._wrap_labels: list[object] = []

        title = ttk.Label(main, text="Power Profiles (TCC)", font=("Sans", 14, "bold"))
        title.pack(anchor="w", pady=(0, 8))

        desc = ttk.Label(
            main,
            text=(
                "These profiles are provided by the TUXEDO Control Center daemon (tccd).\n"
                "Activation here is temporary (like the TCC tray menu)."
            ),
            font=("Sans", 9),
            justify="left",
            wraplength=640,
        )
        desc.pack(anchor="w", pady=(0, 12))
        self._wrap_labels.append(desc)

        def _sync_wrap(_event=None) -> None:
            try:
                width = int(main.winfo_width())
                if width <= 1:
                    return
                wrap = max(240, width - 24)
                for label in self._wrap_labels:
                    label.configure(wraplength=wrap)
            except _WRAP_SYNC_ERRORS:
                return

        main.bind("<Configure>", _sync_wrap)
        self.root.after(0, _sync_wrap)

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

        details_frame = ttk.LabelFrame(main, text="Selected Profile", padding=12)
        details_frame.pack(fill="x", pady=(10, 0))

        self.profile_desc = ttk.Label(details_frame, text="", font=("Sans", 9), justify="left", wraplength=640)
        self.profile_desc.pack(fill="x", anchor="w")
        self._wrap_labels.append(self.profile_desc)

        btn_row_top = ttk.Frame(main)
        btn_row_top.pack(fill="x", pady=(16, 0))
        btn_row_top.columnconfigure(0, weight=3)
        btn_row_top.columnconfigure(1, weight=2)
        btn_row_top.columnconfigure(2, weight=2)

        self.btn_activate = ttk.Button(btn_row_top, text="Activate Temporarily", command=self._on_activate)
        self.btn_activate.grid(row=0, column=0, sticky="ew")

        self.btn_refresh = ttk.Button(btn_row_top, text="Refresh", command=self._refresh)
        self.btn_refresh.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.btn_close = ttk.Button(btn_row_top, text="Close", command=self.root.destroy)
        self.btn_close.grid(row=0, column=2, sticky="ew", padx=(8, 0))

        btn_row_bottom = ttk.Frame(main)
        btn_row_bottom.pack(fill="x", pady=(8, 0))
        for column in range(5):
            btn_row_bottom.columnconfigure(column, weight=1)

        self.btn_new = ttk.Button(btn_row_bottom, text="New…", command=self._on_new)
        self.btn_new.grid(row=0, column=0, sticky="ew")

        self.btn_duplicate = ttk.Button(btn_row_bottom, text="Duplicate…", command=self._on_duplicate)
        self.btn_duplicate.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.btn_rename = ttk.Button(btn_row_bottom, text="Rename…", command=self._on_rename)
        self.btn_rename.grid(row=0, column=2, sticky="ew", padx=(8, 0))

        self.btn_edit = ttk.Button(btn_row_bottom, text="Edit…", command=self._on_edit)
        self.btn_edit.grid(row=0, column=3, sticky="ew", padx=(8, 0))

        self.btn_delete = ttk.Button(btn_row_bottom, text="Delete", command=self._on_delete)
        self.btn_delete.grid(row=0, column=4, sticky="ew", padx=(8, 0))

        self.status = ttk.Label(main, text="", font=("Sans", 9), justify="left", wraplength=640)
        self.status.pack(fill="x", anchor="w", pady=(8, 0))
        self._wrap_labels.append(self.status)

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
        self._apply_geometry()
        self.root.after(50, self._apply_geometry)

    def _apply_geometry(self) -> None:
        try:
            self.root.update_idletasks()
            geometry = compute_centered_window_geometry(
                self.root,
                content_height_px=int(self._main_frame.winfo_reqheight()),
                content_width_px=int(self._main_frame.winfo_reqwidth()),
                footer_height_px=0,
                chrome_padding_px=36,
                default_w=760,
                default_h=560,
                screen_ratio_cap=0.95,
            )
            self.root.geometry(geometry)
        except _GEOMETRY_APPLY_ERRORS:
            return

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
            for b in (
                self.btn_duplicate,
                self.btn_rename,
                self.btn_edit,
                self.btn_delete,
            ):
                b.configure(state="disabled")
            return

        pid = self._profiles[idx].id
        is_builtin = is_builtin_profile_id(pid)
        is_default_custom = pid == "__default_custom_profile__"

        can_edit = (not is_builtin) and tcc_power_profiles.is_custom_profile_id(pid)
        can_delete = (not is_builtin) and (not is_default_custom) and (not pid.startswith("__"))

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
        except _SELECTION_INDEX_ERRORS:
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
        create_profile(
            self.root,
            logger=logger,
            set_status=self._set_status,
            refresh=self._refresh,
            write_errors=_TCC_PROFILE_WRITE_ERRORS,
        )

    def _on_duplicate(self) -> None:
        idx = self._selected_index()
        if idx is None or idx < 0 or idx >= len(self._profiles):
            return
        duplicate_profile(
            self.root,
            logger=logger,
            set_status=self._set_status,
            refresh=self._refresh,
            profile=self._profiles[idx],
            write_errors=_TCC_PROFILE_WRITE_ERRORS,
        )

    def _on_rename(self) -> None:
        idx = self._selected_index()
        if idx is None or idx < 0 or idx >= len(self._profiles):
            return
        rename_profile(
            self.root,
            logger=logger,
            set_status=self._set_status,
            refresh=self._refresh,
            profile=self._profiles[idx],
            write_errors=_TCC_PROFILE_WRITE_ERRORS,
        )

    def _on_delete(self) -> None:
        idx = self._selected_index()
        if idx is None or idx < 0 or idx >= len(self._profiles):
            return
        delete_profile(
            self.root,
            logger=logger,
            set_status=self._set_status,
            refresh=self._refresh,
            profile=self._profiles[idx],
            write_errors=_TCC_PROFILE_WRITE_ERRORS,
        )

    def _on_edit(self) -> None:
        idx = self._selected_index()
        if idx is None or idx < 0 or idx >= len(self._profiles):
            return
        edit_profile(
            self.root,
            logger=logger,
            set_status=self._set_status,
            refresh=self._refresh,
            profile=self._profiles[idx],
            write_errors=_TCC_PROFILE_WRITE_ERRORS,
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
        except _TCC_RUNTIME_BOUNDARY_ERRORS as exc:
            log_throttled(
                logger,
                "tcc_profiles.set_temp_profile_by_id",
                interval_s=60,
                level=logging.WARNING,
                msg="Failed to activate temporary TCC profile",
                exc=exc,
            )
            ok = False

        if ok:
            self._set_status("✓ Activated")
        else:
            self._set_status("✗ Activation failed")

        # Refresh so the active checkmark follows what tccd reports.
        try:
            self._refresh()
        except _TCC_REFRESH_BOUNDARY_ERRORS as exc:
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
