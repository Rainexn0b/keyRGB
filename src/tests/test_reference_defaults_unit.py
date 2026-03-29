from __future__ import annotations

from src.core.resources.defaults import (
    DEFAULT_COLORS,
    DEFAULT_KEYMAP,
    REFERENCE_MATRIX_COLS,
    REFERENCE_MATRIX_ROWS,
    build_default_colors,
)


def test_reference_matrix_dimensions_cover_default_keymap() -> None:
    max_row = -1
    max_col = -1
    for coord_text in DEFAULT_KEYMAP.values():
        row_text, col_text = coord_text.split(",", 1)
        max_row = max(max_row, int(row_text))
        max_col = max(max_col, int(col_text))

    assert REFERENCE_MATRIX_ROWS == max_row + 1
    assert REFERENCE_MATRIX_COLS == max_col + 1


def test_build_default_colors_uses_requested_dimensions() -> None:
    colors = build_default_colors(num_rows=2, num_cols=3)

    assert len(colors) == 6
    assert colors[(0, 0)] == (255, 255, 255)
    assert colors[(1, 2)] == (255, 255, 255)
    assert (2, 0) not in colors
    assert (0, 3) not in colors


def test_default_colors_match_reference_dimensions() -> None:
    assert DEFAULT_COLORS == build_default_colors(
        num_rows=REFERENCE_MATRIX_ROWS,
        num_cols=REFERENCE_MATRIX_COLS,
    )