"""UI action helpers for the per-key editor.

These functions keep `editor.py` focused on UI wiring by grouping cohesive
profile-related behaviors.
"""

from __future__ import annotations

from typing import Any

from src.core.profile import profiles

from .full_map import ensure_full_map_ui
from ..hardware import NUM_COLS, NUM_ROWS
from ..profile_management import activate_profile, delete_profile, save_profile
from .status import active_profile, default_profile_set, saved_profile, set_status


def activate_profile_ui(editor: Any) -> None:
    result = activate_profile(
        editor._profile_name_var.get(),
        config=editor.config,
        current_colors=dict(getattr(editor, "colors", {}) or {}),
    )
    editor.profile_name = result.name
    editor._profile_name_var.set(result.name)

    editor.keymap = result.keymap
    editor.layout_tweaks = result.layout_tweaks
    editor.per_key_layout_tweaks = result.per_key_layout_tweaks
    editor.colors = result.colors

    # Reload per-profile backdrop state.
    try:
        editor.backdrop_transparency.set(float(profiles.load_backdrop_transparency(editor.profile_name)))
    except Exception:
        pass
    try:
        editor.canvas.reload_backdrop_image()
    except Exception:
        pass

    # Ensure we're applying a full map, then push it to hardware.
    ensure_full_map_ui(editor, num_rows=NUM_ROWS, num_cols=NUM_COLS)
    editor._commit(force=True)

    editor.overlay_controls.sync_vars_from_scope()
    editor.canvas.redraw()
    set_status(editor, active_profile(editor.profile_name))

    if editor.selected_key_id:
        editor.select_key_id(editor.selected_key_id)


def save_profile_ui(editor: Any) -> None:
    name = save_profile(
        editor._profile_name_var.get(),
        config=editor.config,
        keymap=editor.keymap,
        layout_tweaks=editor.layout_tweaks,
        per_key_layout_tweaks=editor.per_key_layout_tweaks,
        colors=editor.colors,
    )
    editor.profile_name = name
    editor._profile_name_var.set(name)

    # Persist + push the saved state immediately.
    ensure_full_map_ui(editor, num_rows=NUM_ROWS, num_cols=NUM_COLS)
    editor._commit(force=True)
    set_status(editor, saved_profile(editor.profile_name))


def new_profile_ui(editor: Any) -> None:
    """Create a new profile with a default name."""
    from tkinter import simpledialog

    existing_profiles = profiles.list_profiles()
    new_name = simpledialog.askstring(
        "New Profile", "Enter profile name:", parent=editor.root, initialvalue="new_profile"
    )

    if not new_name:
        return  # User cancelled

    new_name = new_name.strip()
    if not new_name:
        set_status(editor, "Profile name cannot be empty")
        return

    if new_name in existing_profiles:
        set_status(editor, f"Profile '{new_name}' already exists")
        return

    # Create the new profile by saving current state
    name = save_profile(
        new_name,
        config=editor.config,
        keymap=editor.keymap,
        layout_tweaks=editor.layout_tweaks,
        per_key_layout_tweaks=editor.per_key_layout_tweaks,
        colors=editor.colors,
    )
    editor.profile_name = name
    editor._profile_name_var.set(name)
    editor._profiles_combo.configure(values=profiles.list_profiles())

    ensure_full_map_ui(editor, num_rows=NUM_ROWS, num_cols=NUM_COLS)
    editor._commit(force=True)
    set_status(editor, f"Created profile '{name}'")


def delete_profile_ui(editor: Any) -> None:
    result = delete_profile(editor._profile_name_var.get())
    if not result.deleted:
        if result.message:
            set_status(editor, result.message)
        return

    editor.profile_name = result.active_profile
    editor._profile_name_var.set(result.active_profile)
    editor._profiles_combo.configure(values=profiles.list_profiles())
    set_status(editor, result.message)


def set_default_profile_ui(editor: Any) -> None:
    name = profiles.set_default_profile(editor._profile_name_var.get())
    editor._profile_name_var.set(name)
    set_status(editor, default_profile_set(name))
