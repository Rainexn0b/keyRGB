"""UI action helpers for the per-key editor.

These functions keep `editor.py` focused on UI wiring by grouping cohesive
profile-related behaviors.
"""

from __future__ import annotations

import logging
from tkinter import TclError
from typing import Any

from src.core.profile import profiles
from src.core.resources.defaults import (
    get_default_keymap,
    get_default_layout_tweaks,
    get_default_per_key_tweaks,
)
from src.core.resources.layouts import LAYOUT_CATALOG, get_layout_keys, resolve_layout_id

from .full_map import ensure_full_map_ui
from .selection import select_visible_identity
from ..hardware import NUM_COLS, NUM_ROWS
from ..profile_management import (
    activate_profile,
    delete_profile,
    keymap_cells_for,
    primary_cell,
    sanitize_keymap_cells,
    save_profile,
)
from .status import active_profile, default_profile_set, layout_defaults_reset, saved_profile, set_status


logger = logging.getLogger(__name__)

_LAYOUT_LABELS: dict[str, str] = {ld.layout_id: ld.label for ld in LAYOUT_CATALOG}
_BACKDROP_MODE_LABELS = {
    "none": "No backdrop",
    "builtin": "Built-in seed",
    "custom": "Custom image",
}
_BACKDROP_UI_ERRORS = (AttributeError, RuntimeError, TypeError, ValueError, TclError)


def _parse_default_keymap(layout_id: str) -> dict[str, tuple[tuple[int, int], ...]]:
    return sanitize_keymap_cells(
        profiles.normalize_keymap(get_default_keymap(layout_id), physical_layout=layout_id),
        num_rows=NUM_ROWS,
        num_cols=NUM_COLS,
    )


def reset_layout_defaults_ui(editor: Any) -> None:
    resolved_layout = resolve_layout_id(editor._physical_layout)
    slot_lookup = getattr(editor, "_slot_id_for_key_id", None)
    key_lookup = getattr(editor, "_key_id_for_slot_id", None)

    editor.keymap = _parse_default_keymap(editor._physical_layout)
    editor.layout_tweaks = get_default_layout_tweaks(editor._physical_layout)
    editor.per_key_layout_tweaks = profiles.normalize_layout_per_key_tweaks(
        get_default_per_key_tweaks(editor._physical_layout),
        physical_layout=editor._physical_layout,
    )
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
    visible_slot_ids = {str(getattr(key, "slot_id", None) or key.key_id) for key in visible_keys}
    selected_slot_id = getattr(editor, "selected_slot_id", None)
    current_slot_id = selected_slot_id
    if current_slot_id is None and callable(slot_lookup) and editor.selected_key_id in visible_key_ids:
        current_slot_id = slot_lookup(editor.selected_key_id)

    if current_slot_id in visible_slot_ids or editor.selected_key_id in visible_key_ids:
        editor.selected_slot_id = str(current_slot_id) if current_slot_id else None
        if editor.selected_slot_id and callable(key_lookup):
            resolved_key_id = key_lookup(editor.selected_slot_id)
            if resolved_key_id:
                editor.selected_key_id = str(resolved_key_id)
        editor.selected_cells = keymap_cells_for(
            editor.keymap,
            editor.selected_key_id,
            slot_id=getattr(editor, "selected_slot_id", None),
            physical_layout=getattr(editor, "_physical_layout", None),
        )
        editor.selected_cell = primary_cell(editor.selected_cells)
    else:
        editor.selected_key_id = None
        editor.selected_slot_id = None
        editor.selected_cells = ()
        editor.selected_cell = None

    if getattr(editor, "selected_slot_id", None) is None and editor.selected_key_id is None:
        for key in visible_keys:
            if keymap_cells_for(
                editor.keymap,
                str(key.key_id),
                slot_id=str(getattr(key, "slot_id", None) or key.key_id),
                physical_layout=getattr(editor, "_physical_layout", None),
            ):
                select_visible_identity(
                    editor,
                    slot_id=str(getattr(key, "slot_id", None) or key.key_id),
                    key_id=str(key.key_id),
                )
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
    backdrop_mode_var = getattr(editor, "_backdrop_mode_var", None)
    if backdrop_mode_var is not None:
        backdrop_mode = profiles.load_backdrop_mode(editor.profile_name)
        try:
            backdrop_mode_var.set(backdrop_mode)
            mode_combo = getattr(editor, "_backdrop_mode_combo", None)
            if mode_combo is not None:
                mode_combo.set(_BACKDROP_MODE_LABELS.get(backdrop_mode, "Built-in seed"))
        except _BACKDROP_UI_ERRORS:
            logger.warning("Failed to update per-profile backdrop mode UI during activation", exc_info=True)

    backdrop_transparency = getattr(editor, "backdrop_transparency", None)
    if backdrop_transparency is not None:
        try:
            backdrop_transparency.set(float(profiles.load_backdrop_transparency(editor.profile_name)))
        except _BACKDROP_UI_ERRORS:
            logger.warning("Failed to update per-profile backdrop transparency UI during activation", exc_info=True)

    if hasattr(editor.canvas, "reload_backdrop_image"):
        try:
            editor.canvas.reload_backdrop_image()
        except Exception:  # @quality-exception exception-transparency: optional per-profile backdrop image reload crosses Tk, image decode, and file/runtime seams and must remain non-fatal for profile activation
            logger.exception("Failed to reload per-profile backdrop image during activation")

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

    selected_slot_id = getattr(editor, "selected_slot_id", None)
    slot_lookup = getattr(editor, "_slot_id_for_key_id", None)
    if selected_slot_id and hasattr(editor, "select_slot_id"):
        editor.select_slot_id(selected_slot_id)
    elif editor.selected_key_id:
        resolved_slot_id = slot_lookup(editor.selected_key_id) if callable(slot_lookup) else None
        select_visible_identity(editor, slot_id=resolved_slot_id, key_id=editor.selected_key_id)


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
