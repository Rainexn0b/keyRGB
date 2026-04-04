from __future__ import annotations

from src.gui.perkey.color_utils import coerce_rgb_triplet, initial_last_non_black_color, rgb_ints


def test_coerce_rgb_triplet_converts_three_values_to_ints() -> None:
    assert coerce_rgb_triplet(["1", 2.8, True], default=(9, 9, 9)) == (1, 2, 1)


def test_coerce_rgb_triplet_returns_default_for_invalid_values() -> None:
    default = (9, 8, 7)

    assert coerce_rgb_triplet(("x", 2, 3), default=default) == default
    assert coerce_rgb_triplet((1, 2), default=default) == default
    assert coerce_rgb_triplet("1,2,3", default=default) == default


def test_initial_last_non_black_color_uses_red_for_black_or_invalid_input() -> None:
    assert initial_last_non_black_color((0, 0, 0)) == (255, 0, 0)
    assert initial_last_non_black_color("bad") == (255, 0, 0)
    assert initial_last_non_black_color((4, 5, 6)) == (4, 5, 6)


def test_rgb_ints_converts_iterable_items() -> None:
    assert rgb_ints(("10", 20.9, False)) == (10, 20, 0)
