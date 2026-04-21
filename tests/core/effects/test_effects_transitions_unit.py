from __future__ import annotations

from src.core.effects.transitions import avoid_full_black, choose_steps, scaled_color_map_nonzero


def test_choose_steps_duration_non_positive_returns_one() -> None:
    assert choose_steps(duration_s=0.0, max_steps=10) == 1


def test_choose_steps_clamps_max_steps_high_and_low() -> None:
    assert choose_steps(duration_s=2.0, max_steps=999, target_fps=120.0) == 60
    assert choose_steps(duration_s=1.0, max_steps=0, target_fps=30.0) == 2


def test_choose_steps_clamps_target_fps_to_minimum() -> None:
    assert choose_steps(duration_s=3.0, max_steps=60, target_fps=0.0) == 3


def test_choose_steps_takes_min_dt_branch_when_dt_too_small() -> None:
    assert choose_steps(duration_s=1.0, max_steps=60, target_fps=60.0, min_dt_s=0.1) == 10


def test_choose_steps_normal_branch_without_min_dt_adjustment() -> None:
    assert choose_steps(duration_s=0.5, max_steps=60, target_fps=20.0, min_dt_s=0.01) == 10


def test_avoid_full_black_brightness_non_positive_passthrough() -> None:
    rgb = (0, 0, 0)
    assert avoid_full_black(rgb=rgb, target_rgb=(5, 6, 7), brightness=0) == rgb


def test_avoid_full_black_target_black_passthrough() -> None:
    rgb = (0, 0, 0)
    assert avoid_full_black(rgb=rgb, target_rgb=(0, 0, 0), brightness=10) == rgb


def test_avoid_full_black_non_black_rgb_passthrough() -> None:
    rgb = (2, 0, 0)
    assert avoid_full_black(rgb=rgb, target_rgb=(0, 3, 0), brightness=10) == rgb


def test_avoid_full_black_zero_to_nonzero_returns_tiny_color() -> None:
    assert avoid_full_black(rgb=(0, 0, 0), target_rgb=(9, 0, 5), brightness=5) == (1, 0, 1)


def test_avoid_full_black_defensive_fallback_returns_red_hint() -> None:
    class Zeroish:
        def __int__(self) -> int:
            return 0

    z = Zeroish()
    assert avoid_full_black(rgb=(0, 0, 0), target_rgb=(z, z, z), brightness=5) == (1, 0, 0)


def test_scaled_color_map_nonzero_black_entries_remain_black() -> None:
    out = scaled_color_map_nonzero({(0, 0): (0, 0, 0)}, scale=0.5, brightness=25)
    assert out[(0, 0)] == (0, 0, 0)


def test_scaled_color_map_nonzero_scales_non_black_entries() -> None:
    out = scaled_color_map_nonzero({(0, 1): (100, 200, 50)}, scale=0.5, brightness=25)
    assert out[(0, 1)] == (50, 100, 25)


def test_scaled_color_map_nonzero_preserves_tiny_nonzero_hint() -> None:
    out = scaled_color_map_nonzero({(1, 1): (5, 1, 0)}, scale=0.1, brightness=25)
    assert out[(1, 1)] == (1, 1, 0)
