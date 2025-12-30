from __future__ import annotations

from src.gui.perkey.color_map_ops import clear_all, ensure_full_map, fill_all


def test_fill_all_builds_full_grid() -> None:
    colors = fill_all(num_rows=2, num_cols=3, color=(1, 2, 3))
    assert len(colors) == 6
    assert colors[(0, 0)] == (1, 2, 3)
    assert colors[(1, 2)] == (1, 2, 3)


def test_clear_all_is_black() -> None:
    colors = clear_all(num_rows=1, num_cols=2)
    assert colors[(0, 0)] == (0, 0, 0)
    assert colors[(0, 1)] == (0, 0, 0)


def test_ensure_full_map_preserves_existing_and_fills_missing() -> None:
    existing = {(0, 0): (9, 9, 9)}
    out = ensure_full_map(
        colors=existing,
        num_rows=2,
        num_cols=2,
        base_color=(1, 2, 3),
        fallback_color=(7, 7, 7),
    )

    assert out[(0, 0)] == (9, 9, 9)
    assert out[(0, 1)] == (1, 2, 3)
    assert out[(1, 0)] == (1, 2, 3)
    assert out[(1, 1)] == (1, 2, 3)


def test_ensure_full_map_uses_fallback_when_base_black() -> None:
    out = ensure_full_map(
        colors={},
        num_rows=1,
        num_cols=2,
        base_color=(0, 0, 0),
        fallback_color=(4, 5, 6),
    )

    assert out[(0, 0)] == (4, 5, 6)
    assert out[(0, 1)] == (4, 5, 6)
