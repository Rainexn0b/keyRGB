from __future__ import annotations

from typing import Protocol

from src.core.backends.base import KeyboardDevice

from ..keyboard_apply import push_per_key_colors
from ..ops.color_map_ops import Color, ColorMap, clear_all, fill_all
from .status import cleared_all_keys, filled_all_keys_rgb, set_status


class _ColorWheelProtocol(Protocol):
    def get_color(self) -> Color: ...


class _CanvasProtocol(Protocol):
    def redraw(self) -> None: ...


class _ConfigProtocol(Protocol):
    brightness: int
    effect: str | None
    per_key_colors: ColorMap | None


class _BulkColorEditorProtocol(Protocol):
    color_wheel: _ColorWheelProtocol
    canvas: _CanvasProtocol
    config: _ConfigProtocol
    kb: KeyboardDevice | None
    colors: ColorMap

    def _commit(self, *, force: bool) -> None: ...


class _FillAllFn(Protocol):
    def __call__(self, *, num_rows: int, num_cols: int, color: Color) -> ColorMap: ...


class _ClearAllFn(Protocol):
    def __call__(self, *, num_rows: int, num_cols: int) -> ColorMap: ...


class _PushPerKeyColorsFn(Protocol):
    def __call__(
        self,
        kb: KeyboardDevice | None,
        colors: ColorMap,
        *,
        brightness: int,
        enable_user_mode: bool = True,
    ) -> KeyboardDevice | None: ...


def fill_all_ui(
    editor: _BulkColorEditorProtocol,
    *,
    num_rows: int,
    num_cols: int,
    fill_fn: _FillAllFn = fill_all,
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
    editor: _BulkColorEditorProtocol,
    *,
    num_rows: int,
    num_cols: int,
    clear_fn: _ClearAllFn = clear_all,
    push_fn: _PushPerKeyColorsFn = push_per_key_colors,
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
