from __future__ import annotations

from ..profile_management import keymap_cells_for
from . import _sample_tool_support as _support
from .selection import select_visible_identity
from .wheel_apply import on_wheel_color_release_ui
from .status import (
    sample_tool_pick_a_key,
    sample_tool_sampled_color,
    sample_tool_unmapped_key,
    set_status,
)


def on_sample_tool_toggled_ui(editor: _support._SampleToolToggleEditorProtocol) -> None:
    """Reset sample tool state + set an instructional status message."""

    enabled = _support._sample_tool_enabled(editor)
    editor._sample_tool_has_sampled = False

    if enabled:
        set_status(editor, sample_tool_pick_a_key())


def on_key_clicked_ui(
    editor: _support._SampleToolEditorProtocol,
    key_id: str,
    *,
    num_rows: int,
    num_cols: int,
    apply_release_fn: _support._ApplyReleaseFn = on_wheel_color_release_ui,
) -> None:
    """Handle a click on a key in the per-key canvas.

    Behavior:
    - If sample tool is off: normal selection behavior (updates wheel to key color).
    - If sample tool is on and no sample picked yet: sample this key's color into the wheel.
    - If sample tool is on and already sampled: apply the current wheel color to clicked keys.

    This provides an "eyedropper then paint" workflow similar to MSPaint.
    """

    enabled = _support._sample_tool_enabled(editor)

    if not enabled:
        editor._sample_tool_has_sampled = False
        select_visible_identity(editor, key_id=str(key_id))
        return

    key_id = str(key_id)
    cells = keymap_cells_for(
        _support._keymap_or_empty(editor),
        key_id,
        slot_id=editor.selected_slot_id,
        physical_layout=_support._physical_layout_or_none(editor),
    )

    # Update selection highlight even in sample mode.
    _support._set_selected_key_without_updating_wheel(editor, key_id)

    if not cells:
        set_status(editor, sample_tool_unmapped_key(key_id))
        _support._redraw_canvas_best_effort(editor)
        return

    # Stage 1: sample color into the wheel.
    if not bool(editor._sample_tool_has_sampled):
        r, g, b = _support._sample_selected_color_into_wheel(editor, cells)
        set_status(editor, sample_tool_sampled_color(key_id, r, g, b))
        _support._redraw_canvas_best_effort(editor)
        return

    # Stage 2: apply current wheel color to clicked keys.
    r, g, b = _support._current_or_fallback_wheel_color(editor)

    apply_release_fn(editor, r, g, b, num_rows=num_rows, num_cols=num_cols)

    _support._redraw_canvas_best_effort(editor)


def on_slot_clicked_ui(
    editor: _support._SampleToolEditorProtocol,
    slot_id: str,
    *,
    num_rows: int,
    num_cols: int,
    apply_release_fn: _support._ApplyReleaseFn = on_wheel_color_release_ui,
) -> None:
    enabled = _support._sample_tool_enabled(editor)

    if not enabled:
        editor._sample_tool_has_sampled = False
        if _support._select_slot_id_if_present(editor, str(slot_id)):
            return

        key_id = _support._key_id_for_slot_identity(editor, str(slot_id))
        if key_id is not None:
            _support._select_key_id_if_present(editor, str(key_id))
        return

    key_id = _support._key_id_for_slot_identity(editor, str(slot_id))
    if key_id is None:
        return

    on_key_clicked_ui(
        editor,
        str(key_id),
        num_rows=num_rows,
        num_cols=num_cols,
        apply_release_fn=apply_release_fn,
    )
