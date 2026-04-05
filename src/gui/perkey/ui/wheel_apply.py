from __future__ import annotations

from typing import Any, Callable

from ..ops.color_apply_ops import apply_color_to_map
from ..profile_management import keymap_cells_for
from .status import saved_all_keys_rgb, saved_key_rgb, set_status


def _physical_layout_or_none(editor: Any) -> object | None:
    try:
        return editor._physical_layout
    except AttributeError:
        return None


def _selected_key_id_for_slot(editor: Any, selected_key_id: str | None, selected_slot_id: str | None) -> str | None:
    if selected_key_id is not None or selected_slot_id is None:
        return selected_key_id

    try:
        return editor._key_id_for_slot_id(selected_slot_id)
    except AttributeError:
        return None


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

    selected_slot_id = getattr(editor, "selected_slot_id", None)
    selected_key_id = _selected_key_id_for_slot(editor, getattr(editor, "selected_key_id", None), selected_slot_id)
    selected_identity = selected_slot_id or selected_key_id

    selected_cells = tuple(
        getattr(editor, "selected_cells", ())
        or keymap_cells_for(
            editor.keymap,
            selected_key_id,
            slot_id=selected_slot_id,
            physical_layout=_physical_layout_or_none(editor),
        )
    )

    if (not editor.apply_all_keys.get()) and (not selected_cells or not selected_identity):
        return

    editor.colors = apply_fn(
        colors=dict(editor.colors),
        num_rows=num_rows,
        num_cols=num_cols,
        color=color,
        apply_all_keys=bool(editor.apply_all_keys.get()),
        selected_cells=selected_cells,
    )

    if editor.apply_all_keys.get():
        editor.canvas.redraw()
    else:
        editor.canvas.update_key_visual(str(selected_identity), color)

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

    selected_slot_id = getattr(editor, "selected_slot_id", None)
    selected_key_id = _selected_key_id_for_slot(editor, getattr(editor, "selected_key_id", None), selected_slot_id)
    selected_identity = selected_slot_id or selected_key_id

    selected_cells = tuple(
        getattr(editor, "selected_cells", ())
        or keymap_cells_for(
            editor.keymap,
            selected_key_id,
            slot_id=selected_slot_id,
            physical_layout=_physical_layout_or_none(editor),
        )
    )

    if (not editor.apply_all_keys.get()) and (not selected_cells or not selected_identity):
        return

    editor.colors = apply_fn(
        colors=dict(editor.colors),
        num_rows=num_rows,
        num_cols=num_cols,
        color=color,
        apply_all_keys=bool(editor.apply_all_keys.get()),
        selected_cells=selected_cells,
    )

    if editor.apply_all_keys.get():
        editor.canvas.redraw()
    else:
        editor.canvas.update_key_visual(str(selected_identity), color)

    editor._commit(force=True)

    if editor.apply_all_keys.get():
        set_status(editor, saved_all_keys_rgb(r, g, b))
    elif selected_cells and selected_identity is not None:
        set_status(editor, saved_key_rgb(str(selected_key_id or selected_identity), r, g, b))
