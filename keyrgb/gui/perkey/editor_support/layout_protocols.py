"""Structural protocols for the per-key layout state helpers.

Owns the editor-app/config/canvas/notebook ``Protocol`` surface shared by
``layout_state.py`` and ``layout.py`` so ``layout_state.py`` stays small.
Adds no behavior.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

from keyrgb.core.resources.layout_slots import LayoutSlotState

LayoutSlotOverrides = dict[str, dict[str, object]]
LayoutTweaks = dict[str, float]
PerKeyLayoutTweaks = dict[str, dict[str, float]]
BoundaryLogger = Callable[[str, str, BaseException], None]


class _PathExistsProtocol(Protocol):
    def exists(self) -> bool: ...


class _ProfilePathsProtocol(Protocol):  # noqa: PYI046 – re-exported via layout.py for cross-module casts
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


class _LightbarControlsProtocol(Protocol):  # noqa: PYI046 – re-exported via layout.py for cross-module casts
    def sync_vars_from_editor(self) -> None: ...


class _CanvasProtocol(Protocol):
    def redraw(self) -> None: ...


class _VisibleLayoutKeyProtocol(Protocol):
    slot_id: str | None
    key_id: str


class _LoadLayoutSlotOverridesProfilesProtocol(Protocol):  # noqa: PYI046 - re-exported via layout_state/layout
    def load_layout_slots(self, profile_name: str, *, physical_layout: str) -> LayoutSlotOverrides: ...


class _LoadLayoutTweaksProfilesProtocol(Protocol):  # noqa: PYI046 - re-exported via layout_state/layout
    def load_layout_global(self, profile_name: str, *, physical_layout: str) -> LayoutTweaks: ...


class _LoadPerKeyLayoutTweaksProfilesProtocol(Protocol):  # noqa: PYI046 - re-exported via layout_state/layout
    def load_layout_per_key(self, profile_name: str, *, physical_layout: str) -> PerKeyLayoutTweaks: ...


class _CollectDeviceDiscoveryFn(Protocol):  # noqa: PYI046 - re-exported via layout_state/layout
    def __call__(self, *, include_usb: bool) -> Mapping[str, object]: ...


class _NotebookProtocol(Protocol):
    def select(self, tab_id: object = ...) -> None: ...

    def add(self, child: object, **kwargs: object) -> None: ...


class _LayoutEditorAppProtocol(Protocol):  # noqa: PYI046 - re-exported via layout_state/layout
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
    _lighting_areas_panel: _GridPanelProtocol
    _editor_notebook: _NotebookProtocol
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
