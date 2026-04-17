from __future__ import annotations

from typing import Callable, cast

from src.core.profile import profiles
from src.core.resources.layout_legends import load_layout_legend_pack, resolve_layout_legend_pack_id
from src.core.resources.layout_slots import LayoutSlotState, get_layout_slot_states

from ..profile_management import keymap_cells_for
from ..ui.layout_slots import refresh_layout_slots_ui
from ..ui.status import layout_slot_label_updated, layout_slot_visibility_updated, set_status
from . import layout_state as _layout_state


BoundaryLogger = _layout_state.BoundaryLogger
LayoutSlotOverrides = _layout_state.LayoutSlotOverrides
LayoutTweaks = _layout_state.LayoutTweaks
PerKeyLayoutTweaks = _layout_state.PerKeyLayoutTweaks
_CollectDeviceDiscoveryFn = _layout_state._CollectDeviceDiscoveryFn
_GridPanelProtocol = _layout_state._GridPanelProtocol
_LightbarControlsProtocol = _layout_state._LightbarControlsProtocol
_LayoutEditorAppProtocol = _layout_state._LayoutEditorAppProtocol
_LoadLayoutSlotOverridesProfilesProtocol = _layout_state._LoadLayoutSlotOverridesProfilesProtocol
_LoadLayoutTweaksProfilesProtocol = _layout_state._LoadLayoutTweaksProfilesProtocol
_LoadPerKeyLayoutTweaksProfilesProtocol = _layout_state._LoadPerKeyLayoutTweaksProfilesProtocol
_ProfilePathsProtocol = _layout_state._ProfilePathsProtocol


def _layout_setup_controls_or_none(app: _LayoutEditorAppProtocol) -> _GridPanelProtocol | None:
    try:
        return app._layout_setup_controls
    except AttributeError:
        return None


def _refresh_legend_pack_choices_or_none(controls: object | None) -> Callable[[], None] | None:
    refresh_choices = getattr(controls, "refresh_legend_pack_choices", None)
    if not callable(refresh_choices):
        return None
    return cast(Callable[[], None], refresh_choices)


def _lightbar_controls_or_none(app: object) -> _LightbarControlsProtocol | None:
    controls = getattr(app, "lightbar_controls", None)
    sync_vars_from_editor = getattr(controls, "sync_vars_from_editor", None)
    if not callable(sync_vars_from_editor):
        return None
    return cast(_LightbarControlsProtocol, controls)


def normalize_layout_legend_pack(layout_id: str, legend_pack_id: str | None) -> str:
    return _layout_state.normalize_layout_legend_pack(
        layout_id,
        legend_pack_id,
        load_layout_legend_pack_fn=load_layout_legend_pack,
    )


def resolved_layout_legend_pack_id(app: _LayoutEditorAppProtocol) -> str:
    return _layout_state.resolved_layout_legend_pack_id(
        app,
        resolve_layout_legend_pack_id_fn=resolve_layout_legend_pack_id,
    )


def sync_layout_legend_pack_ui(
    app: _LayoutEditorAppProtocol,
    *,
    tk_call_errors: tuple[type[Exception], ...],
    log_boundary_exception: BoundaryLogger,
) -> None:
    _layout_state.sync_layout_legend_pack_ui(
        app,
        tk_call_errors=tk_call_errors,
        log_boundary_exception=log_boundary_exception,
        layout_setup_controls_or_none_fn=_layout_setup_controls_or_none,
        refresh_legend_pack_choices_or_none_fn=_refresh_legend_pack_choices_or_none,
    )


def refresh_layout_slot_controls(app: _LayoutEditorAppProtocol) -> None:
    _layout_state.refresh_layout_slot_controls(
        app,
        refresh_layout_slots_ui_fn=refresh_layout_slots_ui,
    )


def get_layout_slot_states_for_editor(app: _LayoutEditorAppProtocol) -> list[LayoutSlotState]:
    return _layout_state.get_layout_slot_states_for_editor(
        app,
        get_layout_slot_states_fn=get_layout_slot_states,
    )


