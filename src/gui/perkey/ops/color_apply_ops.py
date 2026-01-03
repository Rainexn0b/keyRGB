from __future__ import annotations

from typing import Optional, Tuple

from .color_map_ops import Color, ColorMap, fill_all


def apply_color_to_map(
    *,
    colors: ColorMap,
    num_rows: int,
    num_cols: int,
    color: Color,
    apply_all_keys: bool,
    selected_cell: Optional[Tuple[int, int]],
) -> ColorMap:
    """Apply a color selection to the per-key color map.

    - If apply_all_keys is True: returns a full grid with the chosen color.
    - Else: returns a copy with selected_cell updated (or unchanged if none).

    Pure helper: does not touch UI, config, or hardware.
    """

    if bool(apply_all_keys):
        return fill_all(num_rows=int(num_rows), num_cols=int(num_cols), color=color)

    if selected_cell is None:
        return dict(colors)

    out: ColorMap = dict(colors)
    row, col = int(selected_cell[0]), int(selected_cell[1])
    out[(row, col)] = (int(color[0]), int(color[1]), int(color[2]))
    return out
