from __future__ import annotations

from typing import Any

from .status import keymap_reloaded, no_keymap_found, set_status


def reload_keymap_ui(editor: Any) -> None:
    """Reload the current profile keymap and refresh editor selection.

    No UX change: preserves the prior behavior and messages from
    `PerKeyEditor._reload_keymap`.
    """

    old = dict(getattr(editor, "keymap", {}) or {})

    editor.keymap = editor._load_keymap()

    if getattr(editor, "selected_key_id", None) is not None:
        editor.selected_cell = editor.keymap.get(editor.selected_key_id)

    if old != editor.keymap:
        if editor.keymap:
            set_status(editor, keymap_reloaded())
        else:
            set_status(editor, no_keymap_found())

    editor.canvas.redraw()
