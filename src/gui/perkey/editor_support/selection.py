from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, TypeAlias

from src.core.resources.layout import get_layout_keys

from ..profile_management import (
    KeyCell,
    KeyCells,
    Keymap,
    PerKeyColors,
    keymap_cells_for,
    representative_cell,
)
from ..ui.status import selected_mapped, selected_unmapped, set_status


LayoutSlotOverrides: TypeAlias = dict[str, dict[str, object]]
RgbColor: TypeAlias = tuple[int, int, int]


class _VisibleLayoutKeyProtocol(Protocol):
    key_id: str
    slot_id: str | None


_VisibleKeyMap: TypeAlias = dict[str, _VisibleLayoutKeyProtocol]
_EMPTY_KEY_CELLS: KeyCells = ()


class _StringVarProtocol(Protocol):
    def get(self) -> str: ...


class _OverlayControlsProtocol(Protocol):
    def sync_vars_from_scope(self) -> None: ...


class _CanvasProtocol(Protocol):
    def redraw(self) -> None: ...


class _ColorWheelProtocol(Protocol):
    def set_color(self, r: int, g: int, b: int) -> None: ...


class _VisibleLayoutSourceProtocol(Protocol):
    _physical_layout: str
    layout_slot_overrides: LayoutSlotOverrides

    def _resolved_layout_legend_pack_id(self) -> str: ...


class _VisibleKeyMapsSourceProtocol(Protocol):
    def _get_visible_layout_keys(self) -> Sequence[_VisibleLayoutKeyProtocol]: ...


class _VisibleKeyLookupSourceProtocol(Protocol):
    def _visible_key_maps(self) -> tuple[_VisibleKeyMap, _VisibleKeyMap]: ...


class _VisibleKeyIdLookupProtocol(Protocol):
    def _visible_key_for_key_id(
        self,
        key_id: str | None,
    ) -> _VisibleLayoutKeyProtocol | None: ...


class _VisibleSlotIdLookupProtocol(Protocol):
    def _visible_key_for_slot_id(
        self,
        slot_id: str | None,
    ) -> _VisibleLayoutKeyProtocol | None: ...


class _SelectionStateProtocol(Protocol):
    selected_key_id: str | None
    selected_slot_id: str | None
    selected_cells: KeyCells
    selected_cell: KeyCell | None


class _SelectionApplyProtocol(_SelectionStateProtocol, Protocol):
    keymap: Keymap
    _physical_layout: str


class _SelectionDisplayProtocol(_SelectionStateProtocol, Protocol):
    def _key_id_for_slot_id(self, slot_id: str | None) -> str | None: ...


class _SelectionRefreshProtocol(_SelectionStateProtocol, Protocol):
    keymap: Keymap
    colors: PerKeyColors
    _physical_layout: str

    def _selected_display_key_id(self) -> str | None: ...


class _SelectionFinalizeProtocol(_SelectionStateProtocol, Protocol):
    overlay_scope: _StringVarProtocol
    overlay_controls: _OverlayControlsProtocol
    canvas: _CanvasProtocol
    colors: PerKeyColors
    color_wheel: _ColorWheelProtocol
    _last_non_black_color: RgbColor

    def _selected_display_key_id(self) -> str | None: ...


class _SlotSelectionProtocol(Protocol):
    canvas: _CanvasProtocol

    def _visible_key_for_slot_id(
        self,
        slot_id: str | None,
    ) -> _VisibleLayoutKeyProtocol | None: ...

    def _clear_selection(self) -> None: ...

    def _apply_selection_for_visible_key(self, key: _VisibleLayoutKeyProtocol) -> None: ...

    def _finalize_selection(self, requested_identity: str) -> None: ...


def get_visible_layout_keys(
    app: _VisibleLayoutSourceProtocol,
) -> Sequence[_VisibleLayoutKeyProtocol]:
    return get_layout_keys(
        app._physical_layout,
        legend_pack_id=app._resolved_layout_legend_pack_id(),
        slot_overrides=app.layout_slot_overrides,
    )


