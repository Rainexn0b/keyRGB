"""UI action helpers for the per-key editor.

These functions keep `editor.py` focused on UI wiring by grouping cohesive
profile-related behaviors.
"""

from __future__ import annotations

import logging

from src.core.profile import profiles
from ._profile_actions_support import (
    _PerKeyProfileEditorProtocol,
    _layout_labels,
    _parse_default_keymap,
    _refresh_layout_slot_controls_if_present,
    _select_slot_id_if_present,
    _sync_backdrop_ui_after_activation,
)
from ..hardware import NUM_COLS, NUM_ROWS

logger = logging.getLogger(__name__)


# Keep module-backed seams patchable while deferring heavier imports until use.
def get_default_keymap(layout_id: str):
    from src.core.resources.defaults import get_default_keymap as _get_default_keymap

    return _get_default_keymap(layout_id)


def get_default_layout_tweaks(layout_id: str):
    from src.core.resources.defaults import get_default_layout_tweaks as _get_default_layout_tweaks

    return _get_default_layout_tweaks(layout_id)


def get_default_per_key_tweaks(layout_id: str):
    from src.core.resources.defaults import get_default_per_key_tweaks as _get_default_per_key_tweaks

    return _get_default_per_key_tweaks(layout_id)


def get_layout_keys(*args, **kwargs):
    from src.core.resources.layouts import get_layout_keys as _get_layout_keys

    return _get_layout_keys(*args, **kwargs)


def resolve_layout_id(*args, **kwargs):
    from src.core.resources.layouts import resolve_layout_id as _resolve_layout_id

    return _resolve_layout_id(*args, **kwargs)


def ensure_full_map_ui(*args, **kwargs):
    from .full_map import ensure_full_map_ui as _ensure_full_map_ui

    return _ensure_full_map_ui(*args, **kwargs)


def select_visible_identity(*args, **kwargs):
    from .selection import select_visible_identity as _select_visible_identity

    return _select_visible_identity(*args, **kwargs)


def active_profile(*args, **kwargs):
    from .status import active_profile as _active_profile

    return _active_profile(*args, **kwargs)


def default_profile_set(*args, **kwargs):
    from .status import default_profile_set as _default_profile_set

    return _default_profile_set(*args, **kwargs)


def layout_defaults_reset(*args, **kwargs):
    from .status import layout_defaults_reset as _layout_defaults_reset

    return _layout_defaults_reset(*args, **kwargs)


def saved_profile(*args, **kwargs):
    from .status import saved_profile as _saved_profile

    return _saved_profile(*args, **kwargs)


def set_status(*args, **kwargs):
    from .status import set_status as _set_status

    return _set_status(*args, **kwargs)


def activate_profile(*args, **kwargs):
    from ..profile_management import activate_profile as _activate_profile

    return _activate_profile(*args, **kwargs)


def delete_profile(*args, **kwargs):
    from ..profile_management import delete_profile as _delete_profile

    return _delete_profile(*args, **kwargs)


def keymap_cells_for(*args, **kwargs):
    from ..profile_management import keymap_cells_for as _keymap_cells_for

    return _keymap_cells_for(*args, **kwargs)


def primary_cell(*args, **kwargs):
    from ..profile_management import primary_cell as _primary_cell

    return _primary_cell(*args, **kwargs)


def sanitize_keymap_cells(*args, **kwargs):
    from ..profile_management import sanitize_keymap_cells as _sanitize_keymap_cells

    return _sanitize_keymap_cells(*args, **kwargs)


def save_profile(*args, **kwargs):
    from ..profile_management import save_profile as _save_profile

    return _save_profile(*args, **kwargs)


def reset_layout_defaults_ui(editor: _PerKeyProfileEditorProtocol) -> None:
    resolved_layout = resolve_layout_id(editor._physical_layout)
    slot_lookup = editor._slot_id_for_key_id
    key_lookup = editor._key_id_for_slot_id

    editor.keymap = _parse_default_keymap(editor._physical_layout, get_default_keymap)
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

    _refresh_layout_slot_controls_if_present(editor)

    visible_keys = get_layout_keys(editor._physical_layout, slot_overrides=editor.layout_slot_overrides)
    visible_key_ids = {key.key_id for key in visible_keys}
    visible_slot_ids = {str(getattr(key, "slot_id", None) or key.key_id) for key in visible_keys}
    current_slot_id = editor.selected_slot_id
    if current_slot_id is None and editor.selected_key_id in visible_key_ids:
        current_slot_id = slot_lookup(editor.selected_key_id)

    if current_slot_id in visible_slot_ids or editor.selected_key_id in visible_key_ids:
        editor.selected_slot_id = str(current_slot_id) if current_slot_id else None
        if editor.selected_slot_id:
            resolved_key_id = key_lookup(editor.selected_slot_id)
            if resolved_key_id:
                editor.selected_key_id = str(resolved_key_id)
        editor.selected_cells = keymap_cells_for(
            editor.keymap,
            editor.selected_key_id,
            slot_id=editor.selected_slot_id,
            physical_layout=editor._physical_layout,
        )
        editor.selected_cell = primary_cell(editor.selected_cells)
    else:
        editor.selected_key_id = None
        editor.selected_slot_id = None
        editor.selected_cells = ()
        editor.selected_cell = None

    if editor.selected_slot_id is None and editor.selected_key_id is None:
        for key in visible_keys:
            if keymap_cells_for(
                editor.keymap,
                str(key.key_id),
                slot_id=str(getattr(key, "slot_id", None) or key.key_id),
                physical_layout=editor._physical_layout,
            ):
                select_visible_identity(
                    editor,
                    slot_id=str(getattr(key, "slot_id", None) or key.key_id),
                    key_id=str(key.key_id),
                )
                break

    editor.overlay_controls.sync_vars_from_scope()
    editor.canvas.redraw()
    set_status(editor, layout_defaults_reset(_layout_labels().get(resolved_layout, resolved_layout.upper())))


