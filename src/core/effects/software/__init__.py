"""Software-rendered (CPU) effects package."""

from __future__ import annotations

from .base import Color, Key, base_color_map, clamp01, frame_dt_s, has_per_key, mix, pace, render, scale
from .effects import (
    run_breathing,
    run_chase,
    run_color_cycle,
    run_fire,
    run_rain,
    run_rainbow_swirl,
    run_rainbow_wave,
    run_random,
    run_spectrum_cycle,
    run_strobe,
    run_twinkle,
)

__all__ = [
    "Color",
    "Key",
    "clamp01",
    "pace",
    "frame_dt_s",
    "has_per_key",
    "base_color_map",
    "mix",
    "scale",
    "render",
    "run_breathing",
    "run_fire",
    "run_random",
    "run_rainbow_wave",
    "run_rainbow_swirl",
    "run_spectrum_cycle",
    "run_color_cycle",
    "run_twinkle",
    "run_strobe",
    "run_chase",
    "run_rain",
]
