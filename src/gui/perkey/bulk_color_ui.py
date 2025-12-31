from __future__ import annotations

from typing import Any, Callable

from .color_map_ops import clear_all, fill_all
from .keyboard_apply import push_per_key_colors
from .status_ui import cleared_all_keys, filled_all_keys_rgb, set_status


def fill_all_ui(
    editor: Any,
    *,
    num_rows: int,
    num_cols: int,
    fill_fn: Callable[..., dict] = fill_all,
) -> None:
    """Fill all keys with the current wheel color and commit.

    No UX change: preserves the prior behavior and messages from
    `PerKeyEditor._fill_all`.
    """

    r, g, b = editor.color_wheel.get_color()
    color = (r, g, b)

    editor.colors = fill_fn(num_rows=num_rows, num_cols=num_cols, color=color)

    editor.canvas.redraw()
    editor._commit(force=True)
    set_status(editor, filled_all_keys_rgb(r, g, b))


def clear_all_ui(
    editor: Any,
    *,
    num_rows: int,
    num_cols: int,
    clear_fn: Callable[..., dict] = clear_all,
    push_fn: Callable[..., Any] = push_per_key_colors,
) -> None:
    """Clear all keys (set to off) and push to hardware.

    No UX change: preserves the prior behavior and messages from
    `PerKeyEditor._clear_all`.
    """

    editor.colors = clear_fn(num_rows=num_rows, num_cols=num_cols)
    editor.canvas.redraw()
    editor.config.effect = "perkey"
    editor.config.per_key_colors = editor.colors

    editor.kb = push_fn(
        editor.kb,
        editor.colors,
        brightness=int(editor.config.brightness),
        enable_user_mode=True,
    )

    set_status(editor, cleared_all_keys())
