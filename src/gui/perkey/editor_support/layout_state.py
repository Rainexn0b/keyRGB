from __future__ import annotations

from typing import Callable, Mapping, Protocol, Sequence, cast

from src.core.profile import profiles
from src.core.resources.layout_legends import load_layout_legend_pack, resolve_layout_legend_pack_id
from src.core.resources.layout_slots import LayoutSlotState, get_layout_slot_states

from ..profile_management import keymap_cells_for
from ..ui.layout_slots import refresh_layout_slots_ui


_LIGHTBAR_DISCOVERY_ERRORS = (
    AttributeError,
    ImportError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)

LayoutSlotOverrides = dict[str, dict[str, object]]
LayoutTweaks = dict[str, float]
PerKeyLayoutTweaks = dict[str, dict[str, float]]
BoundaryLogger = Callable[[str, str, Exception], None]


class _PathExistsProtocol(Protocol):
    def exists(self) -> bool: ...


class _ProfilePathsProtocol(Protocol):
    keymap: _PathExistsProtocol
    layout_global: _PathExistsProtocol
    layout_per_key: _PathExistsProtocol


class _StringVarProtocol(Protocol):
    def get(self) -> str: ...

    def set(self, value: object) -> None: ...


class _ConfigProtocol(Protocol):
    physical_layout: str
    layout_legend_pack: str


class _GridPanelProtocol(Protocol):
    def grid(self) -> None: ...

    def grid_remove(self) -> None: ...


class _OverlayControlsProtocol(Protocol):
    def sync_vars_from_scope(self) -> None: ...


class _LightbarControlsProtocol(Protocol):
    def sync_vars_from_editor(self) -> None: ...


class _CanvasProtocol(Protocol):
    def redraw(self) -> None: ...


class _VisibleLayoutKeyProtocol(Protocol):
    slot_id: str | None
    key_id: str


class _LoadLayoutSlotOverridesProfilesProtocol(Protocol):
    def load_layout_slots(self, profile_name: str, *, physical_layout: str) -> LayoutSlotOverrides: ...


class _LoadLayoutTweaksProfilesProtocol(Protocol):
    def load_layout_global(self, profile_name: str, *, physical_layout: str) -> LayoutTweaks: ...


class _LoadPerKeyLayoutTweaksProfilesProtocol(Protocol):
    def load_layout_per_key(self, profile_name: str, *, physical_layout: str) -> PerKeyLayoutTweaks: ...


class _CollectDeviceDiscoveryFn(Protocol):
    def __call__(self, *, include_usb: bool) -> Mapping[str, object]: ...


class _LayoutEditorAppProtocol(Protocol):
    profile_name: str
    _physical_layout: str
    _layout_legend_pack: str
    selected_slot_id: str | None
    selected_key_id: str | None
    layout_slot_overrides: LayoutSlotOverrides
    layout_tweaks: LayoutTweaks
    per_key_layout_tweaks: PerKeyLayoutTweaks
    keymap: Mapping[str, object]
    _setup_panel_mode: str | None
    config: _ConfigProtocol
    _layout_var: _StringVarProtocol
    _legend_pack_var: _StringVarProtocol
    _overlay_setup_panel: _GridPanelProtocol
    _layout_setup_controls: _GridPanelProtocol
    overlay_controls: _OverlayControlsProtocol
    canvas: _CanvasProtocol

    def _normalize_layout_legend_pack(self, layout_id: str, legend_pack_id: str | None) -> str: ...

    def _resolved_layout_legend_pack_id(self) -> str: ...

    def _sync_layout_legend_pack_ui(self) -> None: ...

    def _get_layout_slot_states(self) -> Sequence[LayoutSlotState]: ...

    def _get_visible_layout_keys(self) -> Sequence[_VisibleLayoutKeyProtocol]: ...

    def _slot_id_for_key_id(self, key_id: str | None) -> str | None: ...

    def _clear_selection(self) -> None: ...

    def select_slot_id(self, slot_id: str) -> None: ...

    def _refresh_selected_cells(self) -> None: ...

    def _load_keymap(self) -> Mapping[str, object]: ...

    def _load_layout_tweaks(self) -> LayoutTweaks: ...

    def _load_per_key_layout_tweaks(self) -> PerKeyLayoutTweaks: ...

    def _load_layout_slot_overrides(self) -> LayoutSlotOverrides: ...

    def _persist_layout_slot_overrides(self) -> None: ...

    def _refresh_layout_slot_controls(self) -> None: ...

    def _sync_visible_layout_state(self) -> None: ...

    def _layout_slot_state_for_identity(self, identity: str | None) -> LayoutSlotState | None: ...

    def _hide_setup_panel(self) -> None: ...

    def _show_setup_panel(self, mode: str) -> None: ...


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
            cast(Exception, exc),
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