def activate_profile_ui(editor: _PerKeyProfileEditorProtocol) -> None:
    result = activate_profile(
        editor._profile_name_var.get(),
        config=editor.config,
        current_colors=dict(editor.colors or {}),
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

    _sync_backdrop_ui_after_activation(editor, editor.profile_name, logger=logger)

    ensure_full_map_ui(editor, num_rows=NUM_ROWS, num_cols=NUM_COLS)
    editor._commit(force=True)

    editor.overlay_controls.sync_vars_from_scope()
    if editor.lightbar_controls is not None:
        editor.lightbar_controls.sync_vars_from_editor()
    _refresh_layout_slot_controls_if_present(editor)
    editor.canvas.redraw()
    set_status(editor, active_profile(editor.profile_name))

    selected_slot_id = editor.selected_slot_id
    slot_lookup = editor._slot_id_for_key_id
    if not (selected_slot_id and _select_slot_id_if_present(editor, selected_slot_id)) and editor.selected_key_id:
        resolved_slot_id = slot_lookup(editor.selected_key_id)
        select_visible_identity(editor, slot_id=resolved_slot_id, key_id=editor.selected_key_id)


def save_profile_ui(editor: _PerKeyProfileEditorProtocol) -> None:
    name = save_profile(
        editor._profile_name_var.get(),
        config=editor.config,
        keymap=editor.keymap,
        layout_tweaks=editor.layout_tweaks,
        per_key_layout_tweaks=editor.per_key_layout_tweaks,
        lightbar_overlay=dict(editor.lightbar_overlay or {}),
        physical_layout=editor._physical_layout,
        layout_slot_overrides=editor.layout_slot_overrides,
        colors=editor.colors,
    )
    editor.profile_name = name
    editor._profile_name_var.set(name)

    ensure_full_map_ui(editor, num_rows=NUM_ROWS, num_cols=NUM_COLS)
    editor._commit(force=True)
    set_status(editor, saved_profile(editor.profile_name))


def new_profile_ui(editor: _PerKeyProfileEditorProtocol) -> None:
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
        return

    new_name = new_name.strip()
    if not new_name:
        set_status(editor, "Lighting profile name cannot be empty")
        return

    if new_name in existing_profiles:
        set_status(editor, f"Lighting profile '{new_name}' already exists")
        return

    name = save_profile(
        new_name,
        config=editor.config,
        keymap=editor.keymap,
        layout_tweaks=editor.layout_tweaks,
        per_key_layout_tweaks=editor.per_key_layout_tweaks,
        lightbar_overlay=dict(editor.lightbar_overlay or {}),
        physical_layout=editor._physical_layout,
        layout_slot_overrides=editor.layout_slot_overrides,
        colors=editor.colors,
    )
    editor.profile_name = name
    editor._profile_name_var.set(name)
    editor._profiles_combo.configure(values=profiles.list_profiles())

    ensure_full_map_ui(editor, num_rows=NUM_ROWS, num_cols=NUM_COLS)
    editor._commit(force=True)
    set_status(editor, f"Created lighting profile '{name}'")


def delete_profile_ui(editor: _PerKeyProfileEditorProtocol) -> None:
    result = delete_profile(editor._profile_name_var.get())
    if not result.deleted:
        if result.message:
            set_status(editor, result.message)
        return

    editor.profile_name = result.active_profile
    editor._profile_name_var.set(result.active_profile)
    editor._profiles_combo.configure(values=profiles.list_profiles())
    set_status(editor, result.message)


def set_default_profile_ui(editor: _PerKeyProfileEditorProtocol) -> None:
    name = profiles.set_default_profile(editor._profile_name_var.get())
    editor._profile_name_var.set(name)
    set_status(editor, default_profile_set(name))
