from __future__ import annotations

from typing import Protocol, cast

from ..ops.color_map_ops import Color, ColorMap, ensure_full_map


class _ConfigProtocol(Protocol):
    color: Color


class _FullMapEditorProtocol(Protocol):
    config: _ConfigProtocol
    colors: ColorMap


class _LastNonBlackColorOwner(Protocol):
    _last_non_black_color: object | None


class _EnsureFullMapFn(Protocol):
    def __call__(
        self,
        *,
        colors: ColorMap,
        num_rows: int,
        num_cols: int,
        base_color: Color,
        fallback_color: Color,
    ) -> ColorMap: ...


def _config_color(editor: _FullMapEditorProtocol) -> Color:
    color = editor.config.color
    return int(color[0]), int(color[1]), int(color[2])


def _last_non_black_color_or_none(editor: object) -> Color | None:
    try:
        color = cast(_LastNonBlackColorOwner, editor)._last_non_black_color
    except AttributeError:
        return None
    if not isinstance(color, (list, tuple)) or len(color) != 3:
        return None
    return int(color[0]), int(color[1]), int(color[2])


def ensure_full_map_ui(
    editor: _FullMapEditorProtocol,
    *,
    num_rows: int,
    num_cols: int,
    ensure_fn: _EnsureFullMapFn = ensure_full_map,
) -> None:
    """Ensure the per-key color map fully covers the keyboard.

    No UX change: preserves the prior behavior of `PerKeyEditor._ensure_full_map`.
    """

    # Use the last non-black wheel color as the base fill. This matches the
    # expected workflow: start from a unified color, then override a few keys
    # without blanking the rest of the keyboard.
    fallback = _config_color(editor)
    last = _last_non_black_color_or_none(editor)
    base = last if last is not None else fallback

    editor.colors = ensure_fn(
        colors=dict(editor.colors),
        num_rows=num_rows,
        num_cols=num_cols,
        base_color=base,
        fallback_color=fallback,
    )
