from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

from ..profile_management import keymap_cells_for, representative_cell
from .selection import select_visible_identity
from .wheel_apply import on_wheel_color_release_ui
from .status import (
    sample_tool_pick_a_key,
    sample_tool_sampled_color,
    sample_tool_unmapped_key,
    set_status,
)


_TK_WIDGET_ERRORS = (AttributeError, RuntimeError, tk.TclError)
_UI_VALUE_ERRORS = (TypeError, ValueError, OverflowError)
_OVERLAY_SYNC_ERRORS = _TK_WIDGET_ERRORS + _UI_VALUE_ERRORS
_WHEEL_COLOR_ERRORS = _TK_WIDGET_ERRORS + _UI_VALUE_ERRORS


def _redraw_canvas_best_effort(editor: Any) -> None:
    try:
        editor.canvas.redraw()
    except _TK_WIDGET_ERRORS:
        pass


def _key_id_for_slot_identity(editor: Any, slot_id: str) -> str | None:
    key_lookup = getattr(editor, "_key_id_for_slot_id", None)
    if callable(key_lookup):
        key_id = key_lookup(slot_id)
        if key_id:
            return str(key_id)

    visible_lookup = getattr(editor, "_visible_key_for_slot_id", None)
    key = visible_lookup(slot_id) if callable(visible_lookup) else None
    resolved_key_id = getattr(key, "key_id", None) if key is not None else None
    if resolved_key_id:
        return str(resolved_key_id)
    return None


def _set_selected_key_without_updating_wheel(editor: Any, key_id: str) -> None:
    editor.selected_key_id = key_id
    slot_lookup = getattr(editor, "_slot_id_for_key_id", None)
    if callable(slot_lookup):
        editor.selected_slot_id = slot_lookup(key_id)
    editor.selected_cells = keymap_cells_for(
        getattr(editor, "keymap", {}) or {},
        key_id,
        slot_id=getattr(editor, "selected_slot_id", None),
        physical_layout=getattr(editor, "_physical_layout", None),
    )
    editor.selected_cell = representative_cell(editor.selected_cells, colors=getattr(editor, "colors", {}) or {})

    # Keep overlay controls in sync if present.
    try:
        if getattr(editor, "overlay_scope", None) is not None and editor.overlay_scope.get() == "key":
            oc = getattr(editor, "overlay_controls", None)
            if oc is not None:
                sync = getattr(oc, "sync_vars_from_scope", None)
                if callable(sync):
                    sync()
    except _OVERLAY_SYNC_ERRORS:
        pass


def on_sample_tool_toggled_ui(editor: Any) -> None:
    """Reset sample tool state + set an instructional status message."""

    enabled = bool(getattr(getattr(editor, "sample_tool_enabled", None), "get", lambda: False)())
    editor._sample_tool_has_sampled = False

    if enabled:
        set_status(editor, sample_tool_pick_a_key())


def on_key_clicked_ui(
    editor: Any,
    key_id: str,
    *,
    num_rows: int,
    num_cols: int,
    apply_release_fn: Callable[..., None] = on_wheel_color_release_ui,
) -> None:
    """Handle a click on a key in the per-key canvas.

    Behavior:
    - If sample tool is off: normal selection behavior (updates wheel to key color).
    - If sample tool is on and no sample picked yet: sample this key's color into the wheel.
    - If sample tool is on and already sampled: apply the current wheel color to clicked keys.

    This provides an "eyedropper then paint" workflow similar to MSPaint.
    """

    enabled = bool(getattr(getattr(editor, "sample_tool_enabled", None), "get", lambda: False)())

    if not enabled:
        editor._sample_tool_has_sampled = False
        select_visible_identity(editor, key_id=str(key_id))
        return

    key_id = str(key_id)
    keymap = getattr(editor, "keymap", {}) or {}
    cells = keymap_cells_for(
        keymap,
        key_id,
        slot_id=getattr(editor, "selected_slot_id", None),
        physical_layout=getattr(editor, "_physical_layout", None),
    )

    # Update selection highlight even in sample mode.
    _set_selected_key_without_updating_wheel(editor, key_id)

    if not cells:
        set_status(editor, sample_tool_unmapped_key(key_id))
        _redraw_canvas_best_effort(editor)
        return

    colors = getattr(editor, "colors", {}) or {}

    # Stage 1: sample color into the wheel.
    if not bool(getattr(editor, "_sample_tool_has_sampled", False)):
        cell = representative_cell(cells, colors=colors)
        r, g, b = colors.get(cell, (0, 0, 0)) if cell is not None else (0, 0, 0)
        try:
            editor.color_wheel.set_color(int(r), int(g), int(b))
        except _WHEEL_COLOR_ERRORS:
            pass
        editor._sample_tool_has_sampled = True
        set_status(editor, sample_tool_sampled_color(key_id, int(r), int(g), int(b)))
        _redraw_canvas_best_effort(editor)
        return

    # Stage 2: apply current wheel color to clicked keys.
    try:
        r, g, b = editor.color_wheel.get_color()
        r, g, b = int(r), int(g), int(b)
    except _WHEEL_COLOR_ERRORS:
        # Fallback to last known non-black color.
        r, g, b = getattr(editor, "_last_non_black_color", (255, 0, 0)) or (255, 0, 0)
        r, g, b = int(r), int(g), int(b)

    apply_release_fn(editor, r, g, b, num_rows=num_rows, num_cols=num_cols)

    _redraw_canvas_best_effort(editor)


def on_slot_clicked_ui(
    editor: Any,
    slot_id: str,
    *,
    num_rows: int,
    num_cols: int,
    apply_release_fn: Callable[..., None] = on_wheel_color_release_ui,
) -> None:
    enabled = bool(getattr(getattr(editor, "sample_tool_enabled", None), "get", lambda: False)())

    if not enabled:
        editor._sample_tool_has_sampled = False
        select_slot = getattr(editor, "select_slot_id", None)
        if callable(select_slot):
            select_slot(str(slot_id))
            return

        key_id = _key_id_for_slot_identity(editor, str(slot_id))
        select_key = getattr(editor, "select_key_id", None)
        if key_id is not None and callable(select_key):
            select_key(str(key_id))
        return

    key_id = _key_id_for_slot_identity(editor, str(slot_id))
    if key_id is None:
        return

    on_key_clicked_ui(
        editor,
        str(key_id),
        num_rows=num_rows,
        num_cols=num_cols,
        apply_release_fn=apply_release_fn,
    )
