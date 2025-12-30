from __future__ import annotations

from src.gui.perkey.color_apply_ops import apply_color_to_map


def test_apply_color_to_map_updates_selected_cell_only() -> None:
    colors = {(0, 0): (1, 1, 1), (0, 1): (2, 2, 2)}
    out = apply_color_to_map(
        colors=colors,
        num_rows=2,
        num_cols=2,
        color=(9, 8, 7),
        apply_all_keys=False,
        selected_cell=(0, 1),
    )
    assert out[(0, 0)] == (1, 1, 1)
    assert out[(0, 1)] == (9, 8, 7)


def test_apply_color_to_map_no_selected_cell_noop() -> None:
    colors = {(0, 0): (1, 1, 1)}
    out = apply_color_to_map(
        colors=colors,
        num_rows=2,
        num_cols=2,
        color=(9, 8, 7),
        apply_all_keys=False,
        selected_cell=None,
    )
    assert out == colors


def test_apply_color_to_map_apply_all_returns_full_grid() -> None:
    out = apply_color_to_map(
        colors={(0, 0): (1, 1, 1)},
        num_rows=2,
        num_cols=3,
        color=(4, 5, 6),
        apply_all_keys=True,
        selected_cell=(0, 0),
    )
    assert len(out) == 6
    assert out[(0, 0)] == (4, 5, 6)
    assert out[(1, 2)] == (4, 5, 6)
