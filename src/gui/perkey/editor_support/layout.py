from __future__ import annotations

from typing import Any, Callable

from src.core.profile import profiles
from src.core.resources.layout_legends import load_layout_legend_pack, resolve_layout_legend_pack_id
from src.core.resources.layout_slots import get_layout_slot_states

from ..profile_management import keymap_cells_for
from ..ui.layout_slots import refresh_layout_slots_ui
from ..ui.status import layout_slot_label_updated, layout_slot_visibility_updated, set_status


_LIGHTBAR_DISCOVERY_ERRORS = (AttributeError, ImportError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _layout_setup_controls_or_none(app: Any) -> Any | None:
    try:
        return app._layout_setup_controls
    except AttributeError:
        return None


def _refresh_legend_pack_choices_or_none(controls: Any) -> Callable[[], object] | None:
    if controls is None:
        return None
    try:
        refresh_choices = controls.refresh_legend_pack_choices
    except AttributeError:
        return None
    if not callable(refresh_choices):
        return None
    return refresh_choices


def _lightbar_controls_or_none(app: Any) -> Any | None:
    try:
        return app.lightbar_controls
    except AttributeError:
        return None


def normalize_layout_legend_pack(layout_id: str, legend_pack_id: str | None) -> str:
    requested = str(legend_pack_id or "auto").strip().lower()
    if not requested or requested == "auto":
        return "auto"

    pack = load_layout_legend_pack(requested)
    if not pack:
        return "auto"

    resolved_pack_layout = str(pack.get("layout_id") or layout_id).strip().lower()
    return requested if resolved_pack_layout == str(layout_id or "auto").strip().lower() else "auto"


def resolved_layout_legend_pack_id(app: Any) -> str:
    selected = app._normalize_layout_legend_pack(app._physical_layout, app._layout_legend_pack)
    return resolve_layout_legend_pack_id(app._physical_layout, None if selected == "auto" else selected)


def sync_layout_legend_pack_ui(
    app: Any,
    *,
    tk_call_errors: tuple[type[BaseException], ...],
    log_boundary_exception: Any,
) -> None:
    try:
        app._legend_pack_var.set(app._layout_legend_pack)
    except tk_call_errors as exc:
        log_boundary_exception(
            "perkey.editor.legend_pack_var",
            "Failed to update perkey legend pack variable",
            exc,
        )

    refresh_choices = _refresh_legend_pack_choices_or_none(_layout_setup_controls_or_none(app))
    if refresh_choices is not None:
        refresh_choices()


def refresh_layout_slot_controls(app: Any) -> None:
    refresh_layout_slots_ui(app)


def get_layout_slot_states_for_editor(app: Any):
    return get_layout_slot_states(
        app._physical_layout,
        app.layout_slot_overrides,
        legend_pack_id=app._resolved_layout_legend_pack_id(),
    )


def selected_overlay_identity(app: Any) -> str | None:
    return app.selected_slot_id or app.selected_key_id


def layout_slot_state_for_identity(app: Any, identity: str | None):
    if not identity:
        return None
    for state in app._get_layout_slot_states():
        if identity in {state.slot_id, state.key_id}:
            return state
    return None


def sync_visible_layout_state(app: Any) -> None:
    visible_keys = app._get_visible_layout_keys()
    visible_slot_ids = {str(key.slot_id or key.key_id) for key in visible_keys}
    current_slot_id = app.selected_slot_id or app._slot_id_for_key_id(app.selected_key_id) or app.selected_key_id
    if current_slot_id not in visible_slot_ids:
        app._clear_selection()
        for key in visible_keys:
            if keymap_cells_for(
                app.keymap,
                str(key.key_id),
                slot_id=str(key.slot_id or key.key_id),
                physical_layout=app._physical_layout,
            ):
                app.select_slot_id(str(key.slot_id or key.key_id))
                break
    else:
        app.selected_slot_id = str(current_slot_id) if current_slot_id else None
        app._refresh_selected_cells()


def load_layout_slot_overrides(app: Any) -> dict[str, dict[str, object]]:
    return profiles.load_layout_slots(app.profile_name, physical_layout=app._physical_layout)


def detect_lightbar_device(*, collect_device_discovery: Any, log_boundary_exception: Any) -> bool:
    try:
        payload = collect_device_discovery(include_usb=True)
    except _LIGHTBAR_DISCOVERY_ERRORS as exc:
        log_boundary_exception(
            "perkey.editor.lightbar_discovery",
            "Failed to collect perkey lightbar discovery snapshot",
            exc,
        )
        return False

    for section in ("supported", "candidates"):
        entries = payload.get(section)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and str(entry.get("device_type") or "") == "lightbar":
                return True
    return False


def persist_layout_slot_overrides(app: Any) -> None:
    app.layout_slot_overrides = profiles.save_layout_slots(
        dict(app.layout_slot_overrides),
        app.profile_name,
        physical_layout=app._physical_layout,
    )


def set_layout_slot_visibility(app: Any, slot_id: str, visible: bool) -> None:
    state = app._layout_slot_state_for_identity(slot_id)
    normalized_slot_id = state.slot_id if state is not None else str(slot_id)
    override = dict(app.layout_slot_overrides.get(normalized_slot_id, {}))
    if bool(visible):
        override.pop("visible", None)
    else:
        override["visible"] = False

    if override:
        app.layout_slot_overrides[normalized_slot_id] = override
    else:
        app.layout_slot_overrides.pop(normalized_slot_id, None)

    app._persist_layout_slot_overrides()
    app._refresh_layout_slot_controls()
    app._sync_visible_layout_state()
    app.canvas.redraw()
    set_status(app, layout_slot_visibility_updated(state.key_id if state is not None else normalized_slot_id, visible))


def set_layout_slot_label(app: Any, slot_id: str, label: str) -> None:
    states = app._get_layout_slot_states()
    state = app._layout_slot_state_for_identity(slot_id)
    normalized_slot_id = state.slot_id if state is not None else str(slot_id)
    default_labels = {slot_state.slot_id: slot_state.default_label for slot_state in states}
    normalized_label = str(label).strip()
    override = dict(app.layout_slot_overrides.get(normalized_slot_id, {}))
    default_label = default_labels.get(normalized_slot_id, state.key_id if state is not None else normalized_slot_id)

    if normalized_label and normalized_label != default_label:
        override["label"] = normalized_label
    else:
        override.pop("label", None)

    if override:
        app.layout_slot_overrides[normalized_slot_id] = override
    else:
        app.layout_slot_overrides.pop(normalized_slot_id, None)

    app._persist_layout_slot_overrides()
    app._refresh_layout_slot_controls()
    app.canvas.redraw()
    set_status(
        app,
        layout_slot_label_updated(
            state.key_id if state is not None else normalized_slot_id, normalized_label or default_label
        ),
    )


def load_layout_tweaks(app: Any, *, profiles_module: Any = profiles) -> dict[str, float]:
    return profiles_module.load_layout_global(app.profile_name, physical_layout=app._physical_layout)


def load_per_key_layout_tweaks(app: Any) -> dict[str, dict[str, float]]:
    return profiles.load_layout_per_key(app.profile_name, physical_layout=app._physical_layout)


def on_layout_changed(app: Any) -> None:
    layout_id = app._layout_var.get()
    app._physical_layout = layout_id
    app.config.physical_layout = layout_id
    app._layout_legend_pack = app._normalize_layout_legend_pack(layout_id, app._layout_legend_pack)
    app.config.layout_legend_pack = app._layout_legend_pack
    app._sync_layout_legend_pack_ui()

    profile_paths = profiles.paths_for(app.profile_name)
    if not profile_paths.keymap.exists():
        app.keymap = app._load_keymap()
    if not profile_paths.layout_global.exists():
        app.layout_tweaks = app._load_layout_tweaks()
    if not profile_paths.layout_per_key.exists():
        app.per_key_layout_tweaks = app._load_per_key_layout_tweaks()

    app.layout_slot_overrides = app._load_layout_slot_overrides()

    if app._setup_panel_mode == "overlay":
        app.overlay_controls.sync_vars_from_scope()

    app._refresh_layout_slot_controls()
    app._sync_visible_layout_state()
    app.canvas.redraw()


def on_layout_legend_pack_changed(app: Any) -> None:
    legend_pack_id = app._legend_pack_var.get()
    app._layout_legend_pack = app._normalize_layout_legend_pack(app._physical_layout, legend_pack_id)
    app.config.layout_legend_pack = app._layout_legend_pack
    app._sync_layout_legend_pack_ui()
    app._sync_visible_layout_state()
    app.canvas.redraw()


def hide_setup_panel(app: Any) -> None:
    app._overlay_setup_panel.grid_remove()
    app._layout_setup_controls.grid_remove()
    app._setup_panel_mode = None


def show_setup_panel(app: Any, mode: str) -> None:
    app._hide_setup_panel()
    if mode == "overlay":
        app._overlay_setup_panel.grid()
        app.overlay_controls.sync_vars_from_scope()
        lightbar_controls = _lightbar_controls_or_none(app)
        if lightbar_controls is not None:
            lightbar_controls.sync_vars_from_editor()
    elif mode == "layout":
        app._layout_setup_controls.grid()
        app._refresh_layout_slot_controls()
    app._setup_panel_mode = mode


def toggle_overlay(app: Any) -> None:
    if app._setup_panel_mode == "overlay":
        app._hide_setup_panel()
    else:
        app._show_setup_panel("overlay")


def toggle_layout_setup(app: Any) -> None:
    if app._setup_panel_mode == "layout":
        app._hide_setup_panel()
    else:
        app._show_setup_panel("layout")
