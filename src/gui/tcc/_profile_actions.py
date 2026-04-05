from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import tkinter as tk
from tkinter import messagebox, simpledialog

from src.core.utils.logging_utils import log_throttled
from src.core.power.tcc_profiles.models import is_builtin_profile_id
from src.gui.tcc.profile_editor import open_profile_json_editor
import src.core.power.tcc_profiles as tcc_power_profiles


def create_profile(
    root: tk.Misc,
    *,
    logger: logging.Logger,
    set_status: Callable[[str], None],
    refresh: Callable[[], None],
    write_errors: tuple[type[BaseException], ...],
) -> None:
    name = simpledialog.askstring("New Profile", "Profile name:", parent=root)
    if name is None:
        return
    name = name.strip()
    if not name:
        return
    try:
        tcc_power_profiles.create_custom_profile(name)
        set_status("✓ Created")
    except write_errors as exc:
        log_throttled(
            logger,
            "tcc_profiles.create_custom_profile",
            interval_s=60,
            level=logging.WARNING,
            msg="Failed to create TCC custom profile",
            exc=exc,
        )
        messagebox.showerror("Create failed", str(exc))
        return
    refresh()


def duplicate_profile(
    root: tk.Misc,
    *,
    logger: logging.Logger,
    set_status: Callable[[str], None],
    refresh: Callable[[], None],
    profile: tcc_power_profiles.TccProfile,
    write_errors: tuple[type[BaseException], ...],
) -> None:
    if is_builtin_profile_id(profile.id):
        return
    name = simpledialog.askstring("Duplicate Profile", "New profile name:", parent=root)
    if name is None:
        return
    name = name.strip()
    if not name:
        return
    try:
        tcc_power_profiles.duplicate_custom_profile(profile.id, name)
        set_status("✓ Duplicated")
    except write_errors as exc:
        log_throttled(
            logger,
            "tcc_profiles.duplicate_custom_profile",
            interval_s=60,
            level=logging.WARNING,
            msg="Failed to duplicate TCC custom profile",
            exc=exc,
        )
        messagebox.showerror("Duplicate failed", str(exc))
        return
    refresh()


def rename_profile(
    root: tk.Misc,
    *,
    logger: logging.Logger,
    set_status: Callable[[str], None],
    refresh: Callable[[], None],
    profile: tcc_power_profiles.TccProfile,
    write_errors: tuple[type[BaseException], ...],
) -> None:
    if is_builtin_profile_id(profile.id):
        return
    name = simpledialog.askstring("Rename Profile", "New name:", initialvalue=profile.name, parent=root)
    if name is None:
        return
    name = name.strip()
    if not name:
        return
    try:
        tcc_power_profiles.rename_custom_profile(profile.id, name)
        set_status("✓ Renamed")
    except write_errors as exc:
        log_throttled(
            logger,
            "tcc_profiles.rename_custom_profile",
            interval_s=60,
            level=logging.WARNING,
            msg="Failed to rename TCC custom profile",
            exc=exc,
        )
        messagebox.showerror("Rename failed", str(exc))
        return
    refresh()


def delete_profile(
    root: tk.Misc,
    *,
    logger: logging.Logger,
    set_status: Callable[[str], None],
    refresh: Callable[[], None],
    profile: tcc_power_profiles.TccProfile,
    write_errors: tuple[type[BaseException], ...],
) -> None:
    if profile.id.startswith("__"):
        return
    if not messagebox.askyesno("Delete Profile", f"Delete '{profile.name}'?", parent=root):
        return
    try:
        tcc_power_profiles.delete_custom_profile(profile.id)
        set_status("✓ Deleted")
    except write_errors as exc:
        log_throttled(
            logger,
            "tcc_profiles.delete_custom_profile",
            interval_s=60,
            level=logging.WARNING,
            msg="Failed to delete TCC custom profile",
            exc=exc,
        )
        messagebox.showerror("Delete failed", str(exc))
        return
    refresh()


def edit_profile(
    root: tk.Misc,
    *,
    logger: logging.Logger,
    set_status: Callable[[str], None],
    refresh: Callable[[], None],
    profile: tcc_power_profiles.TccProfile,
    write_errors: tuple[type[BaseException], ...],
) -> None:
    if is_builtin_profile_id(profile.id):
        return

    payload: dict[str, Any] | None = None
    try:
        payload = tcc_power_profiles.get_custom_profile_payload(profile.id)
    except write_errors as exc:
        log_throttled(
            logger,
            "tcc_profiles.get_custom_profile_payload",
            interval_s=60,
            level=logging.WARNING,
            msg="Failed to load editable TCC profile payload",
            exc=exc,
        )
        payload = None

    if not isinstance(payload, dict):
        messagebox.showerror("Edit failed", "Could not load editable profile payload from tccd.")
        return

    open_profile_json_editor(
        root,
        profile_name=profile.name,
        payload=payload,
        on_save=lambda obj: tcc_power_profiles.update_custom_profile(profile.id, obj),
        on_saved=lambda: (set_status("✓ Saved"), refresh()),  # type: ignore[arg-type, func-returns-value]
    )