def selected_overlay_identity(app: _LayoutEditorAppProtocol) -> str | None:
    return _layout_state.selected_overlay_identity(app)


def layout_slot_state_for_identity(
    app: _LayoutEditorAppProtocol,
    identity: str | None,
) -> LayoutSlotState | None:
    return _layout_state.layout_slot_state_for_identity(app, identity)


def sync_visible_layout_state(app: _LayoutEditorAppProtocol) -> None:
    _layout_state.sync_visible_layout_state(
        app,
        keymap_cells_for_fn=keymap_cells_for,
    )


def load_layout_slot_overrides(
    app: _LayoutEditorAppProtocol,
    *,
    profiles_module: _LoadLayoutSlotOverridesProfilesProtocol = profiles,
) -> LayoutSlotOverrides:
    return _layout_state.load_layout_slot_overrides(app, profiles_module=profiles_module)


def load_layout_tweaks(
    app: _LayoutEditorAppProtocol,
    *,
    profiles_module: _LoadLayoutTweaksProfilesProtocol = profiles,
) -> LayoutTweaks:
    return _layout_state.load_layout_tweaks(app, profiles_module=profiles_module)


def load_per_key_layout_tweaks(
    app: _LayoutEditorAppProtocol,
    *,
    profiles_module: _LoadPerKeyLayoutTweaksProfilesProtocol = profiles,
) -> PerKeyLayoutTweaks:
    return _layout_state.load_per_key_layout_tweaks(app, profiles_module=profiles_module)


def detect_lightbar_device(
    *,
    collect_device_discovery: _CollectDeviceDiscoveryFn,
    log_boundary_exception: BoundaryLogger,
) -> bool:
    return _layout_state.detect_lightbar_device(
        collect_device_discovery=collect_device_discovery,
        log_boundary_exception=log_boundary_exception,
    )


def persist_layout_slot_overrides(app: _LayoutEditorAppProtocol) -> None:
    app.layout_slot_overrides = profiles.save_layout_slots(
        dict(app.layout_slot_overrides),
        app.profile_name,
        physical_layout=app._physical_layout,
    )


def set_layout_slot_visibility(app: _LayoutEditorAppProtocol, slot_id: str, visible: bool) -> None:
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


def set_layout_slot_label(app: _LayoutEditorAppProtocol, slot_id: str, label: str) -> None:
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
            state.key_id if state is not None else normalized_slot_id,
            normalized_label or default_label,
        ),
    )


def on_layout_changed(app: _LayoutEditorAppProtocol) -> None:
    layout_id = app._layout_var.get()
    app._physical_layout = layout_id
    app.config.physical_layout = layout_id
    app._layout_legend_pack = app._normalize_layout_legend_pack(layout_id, app._layout_legend_pack)
    app.config.layout_legend_pack = app._layout_legend_pack
    app._sync_layout_legend_pack_ui()

    profile_paths = cast(_ProfilePathsProtocol, profiles.paths_for(app.profile_name))
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


def on_layout_legend_pack_changed(app: _LayoutEditorAppProtocol) -> None:
    legend_pack_id = app._legend_pack_var.get()
    app._layout_legend_pack = app._normalize_layout_legend_pack(app._physical_layout, legend_pack_id)
    app.config.layout_legend_pack = app._layout_legend_pack
    app._sync_layout_legend_pack_ui()
    app._sync_visible_layout_state()
    app.canvas.redraw()


def hide_setup_panel(app: _LayoutEditorAppProtocol) -> None:
    app._overlay_setup_panel.grid_remove()
    app._layout_setup_controls.grid_remove()
    app._setup_panel_mode = None


def show_setup_panel(app: _LayoutEditorAppProtocol, mode: str) -> None:
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


def toggle_overlay(app: _LayoutEditorAppProtocol) -> None:
    if app._setup_panel_mode == "overlay":
        app._hide_setup_panel()
    else:
        app._show_setup_panel("overlay")


def toggle_layout_setup(app: _LayoutEditorAppProtocol) -> None:
    if app._setup_panel_mode == "layout":
        app._hide_setup_panel()
    else:
        app._show_setup_panel("layout")
