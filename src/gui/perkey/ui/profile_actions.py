"""UI action helpers for the per-key editor.

These functions keep `editor.py` focused on UI wiring by grouping cohesive
profile-related behaviors.
"""

from __future__ import annotations

from typing import Any

from src.core.profile import profiles
from src.core.resources.defaults import (
    get_default_keymap,
    get_default_layout_tweaks,
    get_default_per_key_tweaks,
)
from src.core.resources.layouts import LAYOUT_CATALOG, get_layout_keys, resolve_layout_id

from .full_map import ensure_full_map_ui
from ..hardware import NUM_COLS, NUM_ROWS
from ..profile_management import activate_profile, delete_profile, save_profile
from .status import active_profile, default_profile_set, layout_defaults_reset, saved_profile, set_status


_LAYOUT_LABELS: dict[str, str] = {ld.layout_id: ld.label for ld in LAYOUT_CATALOG}


def _parse_default_keymap(layout_id: str) -> dict[str, tuple[int, int]]:
    parsed: dict[str, tuple[int, int]] = {}
    for key_id, coord_text in get_default_keymap(layout_id).items():
        try:
            row_text, col_text = coord_text.split(",", 1)
            parsed[key_id] = (int(row_text.strip()), int(col_text.strip()))
        except (AttributeError, TypeError, ValueError):
            continue
    return parsed


def reset_layout_defaults_ui(editor: Any) -> None:
    resolved_layout = resolve_layout_id(editor._physical_layout)

    editor.keymap = _parse_default_keymap(editor._physical_layout)
    editor.layout_tweaks = get_default_layout_tweaks(editor._physical_layout)
    editor.per_key_layout_tweaks = get_default_per_key_tweaks(editor._physical_layout)
    editor.layout_slot_overrides = profiles.save_layout_slots(
        {},
        editor.profile_name,
        physical_layout=editor._physical_layout,
    )

    if hasattr(editor, "_refresh_layout_slot_controls"):
        editor._refresh_layout_slot_controls()

    visible_keys = get_layout_keys(
        editor._physical_layout, slot_overrides=getattr(editor, "layout_slot_overrides", None)
    )
    visible_key_ids = {key.key_id for key in visible_keys}

    if editor.selected_key_id in visible_key_ids:
        editor.selected_cell = editor.keymap.get(editor.selected_key_id)
    else:
        editor.selected_key_id = None
        editor.selected_cell = None

    if editor.selected_key_id is None:
        for key in visible_keys:
            if key.key_id in editor.keymap:
                editor.select_key_id(key.key_id)
                break

    editor.overlay_controls.sync_vars_from_scope()
    editor.canvas.redraw()
    set_status(editor, layout_defaults_reset(_LAYOUT_LABELS.get(resolved_layout, resolved_layout.upper())))


def activate_profile_ui(editor: Any) -> None:
    result = activate_profile(
        editor._profile_name_var.get(),
        config=editor.config,
        current_colors=dict(getattr(editor, "colors", {}) or {}),
        num_rows=NUM_ROWS,
        num_cols=NUM_COLS,
        physical_layout=editor._physical_layout,
    )
    editor.profile_name = result.name
    editor._profile_name_var.set(result.name)

    editor.keymap = result.keymap
    editor.layout_tweaks = result.layout_tweaks
    editor.per_key_layout_tweaks = result.per_key_layout_tweaks
    editor.colors = result.colors
    editor.layout_slot_overrides = dict(result.layout_slot_overrides)
    editor.lightbar_overlay = dict(result.lightbar_overlay)

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
    if getattr(editor, "lightbar_controls", None) is not None:
        editor.lightbar_controls.sync_vars_from_editor()
    if hasattr(editor, "_refresh_layout_slot_controls"):
        editor._refresh_layout_slot_controls()
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
        lightbar_overlay=dict(getattr(editor, "lightbar_overlay", {}) or {}),
        physical_layout=editor._physical_layout,
        layout_slot_overrides=getattr(editor, "layout_slot_overrides", {}),
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
        "New Lighting Profile",
        "Enter lighting profile name:",
        parent=editor.root,
        initialvalue="new_profile",
    )

    if not new_name:
        return  # User cancelled

    new_name = new_name.strip()
    if not new_name:
        set_status(editor, "Lighting profile name cannot be empty")
        return

    if new_name in existing_profiles:
        set_status(editor, f"Lighting profile '{new_name}' already exists")
        return

    # Create the new profile by saving current state
    name = save_profile(
        new_name,
        config=editor.config,
        keymap=editor.keymap,
        layout_tweaks=editor.layout_tweaks,
        per_key_layout_tweaks=editor.per_key_layout_tweaks,
        lightbar_overlay=dict(getattr(editor, "lightbar_overlay", {}) or {}),
        physical_layout=editor._physical_layout,
        layout_slot_overrides=getattr(editor, "layout_slot_overrides", {}),
        colors=editor.colors,
    )
    editor.profile_name = name
    editor._profile_name_var.set(name)
    editor._profiles_combo.configure(values=profiles.list_profiles())

    ensure_full_map_ui(editor, num_rows=NUM_ROWS, num_cols=NUM_COLS)
    editor._commit(force=True)
    set_status(editor, f"Created lighting profile '{name}'")


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
