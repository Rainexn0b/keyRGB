"""Profile UI actions: power-source policy + CRUD (activate/save/new/delete).

Extracted from ``profile_actions.py`` (WS1 / B1 slice 1).
"""

from __future__ import annotations

import logging

from src.core.profile import profiles
from src.gui.perkey.hardware import NUM_COLS, NUM_ROWS
from src.gui.perkey.ui._profile_actions_support import (
    _PerKeyProfileEditorProtocol,
    _refresh_layout_slot_controls_if_present,
    _select_slot_id_if_present,
    _sync_backdrop_ui_after_activation,
)

logger = logging.getLogger(__name__)

KEEP_CURRENT_PROFILE_LABEL = "Keep current profile"
_POWER_SOURCE_READ_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _facade():
    """Late import of profile_actions facade (lazy wrappers + guards)."""

    from src.gui.perkey.ui import profile_actions as facade

    return facade


def _configured_power_source_profile_names(editor: _PerKeyProfileEditorProtocol) -> list[str]:
    configured: list[str] = []
    config = getattr(editor, "config", None)
    for attr_name in ("ac_perkey_profile_name", "battery_perkey_profile_name"):
        value = str(getattr(config, attr_name, "") or "").strip()
        if value and value not in configured:
            configured.append(value)
    for var in (
        editor._ac_power_source_profile_var,
        editor._battery_power_source_profile_var,
    ):
        value = str(var.get() or "").strip()
        if value and value != KEEP_CURRENT_PROFILE_LABEL and value not in configured:
            configured.append(value)
    return configured


def power_source_profile_options(editor: _PerKeyProfileEditorProtocol) -> tuple[str, ...]:
    names = list(profiles.list_profiles())
    for configured_name in _configured_power_source_profile_names(editor):
        if configured_name not in names:
            names.append(configured_name)
    return (KEEP_CURRENT_PROFILE_LABEL, *names)


def _power_source_profile_selection(value: object) -> str:
    normalized = str(value or "").strip()
    return normalized or KEEP_CURRENT_PROFILE_LABEL


def _selected_power_source_profile_name(value: object) -> str | None:
    normalized = str(value or "").strip()
    if not normalized or normalized == KEEP_CURRENT_PROFILE_LABEL:
        return None
    return normalized


def _maybe_activate_current_power_source_profile_ui(
    editor: _PerKeyProfileEditorProtocol,
) -> tuple[str, str] | None:
    facade = _facade()
    try:
        on_ac = facade.read_on_ac_power()
    except _POWER_SOURCE_READ_ERRORS:
        return None

    if on_ac is None:
        return None

    source_label = "AC" if bool(on_ac) else "battery"
    desired_profile_name = _selected_power_source_profile_name(
        editor._ac_power_source_profile_var.get() if bool(on_ac) else editor._battery_power_source_profile_var.get()
    )
    if desired_profile_name is None or desired_profile_name == editor.profile_name:
        return None

    editor._profile_name_var.set(desired_profile_name)
    # Go through the facade so tests can monkeypatch profile_actions.activate_profile_ui.
    facade.activate_profile_ui(editor)
    return source_label, desired_profile_name


def sync_power_source_profile_policy_controls(editor: _PerKeyProfileEditorProtocol) -> None:
    options = power_source_profile_options(editor)
    config = getattr(editor, "config", None)
    ac_selection = _power_source_profile_selection(getattr(config, "ac_perkey_profile_name", None))
    battery_selection = _power_source_profile_selection(getattr(config, "battery_perkey_profile_name", None))

    editor._ac_power_source_profile_var.set(ac_selection)
    editor._battery_power_source_profile_var.set(battery_selection)

    for combo in (
        editor._ac_power_source_profile_combo,
        editor._battery_power_source_profile_combo,
    ):
        if combo is not None:
            combo.configure(values=options)


def save_power_source_profile_policy_ui(editor: _PerKeyProfileEditorProtocol) -> None:
    facade = _facade()
    editor.config.ac_perkey_profile_name = _selected_power_source_profile_name(
        editor._ac_power_source_profile_var.get()
    )
    editor.config.battery_perkey_profile_name = _selected_power_source_profile_name(
        editor._battery_power_source_profile_var.get()
    )
    activated_profile = _maybe_activate_current_power_source_profile_ui(editor)
    sync_power_source_profile_policy_controls(editor)
    if activated_profile is None:
        facade.set_status(editor, "Saved AC/battery lighting profile policy")
        return
    source_label, profile_name = activated_profile
    facade.set_status(
        editor, f"Saved AC/battery lighting profile policy and activated '{profile_name}' for {source_label}"
    )


