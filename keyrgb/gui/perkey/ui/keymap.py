from __future__ import annotations

from typing import Protocol, cast

from ..profile_management import KeyCell, KeyCells, Keymap, keymap_cells_for, primary_cell
from .status import keymap_reloaded, no_keymap_found, set_status


class _CanvasProtocol(Protocol):
    def redraw(self) -> None: ...


class _CanvasOwner(Protocol):
    canvas: _CanvasProtocol


class _KeymapLoaderProtocol(Protocol):
    def _load_keymap(self) -> Keymap: ...


class _MutableKeymapOwner(Protocol):
    keymap: Keymap


class _SlotLookupOwner(Protocol):
    def _slot_id_for_key_id(self, key_id: str) -> str | None: ...


class _PhysicalLayoutOwner(Protocol):
    _physical_layout: str


class _SelectedKeyOwner(Protocol):
    selected_key_id: str | None


class _SelectedSlotOwner(Protocol):
    selected_slot_id: str | None


class _MutableSelectionOwner(Protocol):
    selected_cells: KeyCells
    selected_cell: KeyCell | None


def _keymap_or_empty(editor: object) -> Keymap:
    try:
        return cast(_MutableKeymapOwner, editor).keymap or {}
    except AttributeError:
        return {}


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


def _set_selected_slot_id_if_present(editor: object, slot_id: str | None) -> None:
    if not hasattr(editor, "selected_slot_id"):
        return
    cast(_SelectedSlotOwner, editor).selected_slot_id = slot_id


def _slot_id_for_key_id_or_none(editor: object, key_id: str | None) -> str | None:
    if key_id is None:
        return None
    try:
        slot_lookup = cast(_SlotLookupOwner, editor)._slot_id_for_key_id
    except AttributeError:
        return None
    return slot_lookup(key_id) if callable(slot_lookup) else None


def _physical_layout_or_none(editor: object) -> str | None:
    try:
        return cast(_PhysicalLayoutOwner, editor)._physical_layout
    except AttributeError:
        return None


def reload_keymap_ui(editor: object) -> None:
    """Reload the saved keymap for the current profile and refresh selection."""

    old = dict(_keymap_or_empty(editor))

    keymap_owner = cast(_MutableKeymapOwner, editor)
    keymap_owner.keymap = cast(_KeymapLoaderProtocol, editor)._load_keymap()

    selected_key_id = _selected_key_id_or_none(editor)
    selected_slot_id = _selected_slot_id_or_none(editor)
    if selected_slot_id is None and selected_key_id is not None:
        selected_slot_id = _slot_id_for_key_id_or_none(editor, selected_key_id)
        _set_selected_slot_id_if_present(editor, selected_slot_id)

    if selected_key_id is not None or selected_slot_id is not None:
        selected_cells = keymap_cells_for(
            keymap_owner.keymap,
            selected_key_id,
            slot_id=selected_slot_id,
            physical_layout=_physical_layout_or_none(editor),
        )
        selection_owner = cast(_MutableSelectionOwner, editor)
        selection_owner.selected_cells = selected_cells
        selection_owner.selected_cell = primary_cell(selected_cells)

    if old != keymap_owner.keymap:
        if keymap_owner.keymap:
            set_status(editor, keymap_reloaded())
        else:
            set_status(editor, no_keymap_found())

    cast(_CanvasOwner, editor).canvas.redraw()
