from __future__ import annotations

from typing import Any

from ..profile_management import keymap_cells_for, primary_cell
from .status import keymap_reloaded, no_keymap_found, set_status


def reload_keymap_ui(editor: Any) -> None:
    """Reload the saved keymap for the current profile and refresh selection."""

    old = dict(getattr(editor, "keymap", {}) or {})

    editor.keymap = editor._load_keymap()

    selected_key_id = getattr(editor, "selected_key_id", None)
    selected_slot_id = getattr(editor, "selected_slot_id", None)
    if selected_slot_id is None and selected_key_id is not None:
        slot_lookup = getattr(editor, "_slot_id_for_key_id", None)
        if callable(slot_lookup):
            selected_slot_id = slot_lookup(selected_key_id)
            if hasattr(editor, "selected_slot_id"):
                editor.selected_slot_id = selected_slot_id

    if selected_key_id is not None or selected_slot_id is not None:
        editor.selected_cells = keymap_cells_for(
            editor.keymap,
            selected_key_id,
            slot_id=selected_slot_id,
            physical_layout=getattr(editor, "_physical_layout", None),
        )
        editor.selected_cell = primary_cell(editor.selected_cells)

    if old != editor.keymap:
        if editor.keymap:
            set_status(editor, keymap_reloaded())
        else:
            set_status(editor, no_keymap_found())

    editor.canvas.redraw()
