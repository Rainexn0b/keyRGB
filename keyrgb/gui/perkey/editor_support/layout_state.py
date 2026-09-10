from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import cast

from keyrgb.core.profile import profiles
from keyrgb.core.resources.layout_legends import load_layout_legend_pack, resolve_layout_legend_pack_id
from keyrgb.core.resources.layout_slots import LayoutSlotState, get_layout_slot_states

from ..profile_management import keymap_cells_for
from ..ui.layout_slots import refresh_layout_slots_ui
from . import layout_protocols as _protocols

LayoutSlotOverrides = _protocols.LayoutSlotOverrides
LayoutTweaks = _protocols.LayoutTweaks
PerKeyLayoutTweaks = _protocols.PerKeyLayoutTweaks
BoundaryLogger = _protocols.BoundaryLogger
_PathExistsProtocol = _protocols._PathExistsProtocol
_ProfilePathsProtocol = _protocols._ProfilePathsProtocol
_StringVarProtocol = _protocols._StringVarProtocol
_ConfigProtocol = _protocols._ConfigProtocol
_GridPanelProtocol = _protocols._GridPanelProtocol
_OverlayControlsProtocol = _protocols._OverlayControlsProtocol
_LightbarControlsProtocol = _protocols._LightbarControlsProtocol
_CanvasProtocol = _protocols._CanvasProtocol
_VisibleLayoutKeyProtocol = _protocols._VisibleLayoutKeyProtocol
_LoadLayoutSlotOverridesProfilesProtocol = _protocols._LoadLayoutSlotOverridesProfilesProtocol
_LoadLayoutTweaksProfilesProtocol = _protocols._LoadLayoutTweaksProfilesProtocol
_LoadPerKeyLayoutTweaksProfilesProtocol = _protocols._LoadPerKeyLayoutTweaksProfilesProtocol
_CollectDeviceDiscoveryFn = _protocols._CollectDeviceDiscoveryFn
_NotebookProtocol = _protocols._NotebookProtocol
_LayoutEditorAppProtocol = _protocols._LayoutEditorAppProtocol

_LIGHTBAR_DISCOVERY_ERRORS = (
    AttributeError,
    ImportError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)

# UX-03 editor shell: notebook tab order is Profiles, Setup, Advanced.
# _setup_panel_mode maps to the selected tab: None -> Profiles (0),
# "layout" -> Setup (1), "overlay" -> Advanced (2).
SETUP_PANEL_TAB_INDEX_FOR_MODE: dict[str | None, int] = {
    None: 0,
    "layout": 1,
    "overlay": 2,
}

_TAB_SELECT_ERRORS: tuple[type[Exception], ...]
try:  # pragma: no cover - tkinter is always available in the editor runtime
    import tkinter as _tk_for_tab_errors

    _TAB_SELECT_ERRORS = (
        AttributeError,
        RuntimeError,
        TypeError,
        ValueError,
        _tk_for_tab_errors.TclError,
    )
except ImportError:  # pragma: no cover - headless fallback without TclError
    _TAB_SELECT_ERRORS = (AttributeError, RuntimeError, TypeError, ValueError)


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


def normalize_layout_legend_pack(
    layout_id: str,
    legend_pack_id: str | None,
    *,
    load_layout_legend_pack_fn: Callable[[str], Mapping[str, object] | None] = load_layout_legend_pack,
) -> str:
    requested = str(legend_pack_id or "auto").strip().lower()
    if not requested or requested == "auto":
        return "auto"

    pack = load_layout_legend_pack_fn(requested)
    if not pack:
        return "auto"

    resolved_pack_layout = str(pack.get("layout_id") or layout_id).strip().lower()
    return requested if resolved_pack_layout == str(layout_id or "auto").strip().lower() else "auto"


def resolved_layout_legend_pack_id(
    app: _LayoutEditorAppProtocol,
    *,
    resolve_layout_legend_pack_id_fn: Callable[[str, str | None], str] = resolve_layout_legend_pack_id,
) -> str:
    selected = app._normalize_layout_legend_pack(app._physical_layout, app._layout_legend_pack)
    return resolve_layout_legend_pack_id_fn(app._physical_layout, None if selected == "auto" else selected)


