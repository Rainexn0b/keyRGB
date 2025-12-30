from __future__ import annotations

from typing import Dict, Tuple

Color = Tuple[int, int, int]
Cell = Tuple[int, int]
ColorMap = Dict[Cell, Color]


def fill_all(*, num_rows: int, num_cols: int, color: Color) -> ColorMap:
    """Return a full grid filled with a single color."""

    r, g, b = int(color[0]), int(color[1]), int(color[2])
    filled: ColorMap = {}
    for row in range(int(num_rows)):
        for col in range(int(num_cols)):
            filled[(row, col)] = (r, g, b)
    return filled


def clear_all(*, num_rows: int, num_cols: int) -> ColorMap:
    """Return a full grid cleared to black."""

    return fill_all(num_rows=num_rows, num_cols=num_cols, color=(0, 0, 0))


def ensure_full_map(
    *,
    colors: ColorMap,
    num_rows: int,
    num_cols: int,
    base_color: Color,
    fallback_color: Color,
) -> ColorMap:
    """Ensure the color map covers every cell.

    Preserves existing entries, and fills missing cells using base_color.
    If base_color is black, uses fallback_color instead.
    """

    if len(colors) >= (int(num_rows) * int(num_cols)):
        return dict(colors)

    base = (int(base_color[0]), int(base_color[1]), int(base_color[2]))
    if base == (0, 0, 0):
        base = (int(fallback_color[0]), int(fallback_color[1]), int(fallback_color[2]))

    out: ColorMap = dict(colors)
    for row in range(int(num_rows)):
        for col in range(int(num_cols)):
            out.setdefault((row, col), base)

    return out
