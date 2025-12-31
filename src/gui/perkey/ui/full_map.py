from __future__ import annotations

from typing import Any, Callable

from ..ops.color_map_ops import ensure_full_map


def ensure_full_map_ui(
    editor: Any,
    *,
    num_rows: int,
    num_cols: int,
    ensure_fn: Callable[..., dict] = ensure_full_map,
) -> None:
    """Ensure the per-key color map fully covers the keyboard.

    No UX change: preserves the prior behavior of `PerKeyEditor._ensure_full_map`.
    """

    # Use the last non-black wheel color as the base fill. This matches the
    # expected workflow: start from a unified color, then override a few keys
    # without blanking the rest of the keyboard.
    last = getattr(editor, "_last_non_black_color", None)
    if isinstance(last, (list, tuple)) and len(last) == 3:
        base = (int(last[0]), int(last[1]), int(last[2]))
    else:
        fallback = tuple(editor.config.color)
        base = (int(fallback[0]), int(fallback[1]), int(fallback[2]))

    fallback = tuple(editor.config.color)

    editor.colors = ensure_fn(
        colors=dict(editor.colors),
        num_rows=num_rows,
        num_cols=num_cols,
        base_color=base,
        fallback_color=fallback,
    )
