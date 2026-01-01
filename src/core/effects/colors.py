from __future__ import annotations

import colorsys
from typing import Tuple


def hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
    """Convert HSV to RGB (h: 0-1, s: 0-1, v: 0-1)."""

    r, g, b = colorsys.hsv_to_rgb(float(h), float(s), float(v))
    return (int(r * 255), int(g * 255), int(b * 255))
