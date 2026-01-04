from __future__ import annotations

from typing import Iterable


def coerce_rgb_triplet(value: object, *, default: tuple[int, int, int]) -> tuple[int, int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            r, g, b = value
            return int(r), int(g), int(b)
        except Exception:
            return default
    return default


def initial_last_non_black_color(config_color: object) -> tuple[int, int, int]:
    base = coerce_rgb_triplet(config_color, default=(255, 0, 0))
    return base if base != (0, 0, 0) else (255, 0, 0)


def rgb_ints(value: Iterable[object]) -> tuple[int, int, int]:
    r, g, b = value
    return int(r), int(g), int(b)
