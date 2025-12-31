from __future__ import annotations

from typing import Any, Callable

from .wheel_apply_ui import on_wheel_color_release_ui
from .status_ui import (
    sample_tool_pick_a_key,
    sample_tool_sampled_color,
    sample_tool_unmapped_key,
    set_status,
)


def _set_selected_key_without_updating_wheel(editor: Any, key_id: str) -> None:
    editor.selected_key_id = key_id
    editor.selected_cell = (getattr(editor, "keymap", {}) or {}).get(key_id)

    # Keep overlay controls in sync if present.
    try:
        if getattr(editor, "overlay_scope", None) is not None and editor.overlay_scope.get() == "key":
            oc = getattr(editor, "overlay_controls", None)
            if oc is not None:
                sync = getattr(oc, "sync_vars_from_scope", None)
                if callable(sync):
                    sync()
    except Exception:
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
        editor.select_key_id(str(key_id))
        return

    key_id = str(key_id)
    keymap = getattr(editor, "keymap", {}) or {}
    cell = keymap.get(key_id)

    # Update selection highlight even in sample mode.
    _set_selected_key_without_updating_wheel(editor, key_id)

    if cell is None:
        set_status(editor, sample_tool_unmapped_key(key_id))
        try:
            editor.canvas.redraw()
        except Exception:
            pass
        return

    colors = getattr(editor, "colors", {}) or {}

    # Stage 1: sample color into the wheel.
    if not bool(getattr(editor, "_sample_tool_has_sampled", False)):
        r, g, b = colors.get(cell, (0, 0, 0))
        try:
            editor.color_wheel.set_color(int(r), int(g), int(b))
        except Exception:
            pass
        editor._sample_tool_has_sampled = True
        set_status(editor, sample_tool_sampled_color(key_id, int(r), int(g), int(b)))
        try:
            editor.canvas.redraw()
        except Exception:
            pass
        return

    # Stage 2: apply current wheel color to clicked keys.
    try:
        r, g, b = editor.color_wheel.get_color()
        r, g, b = int(r), int(g), int(b)
    except Exception:
        # Fallback to last known non-black color.
        r, g, b = (getattr(editor, "_last_non_black_color", (255, 0, 0)) or (255, 0, 0))
        r, g, b = int(r), int(g), int(b)

    apply_release_fn(editor, r, g, b, num_rows=num_rows, num_cols=num_cols)

    try:
        editor.canvas.redraw()
    except Exception:
        pass
