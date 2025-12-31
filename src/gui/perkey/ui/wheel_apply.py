from __future__ import annotations

from typing import Any, Callable

from ..ops.color_apply_ops import apply_color_to_map
from .status import saved_all_keys_rgb, saved_key_rgb, set_status


def on_wheel_color_change_ui(
    editor: Any,
    r: int,
    g: int,
    b: int,
    *,
    num_rows: int,
    num_cols: int,
    apply_fn: Callable[..., dict] = apply_color_to_map,
) -> None:
    """Apply a color while dragging the wheel.

    No UX change: preserves the prior behavior of `PerKeyEditor._on_color_change`.
    """

    color = (r, g, b)
    if color != (0, 0, 0):
        editor._last_non_black_color = color

    if (not editor.apply_all_keys.get()) and (editor.selected_cell is None or not editor.selected_key_id):
        return

    editor.colors = apply_fn(
        colors=dict(editor.colors),
        num_rows=num_rows,
        num_cols=num_cols,
        color=color,
        apply_all_keys=bool(editor.apply_all_keys.get()),
        selected_cell=editor.selected_cell,
    )

    if editor.apply_all_keys.get():
        editor.canvas.redraw()
    else:
        editor.canvas.update_key_visual(editor.selected_key_id, color)

    editor._commit(force=False)


def on_wheel_color_release_ui(
    editor: Any,
    r: int,
    g: int,
    b: int,
    *,
    num_rows: int,
    num_cols: int,
    apply_fn: Callable[..., dict] = apply_color_to_map,
) -> None:
    """Apply a color when releasing the wheel and persist it.

    No UX change: preserves the prior behavior and messages from
    `PerKeyEditor._on_color_release`.
    """

    color = (r, g, b)
    if color != (0, 0, 0):
        editor._last_non_black_color = color

    if (not editor.apply_all_keys.get()) and (editor.selected_cell is None or not editor.selected_key_id):
        return

    editor.colors = apply_fn(
        colors=dict(editor.colors),
        num_rows=num_rows,
        num_cols=num_cols,
        color=color,
        apply_all_keys=bool(editor.apply_all_keys.get()),
        selected_cell=editor.selected_cell,
    )

    if editor.apply_all_keys.get():
        editor.canvas.redraw()
    else:
        editor.canvas.update_key_visual(editor.selected_key_id, color)

    editor._commit(force=True)

    if editor.apply_all_keys.get():
        set_status(editor, saved_all_keys_rgb(r, g, b))
    elif editor.selected_key_id is not None and editor.selected_cell is not None:
        set_status(editor, saved_key_rgb(editor.selected_key_id, r, g, b))