def sync_layout_legend_pack_ui(
    app: _LayoutEditorAppProtocol,
    *,
    tk_call_errors: tuple[type[Exception], ...],
    log_boundary_exception: BoundaryLogger,
    layout_setup_controls_or_none_fn: Callable[
        [_LayoutEditorAppProtocol], object | None
    ] = _layout_setup_controls_or_none,
    refresh_legend_pack_choices_or_none_fn: Callable[
        [object | None], Callable[[], None] | None
    ] = _refresh_legend_pack_choices_or_none,
) -> None:
    try:
        app._legend_pack_var.set(app._layout_legend_pack)
    except tk_call_errors as exc:
        log_boundary_exception(
            "perkey.editor.legend_pack_var",
            "Failed to update perkey legend pack variable",
            exc,
        )

    refresh_choices = refresh_legend_pack_choices_or_none_fn(layout_setup_controls_or_none_fn(app))
    if refresh_choices is not None:
        refresh_choices()


def refresh_layout_slot_controls(
    app: _LayoutEditorAppProtocol,
    *,
    refresh_layout_slots_ui_fn: Callable[[object], None] = refresh_layout_slots_ui,
) -> None:
    refresh_layout_slots_ui_fn(app)


def get_layout_slot_states_for_editor(
    app: _LayoutEditorAppProtocol,
    *,
    get_layout_slot_states_fn: Callable[..., Sequence[LayoutSlotState]] = get_layout_slot_states,
) -> list[LayoutSlotState]:
    return list(
        get_layout_slot_states_fn(
            app._physical_layout,
            app.layout_slot_overrides,
            legend_pack_id=app._resolved_layout_legend_pack_id(),
        )
    )


def selected_overlay_identity(app: _LayoutEditorAppProtocol) -> str | None:
    return app.selected_slot_id or app.selected_key_id


def layout_slot_state_for_identity(
    app: _LayoutEditorAppProtocol,
    identity: str | None,
) -> LayoutSlotState | None:
    if not identity:
        return None
    for state in app._get_layout_slot_states():
        if identity in {state.slot_id, state.key_id}:
            return state
    return None


def sync_visible_layout_state(
    app: _LayoutEditorAppProtocol,
    *,
    keymap_cells_for_fn: Callable[..., object] = keymap_cells_for,
) -> None:
    visible_keys = app._get_visible_layout_keys()
    visible_slot_ids = {str(key.slot_id or key.key_id) for key in visible_keys}
    current_slot_id = app.selected_slot_id or app._slot_id_for_key_id(app.selected_key_id) or app.selected_key_id
    if current_slot_id not in visible_slot_ids:
        app._clear_selection()
        for key in visible_keys:
            if keymap_cells_for_fn(
                app.keymap,
                str(key.key_id),
                slot_id=str(key.slot_id or key.key_id),
                physical_layout=app._physical_layout,
            ):
                app.select_slot_id(str(key.slot_id or key.key_id))
                break
        return

    app.selected_slot_id = str(current_slot_id) if current_slot_id else None
    app._refresh_selected_cells()


def load_layout_slot_overrides(
    app: _LayoutEditorAppProtocol,
    *,
    profiles_module: _LoadLayoutSlotOverridesProfilesProtocol = profiles,
) -> LayoutSlotOverrides:
    return profiles_module.load_layout_slots(app.profile_name, physical_layout=app._physical_layout)


def load_layout_tweaks(
    app: _LayoutEditorAppProtocol,
    *,
    profiles_module: _LoadLayoutTweaksProfilesProtocol = profiles,
) -> LayoutTweaks:
    return profiles_module.load_layout_global(app.profile_name, physical_layout=app._physical_layout)


def load_per_key_layout_tweaks(
    app: _LayoutEditorAppProtocol,
    *,
    profiles_module: _LoadPerKeyLayoutTweaksProfilesProtocol = profiles,
) -> PerKeyLayoutTweaks:
    return profiles_module.load_layout_per_key(app.profile_name, physical_layout=app._physical_layout)


def tab_index_for_setup_mode(mode: str | None) -> int:
    """Map a setup-panel mode to its UX-03 notebook tab index."""

    return SETUP_PANEL_TAB_INDEX_FOR_MODE.get(mode, 0)


def select_setup_panel_tab(app: object, index: int) -> bool:
    """Select a notebook tab by index; False when no notebook is present."""

    notebook = vars(app).get("_editor_notebook")
    select = getattr(notebook, "select", None)
    if notebook is None or not callable(select):
        return False
    try:
        select(index)
    except _TAB_SELECT_ERRORS:
        return False
    return True


def detect_lightbar_device(
    *,
    collect_device_discovery: _CollectDeviceDiscoveryFn,
    log_boundary_exception: BoundaryLogger,
    lightbar_discovery_errors: tuple[type[Exception], ...] = _LIGHTBAR_DISCOVERY_ERRORS,
) -> bool:
    try:
        payload = collect_device_discovery(include_usb=True)
    except lightbar_discovery_errors as exc:
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