def visible_key_maps(app: _VisibleKeyMapsSourceProtocol) -> tuple[_VisibleKeyMap, _VisibleKeyMap]:
    visible_keys = app._get_visible_layout_keys()
    by_key_id = {str(key.key_id): key for key in visible_keys}
    by_slot_id = {str(key.slot_id): key for key in visible_keys if key.slot_id}
    return by_key_id, by_slot_id


def visible_key_for_key_id(
    app: _VisibleKeyLookupSourceProtocol,
    key_id: str | None,
) -> _VisibleLayoutKeyProtocol | None:
    if not key_id:
        return None
    by_key_id, _by_slot_id = app._visible_key_maps()
    return by_key_id.get(str(key_id))


def visible_key_for_slot_id(
    app: _VisibleKeyLookupSourceProtocol,
    slot_id: str | None,
) -> _VisibleLayoutKeyProtocol | None:
    if not slot_id:
        return None
    _by_key_id, by_slot_id = app._visible_key_maps()
    return by_slot_id.get(str(slot_id))


def slot_id_for_key_id(
    app: _VisibleKeyIdLookupProtocol,
    key_id: str | None,
) -> str | None:
    key = app._visible_key_for_key_id(key_id)
    if key is None or not key.slot_id:
        return None
    return str(key.slot_id)


def key_id_for_slot_id(
    app: _VisibleSlotIdLookupProtocol,
    slot_id: str | None,
) -> str | None:
    key = app._visible_key_for_slot_id(slot_id)
    if key is None:
        return None
    return str(key.key_id)


def clear_selection(app: _SelectionStateProtocol) -> None:
    app.selected_key_id = None
    app.selected_slot_id = None
    app.selected_cells = _EMPTY_KEY_CELLS
    app.selected_cell = None


def apply_selection_for_visible_key(
    app: _SelectionApplyProtocol,
    key: _VisibleLayoutKeyProtocol,
) -> None:
    app.selected_key_id = str(key.key_id)
    app.selected_slot_id = str(key.slot_id or key.key_id)
    app.selected_cells = keymap_cells_for(
        app.keymap,
        app.selected_key_id,
        slot_id=app.selected_slot_id,
        physical_layout=app._physical_layout,
    )
    app.selected_cell = None


def selected_display_key_id(app: _SelectionDisplayProtocol) -> str | None:
    if app.selected_key_id:
        return str(app.selected_key_id)
    if app.selected_slot_id:
        return app._key_id_for_slot_id(app.selected_slot_id)
    return None


def refresh_selected_cells(app: _SelectionRefreshProtocol) -> None:
    app.selected_cells = keymap_cells_for(
        app.keymap,
        app._selected_display_key_id(),
        slot_id=app.selected_slot_id,
        physical_layout=app._physical_layout,
    )
    app.selected_cell = representative_cell(app.selected_cells, colors=app.colors)


def finalize_selection(
    app: _SelectionFinalizeProtocol,
    requested_identity: str,
) -> None:
    display_key_id = app._selected_display_key_id() or str(requested_identity)

    if app.overlay_scope.get() == "key":
        app.overlay_controls.sync_vars_from_scope()

    if not app.selected_cells:
        set_status(app, selected_unmapped(display_key_id))
        app.canvas.redraw()
        return

    row, col = app.selected_cells[0]
    display_cell = representative_cell(app.selected_cells, colors=app.colors)
    color = app.colors.get(display_cell, (0, 0, 0)) if display_cell is not None else (0, 0, 0)

    if tuple(color) == (0, 0, 0):
        app.color_wheel.set_color(*app._last_non_black_color)
    else:
        app._last_non_black_color = (int(color[0]), int(color[1]), int(color[2]))
        app.color_wheel.set_color(*color)

    set_status(app, selected_mapped(display_key_id, row, col, len(app.selected_cells)))
    app.canvas.redraw()


def select_slot_id(app: _SlotSelectionProtocol, slot_id: str) -> None:
    key = app._visible_key_for_slot_id(slot_id)
    if key is None:
        app._clear_selection()
        app.canvas.redraw()
        return

    app._apply_selection_for_visible_key(key)
    app._finalize_selection(str(slot_id))
