"""Private support types and best-effort UI helpers for the sample tool."""

from __future__ import annotations

import tkinter as tk
from typing import Protocol, cast

from ..profile_management import KeyCell, KeyCells, Keymap, PerKeyColors, keymap_cells_for, representative_cell


_TK_WIDGET_ERRORS = (AttributeError, RuntimeError, tk.TclError)
_UI_VALUE_ERRORS = (TypeError, ValueError, OverflowError)
_OVERLAY_SYNC_ERRORS = _TK_WIDGET_ERRORS + _UI_VALUE_ERRORS
_WHEEL_COLOR_ERRORS = _TK_WIDGET_ERRORS + _UI_VALUE_ERRORS
RgbColor = tuple[int, int, int]


class _BoolVarProtocol(Protocol):
    def get(self) -> bool: ...


class _StringVarProtocol(Protocol):
    def get(self) -> str: ...


class _CanvasProtocol(Protocol):
    def redraw(self) -> None: ...


class _ColorWheelProtocol(Protocol):
    def set_color(self, r: int, g: int, b: int) -> None: ...

    def get_color(self) -> RgbColor: ...


class _OverlayControlsProtocol(Protocol):
    def sync_vars_from_scope(self) -> None: ...


class _VisibleKeyProtocol(Protocol):
    key_id: str


class _PhysicalLayoutOwner(Protocol):
    _physical_layout: str


class _LastNonBlackColorOwner(Protocol):
    _last_non_black_color: RgbColor


class _CanvasOwner(Protocol):
    canvas: _CanvasProtocol


class _SlotLookupOwner(Protocol):
    def _slot_id_for_key_id(self, key_id: str) -> str | None: ...


class _KeyLookupOwner(Protocol):
    def _key_id_for_slot_id(self, slot_id: str) -> str | None: ...


class _VisibleSlotLookupOwner(Protocol):
    def _visible_key_for_slot_id(self, slot_id: str) -> _VisibleKeyProtocol | None: ...


class _KeymapOwner(Protocol):
    keymap: Keymap


class _ColorsOwner(Protocol):
    colors: PerKeyColors


class _OverlayScopeOwner(Protocol):
    overlay_scope: _StringVarProtocol | None


class _OverlayControlsOwner(Protocol):
    overlay_controls: _OverlayControlsProtocol | None


class _SampleToolToggleEditorProtocol(Protocol):
    sample_tool_enabled: _BoolVarProtocol
    _sample_tool_has_sampled: bool


class _SampleToolEditorProtocol(_SampleToolToggleEditorProtocol, Protocol):
    keymap: Keymap
    colors: PerKeyColors
    selected_key_id: str | None
    selected_slot_id: str | None
    selected_cells: KeyCells
    selected_cell: KeyCell | None
    overlay_scope: _StringVarProtocol | None
    overlay_controls: _OverlayControlsProtocol | None
    canvas: _CanvasProtocol
    color_wheel: _ColorWheelProtocol


class _ApplyReleaseFn(Protocol):
    def __call__(
        self,
        editor: _SampleToolEditorProtocol,
        r: int,
        g: int,
        b: int,
        *,
        num_rows: int,
        num_cols: int,
    ) -> None: ...


def _sample_tool_enabled(editor: object) -> bool:
    try:
        return bool(cast(_SampleToolToggleEditorProtocol, editor).sample_tool_enabled.get())
    except AttributeError:
        return False


def _physical_layout_or_none(editor: object) -> str | None:
    try:
        return cast(_PhysicalLayoutOwner, editor)._physical_layout
    except AttributeError:
        return None


def _keymap_or_empty(editor: object) -> Keymap:
    try:
        return cast(_KeymapOwner, editor).keymap or {}
    except AttributeError:
        return {}


def _colors_or_empty(editor: object) -> PerKeyColors:
    try:
        return cast(_ColorsOwner, editor).colors or {}
    except AttributeError:
        return {}


