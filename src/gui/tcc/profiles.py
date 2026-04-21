#!/usr/bin/env python3
"""TUXEDO Control Center power profiles GUI.

This is a small Tkinter window that talks to the TUXEDO Control Center daemon
(`tccd`) via system DBus.

It is intentionally minimal: list profiles, show active profile, and allow
temporary activation (matching the TCC tray behavior).
"""

from __future__ import annotations

import logging

import src.core.power.tcc_profiles as tcc_power_profiles

from ._profiles_runtime_deps import TccProfilesRuntimeDeps as _runtime_deps


logger = logging.getLogger(__name__)

tk = _runtime_deps.tk
ttk = _runtime_deps.ttk
messagebox = _runtime_deps.messagebox
log_throttled = _runtime_deps.log_throttled
is_builtin_profile_id = _runtime_deps.is_builtin_profile_id
apply_keyrgb_window_icon = _runtime_deps.apply_keyrgb_window_icon
apply_clam_theme = _runtime_deps.apply_clam_theme
compute_centered_window_geometry = _runtime_deps.compute_centered_window_geometry
build_profiles_window = _runtime_deps.build_profiles_window
create_profile = _runtime_deps.create_profile
delete_profile = _runtime_deps.delete_profile
duplicate_profile = _runtime_deps.duplicate_profile
edit_profile = _runtime_deps.edit_profile
rename_profile = _runtime_deps.rename_profile


_SELECTION_INDEX_ERRORS = (IndexError, TypeError, ValueError)
_TCC_PROFILE_WRITE_ERRORS = (tcc_power_profiles.TccProfileWriteError,)
_TCC_RUNTIME_BOUNDARY_ERRORS = (OSError, RuntimeError, TypeError, ValueError)
_TCC_REFRESH_BOUNDARY_ERRORS = _TCC_RUNTIME_BOUNDARY_ERRORS + (AttributeError, tk.TclError)
_GEOMETRY_APPLY_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)
_WRAP_SYNC_ERRORS = (RuntimeError, tk.TclError, TypeError, ValueError)


class TccProfilesGUI:
    def __init__(self) -> None:
        build_profiles_window(
            self,
            tk_module=tk,
            ttk_module=ttk,
            apply_window_icon=apply_keyrgb_window_icon,
            apply_theme=apply_clam_theme,
            wrap_sync_errors=_WRAP_SYNC_ERRORS,
            on_select=self._on_select,
            on_activate=self._on_activate,
            on_refresh=self._refresh,
            on_new=self._on_new,
            on_duplicate=self._on_duplicate,
            on_rename=self._on_rename,
            on_edit=self._on_edit,
            on_delete=self._on_delete,
        )

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

    def _selected_profile(self) -> tcc_power_profiles.TccProfile | None:
        idx = self._selected_index()
        if idx is None or idx < 0 or idx >= len(self._profiles):
            return None
        return self._profiles[idx]

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
        profile = self._selected_profile()
        if profile is None:
            return
        duplicate_profile(
            self.root,
            logger=logger,
            set_status=self._set_status,
            refresh=self._refresh,
            profile=profile,
            write_errors=_TCC_PROFILE_WRITE_ERRORS,
        )

    def _on_rename(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        rename_profile(
            self.root,
            logger=logger,
            set_status=self._set_status,
            refresh=self._refresh,
            profile=profile,
            write_errors=_TCC_PROFILE_WRITE_ERRORS,
        )

    def _on_delete(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        delete_profile(
            self.root,
            logger=logger,
            set_status=self._set_status,
            refresh=self._refresh,
            profile=profile,
            write_errors=_TCC_PROFILE_WRITE_ERRORS,
        )

    def _on_edit(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        edit_profile(
            self.root,
            logger=logger,
            set_status=self._set_status,
            refresh=self._refresh,
            profile=profile,
            write_errors=_TCC_PROFILE_WRITE_ERRORS,
        )

    def _on_activate(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
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
