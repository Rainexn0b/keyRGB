from __future__ import annotations

from collections.abc import Sequence

from keyrgb.core.lighting_layers import zone_cells_for_column

from .color_map_ops import Color, ColorMap, fill_all


def apply_color_to_map(
    *,
    colors: ColorMap,
    num_rows: int,
    num_cols: int,
    color: Color,
    apply_all_keys: bool,
    selected_cells: Sequence[tuple[int, int]] | None,
    zone_count: int = 0,
) -> ColorMap:
    """Apply a color selection to the per-key color map.

    - If apply_all_keys is True: returns a full grid with the chosen color.
    - Else: returns a copy with all selected_cells updated (or unchanged if none).
    - When zone_count > 1, each selected cell expands to its whole zone band.

    Pure helper: does not touch UI, config, or hardware.
    """

    if bool(apply_all_keys):
        return fill_all(num_rows=int(num_rows), num_cols=int(num_cols), color=color)

    if not selected_cells:
        return dict(colors)

    cells = list(selected_cells)
    if int(zone_count) > 1:
        expanded: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for selected_cell in cells:
            for cell in zone_cells_for_column(
                num_rows=int(num_rows),
                num_cols=int(num_cols),
                zone_count=int(zone_count),
                column=int(selected_cell[1]),
            ):
                if cell not in seen:
                    seen.add(cell)
                    expanded.append(cell)
        cells = expanded

    out: ColorMap = dict(colors)
    rgb = (int(color[0]), int(color[1]), int(color[2]))
    for selected_cell in cells:
        row, col = int(selected_cell[0]), int(selected_cell[1])
        out[(row, col)] = rgb
    return out