def _overlay_scope_or_none(editor: object) -> _StringVarProtocol | None:
    try:
        return cast(_OverlayScopeOwner, editor).overlay_scope
    except AttributeError:
        return None


def _overlay_controls_or_none(editor: object) -> _OverlayControlsProtocol | None:
    try:
        return cast(_OverlayControlsOwner, editor).overlay_controls
    except AttributeError:
        return None


def _last_non_black_color_or_default(editor: object) -> RgbColor:
    try:
        return cast(_LastNonBlackColorOwner, editor)._last_non_black_color or (255, 0, 0)
    except AttributeError:
        return (255, 0, 0)


def _redraw_canvas_best_effort(editor: object) -> None:
    try:
        cast(_CanvasOwner, editor).canvas.redraw()
    except _TK_WIDGET_ERRORS:
        pass


def _slot_id_for_key_identity(editor: object, key_id: str) -> str | None:
    try:
        return cast(_SlotLookupOwner, editor)._slot_id_for_key_id(key_id)
    except AttributeError:
        return None


def _key_id_for_slot_identity(editor: object, slot_id: str) -> str | None:
    try:
        key_id = cast(_KeyLookupOwner, editor)._key_id_for_slot_id(slot_id)
    except AttributeError:
        key_id = None
    if key_id:
        return str(key_id)

    try:
        key = cast(_VisibleSlotLookupOwner, editor)._visible_key_for_slot_id(slot_id)
    except AttributeError:
        key = None
    if key is not None and key.key_id:
        return str(key.key_id)
    return None


def _select_slot_id_if_present(editor: object, slot_id: str) -> bool:
    select_slot = getattr(editor, "select_slot_id", None)
    if callable(select_slot):
        select_slot(slot_id)
        return True
    return False


def _select_key_id_if_present(editor: object, key_id: str) -> bool:
    select_key = getattr(editor, "select_key_id", None)
    if callable(select_key):
        select_key(key_id)
        return True
    return False


def _set_selected_key_without_updating_wheel(editor: _SampleToolEditorProtocol, key_id: str) -> None:
    editor.selected_key_id = key_id
    slot_id = _slot_id_for_key_identity(editor, key_id)
    if slot_id is not None:
        editor.selected_slot_id = slot_id
    editor.selected_cells = keymap_cells_for(
        _keymap_or_empty(editor),
        key_id,
        slot_id=editor.selected_slot_id,
        physical_layout=_physical_layout_or_none(editor),
    )
    editor.selected_cell = representative_cell(editor.selected_cells, colors=_colors_or_empty(editor))

    try:
        overlay_scope = _overlay_scope_or_none(editor)
        if overlay_scope is not None and overlay_scope.get() == "key":
            overlay_controls = _overlay_controls_or_none(editor)
            if overlay_controls is not None:
                overlay_controls.sync_vars_from_scope()
    except _OVERLAY_SYNC_ERRORS:
        pass


def _sample_selected_color_into_wheel(editor: _SampleToolEditorProtocol, cells: KeyCells) -> RgbColor:
    colors = _colors_or_empty(editor)
    cell = representative_cell(cells, colors=colors)
    r, g, b = colors.get(cell, (0, 0, 0)) if cell is not None else (0, 0, 0)
    try:
        editor.color_wheel.set_color(int(r), int(g), int(b))
    except _WHEEL_COLOR_ERRORS:
        pass
    editor._sample_tool_has_sampled = True
    return (int(r), int(g), int(b))


def _current_or_fallback_wheel_color(editor: _SampleToolEditorProtocol) -> RgbColor:
    try:
        r, g, b = editor.color_wheel.get_color()
        return (int(r), int(g), int(b))
    except _WHEEL_COLOR_ERRORS:
        r, g, b = _last_non_black_color_or_default(editor)
        return (int(r), int(g), int(b))
