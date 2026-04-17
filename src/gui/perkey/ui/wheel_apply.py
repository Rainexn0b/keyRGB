from __future__ import annotations

from typing import Mapping, Protocol, cast

from ..ops.color_apply_ops import apply_color_to_map
from ..ops.color_map_ops import Color, ColorMap
from ..profile_management import KeyCells, keymap_cells_for
from .status import saved_all_keys_rgb, saved_key_rgb, set_status


class _BoolVarProtocol(Protocol):
    def get(self) -> bool: ...


class _CanvasProtocol(Protocol):
    def redraw(self) -> None: ...

    def update_key_visual(self, key_id: str, color: Color) -> None: ...


class _WheelApplyEditorProtocol(Protocol):
    colors: ColorMap
    keymap: Mapping[str, object]
    apply_all_keys: _BoolVarProtocol
    canvas: _CanvasProtocol
    _last_non_black_color: Color

    def _commit(self, *, force: bool) -> None: ...


class _PhysicalLayoutOwner(Protocol):
    _physical_layout: str


class _SelectedKeyOwner(Protocol):
    selected_key_id: str | None


class _SelectedSlotOwner(Protocol):
    selected_slot_id: str | None


class _SelectedCellsOwner(Protocol):
    selected_cells: KeyCells


class _KeyIdForSlotLookup(Protocol):
    def _key_id_for_slot_id(self, slot_id: str) -> str | None: ...


class _ApplyColorFn(Protocol):
    def __call__(
        self,
        *,
        colors: ColorMap,
        num_rows: int,
        num_cols: int,
        color: Color,
        apply_all_keys: bool,
        selected_cells: KeyCells,
    ) -> ColorMap: ...


def _physical_layout_or_none(editor: object) -> str | None:
    try:
        return cast(_PhysicalLayoutOwner, editor)._physical_layout
    except AttributeError:
        return None


def _selected_key_id_or_none(editor: object) -> str | None:
    try:
        return cast(_SelectedKeyOwner, editor).selected_key_id
    except AttributeError:
        return None


def _selected_slot_id_or_none(editor: object) -> str | None:
    try:
        return cast(_SelectedSlotOwner, editor).selected_slot_id
    except AttributeError:
        return None


def _selected_cells_or_empty(editor: object) -> KeyCells:
    try:
        return tuple(cast(_SelectedCellsOwner, editor).selected_cells or ())
    except AttributeError:
        return ()


def _selected_key_id_for_slot(
    editor: object,
    selected_key_id: str | None,
    selected_slot_id: str | None,
) -> str | None:
    if selected_key_id is not None or selected_slot_id is None:
        return selected_key_id

    try:
        return cast(_KeyIdForSlotLookup, editor)._key_id_for_slot_id(selected_slot_id)
    except AttributeError:
        return None


def _selected_cells(
    editor: object,
    keymap: Mapping[str, object],
    *,
    selected_key_id: str | None,
    selected_slot_id: str | None,
) -> KeyCells:
    return _selected_cells_or_empty(editor) or keymap_cells_for(
        keymap,
        selected_key_id,
        slot_id=selected_slot_id,
        physical_layout=_physical_layout_or_none(editor),
    )


def _apply_wheel_color(
    editor: _WheelApplyEditorProtocol,
    color: Color,
    *,
    num_rows: int,
    num_cols: int,
    apply_fn: _ApplyColorFn,
    force: bool,
) -> tuple[bool, str | None, str | None, KeyCells] | None:
    if color != (0, 0, 0):
        editor._last_non_black_color = color

    apply_all_keys = bool(editor.apply_all_keys.get())
    selected_slot_id = _selected_slot_id_or_none(editor)
    selected_key_id = _selected_key_id_for_slot(
        editor,
        _selected_key_id_or_none(editor),
        selected_slot_id,
    )
    selected_identity = selected_slot_id or selected_key_id
    selected_cells = _selected_cells(
        editor,
        editor.keymap,
        selected_key_id=selected_key_id,
        selected_slot_id=selected_slot_id,
    )

    if (not apply_all_keys) and (not selected_cells or not selected_identity):
        return None

    editor.colors = apply_fn(
        colors=dict(editor.colors),
        num_rows=num_rows,
        num_cols=num_cols,
        color=color,
        apply_all_keys=apply_all_keys,
        selected_cells=selected_cells,
    )

    if apply_all_keys:
        editor.canvas.redraw()
    else:
        editor.canvas.update_key_visual(str(selected_identity), color)

    editor._commit(force=force)
    return apply_all_keys, selected_key_id, selected_identity, selected_cells


def on_wheel_color_change_ui(
    editor: _WheelApplyEditorProtocol,
    r: int,
    g: int,
    b: int,
    *,
    num_rows: int,
    num_cols: int,
    apply_fn: _ApplyColorFn = apply_color_to_map,
) -> None:
    """Apply a color while dragging the wheel.

    No UX change: preserves the prior behavior of `PerKeyEditor._on_color_change`.
    """

    _apply_wheel_color(
        editor,
        (r, g, b),
        num_rows=num_rows,
        num_cols=num_cols,
        apply_fn=apply_fn,
        force=False,
    )


def on_wheel_color_release_ui(
    editor: _WheelApplyEditorProtocol,
    r: int,
    g: int,
    b: int,
    *,
    num_rows: int,
    num_cols: int,
    apply_fn: _ApplyColorFn = apply_color_to_map,
) -> None:
    """Apply a color when releasing the wheel and persist it.

    No UX change: preserves the prior behavior and messages from
    `PerKeyEditor._on_color_release`.
    """

    applied = _apply_wheel_color(
        editor,
        (r, g, b),
        num_rows=num_rows,
        num_cols=num_cols,
        apply_fn=apply_fn,
        force=True,
    )
    if applied is None:
        return

    apply_all_keys, selected_key_id, selected_identity, selected_cells = applied
    if apply_all_keys:
        set_status(editor, saved_all_keys_rgb(r, g, b))
    elif selected_cells and selected_identity is not None:
        set_status(editor, saved_key_rgb(str(selected_key_id or selected_identity), r, g, b))