def activate_profile_ui(editor: _PerKeyProfileEditorProtocol) -> None:
    facade = _facade()
    requested_name = editor._profile_name_var.get()
    if requested_name != editor.profile_name and not facade._guard_destructive_profile_action(
        editor, "activating another profile"
    ):
        return
    result = facade.activate_profile(
        requested_name,
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
    editor.secondary_lighting = result.secondary_lighting

    _sync_backdrop_ui_after_activation(editor, editor.profile_name, logger=logger)

    facade.ensure_full_map_ui(editor, num_rows=NUM_ROWS, num_cols=NUM_COLS)
    editor._commit(force=True)

    editor.overlay_controls.sync_vars_from_scope()
    if editor.lightbar_controls is not None:
        editor.lightbar_controls.sync_vars_from_editor()
    lighting_areas_panel = vars(editor).get("_lighting_areas_panel")
    if lighting_areas_panel is not None:
        lighting_areas_panel.sync_from_editor()
    _refresh_layout_slot_controls_if_present(editor)
    editor.canvas.redraw()
    facade._mark_saved_snapshot_if_supported(editor)
    facade.set_status(editor, facade.active_profile(editor.profile_name))

    selected_slot_id = editor.selected_slot_id
    slot_lookup = editor._slot_id_for_key_id
    if not (selected_slot_id and _select_slot_id_if_present(editor, selected_slot_id)) and editor.selected_key_id:
        resolved_slot_id = slot_lookup(editor.selected_key_id)
        facade.select_visible_identity(editor, slot_id=resolved_slot_id, key_id=editor.selected_key_id)


def save_profile_ui(editor: _PerKeyProfileEditorProtocol) -> None:
    facade = _facade()
    name = facade.save_profile(
        editor._profile_name_var.get(),
        config=editor.config,
        keymap=editor.keymap,
        layout_tweaks=editor.layout_tweaks,
        per_key_layout_tweaks=editor.per_key_layout_tweaks,
        lightbar_overlay=dict(editor.lightbar_overlay or {}),
        physical_layout=editor._physical_layout,
        layout_slot_overrides=editor.layout_slot_overrides,
        colors=editor.colors,
        secondary_lighting=getattr(editor, "secondary_lighting", None),
    )
    editor.profile_name = name
    editor._profile_name_var.set(name)
    sync_power_source_profile_policy_controls(editor)

    facade.ensure_full_map_ui(editor, num_rows=NUM_ROWS, num_cols=NUM_COLS)
    editor._commit(force=True)
    facade._mark_saved_snapshot_if_supported(editor)
    facade.set_status(editor, facade.saved_profile(editor.profile_name))


def new_profile_ui(editor: _PerKeyProfileEditorProtocol) -> None:
    """Create a new profile with a default name."""
    from tkinter import simpledialog

    facade = _facade()
    if not facade._guard_destructive_profile_action(editor, "creating another profile"):
        return

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
        facade.set_status(editor, "Lighting profile name cannot be empty")
        return

    if new_name in existing_profiles:
        facade.set_status(editor, f"Lighting profile '{new_name}' already exists")
        return

    name = facade.save_profile(
        new_name,
        config=editor.config,
        keymap=editor.keymap,
        layout_tweaks=editor.layout_tweaks,
        per_key_layout_tweaks=editor.per_key_layout_tweaks,
        lightbar_overlay=dict(editor.lightbar_overlay or {}),
        physical_layout=editor._physical_layout,
        layout_slot_overrides=editor.layout_slot_overrides,
        colors=editor.colors,
        secondary_lighting=getattr(editor, "secondary_lighting", None),
    )
    editor.profile_name = name
    editor._profile_name_var.set(name)
    editor._profiles_combo.configure(values=profiles.list_profiles())
    sync_power_source_profile_policy_controls(editor)

    facade.ensure_full_map_ui(editor, num_rows=NUM_ROWS, num_cols=NUM_COLS)
    editor._commit(force=True)
    facade._mark_saved_snapshot_if_supported(editor)
    facade.set_status(editor, f"Created lighting profile '{name}'")


def delete_profile_ui(editor: _PerKeyProfileEditorProtocol) -> None:
    facade = _facade()
    if not facade._guard_destructive_profile_action(editor, "deleting a profile"):
        return
    result = facade.delete_profile(editor._profile_name_var.get())
    if not result.deleted:
        if result.message:
            facade.set_status(editor, result.message)
        return

    editor.profile_name = result.active_profile
    editor._profile_name_var.set(result.active_profile)
    editor._profiles_combo.configure(values=profiles.list_profiles())
    sync_power_source_profile_policy_controls(editor)
    if callable(editor._activate_profile):
        editor._activate_profile()
    facade._mark_saved_snapshot_if_supported(editor)
    facade.set_status(editor, result.message)


def set_default_profile_ui(editor: _PerKeyProfileEditorProtocol) -> None:
    facade = _facade()
    name = profiles.set_default_profile(editor._profile_name_var.get())
    editor._profile_name_var.set(name)
    facade.set_status(editor, facade.default_profile_set(name))
