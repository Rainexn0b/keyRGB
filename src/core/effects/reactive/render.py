from __future__ import annotations

import logging
import time as _time
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from src.core.effects.matrix_layout import NUM_COLS, NUM_ROWS
from src.core.effects.perkey_animation import build_full_color_grid

from ._render_brightness import (
    resolve_brightness as _resolve_brightness_impl,
    resolve_reactive_transition_brightness as _resolve_reactive_transition_brightness_impl,
)
from ._render_runtime import render_per_key_frame, render_uniform_frame

logger = logging.getLogger(__name__)
time = _time

# Maximum brightness change per render frame before the stability guard
# clamps. Prevents single-frame jumps (e.g. 3 -> 50) caused by race
# conditions between concurrent brightness writers.
_MAX_BRIGHTNESS_STEP_PER_FRAME: int = 8

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine

Color = Tuple[int, int, int]
Key = Tuple[int, int]


def clamp01(x: float) -> float:
    return 0.0 if x <= 0.0 else (1.0 if x >= 1.0 else x)


def mix(a: Color, b: Color, t: float) -> Color:
    tt = clamp01(t)
    return (
        int(round(a[0] + (b[0] - a[0]) * tt)),
        int(round(a[1] + (b[1] - a[1]) * tt)),
        int(round(a[2] + (b[2] - a[2]) * tt)),
    )


def scale(rgb: Color, s: float) -> Color:
    ss = clamp01(s)
    return (int(round(rgb[0] * ss)), int(round(rgb[1] * ss)), int(round(rgb[2] * ss)))


def _resolve_reactive_transition_brightness(engine: "EffectsEngine") -> Optional[tuple[int, bool]]:
    return _resolve_reactive_transition_brightness_impl(engine, clamp01_fn=clamp01)


def _resolve_brightness(engine: "EffectsEngine") -> Tuple[int, int, int]:
    return _resolve_brightness_impl(
        engine,
        max_step_per_frame=_MAX_BRIGHTNESS_STEP_PER_FRAME,
        clamp01_fn=clamp01,
        logger=logger,
    )


def backdrop_brightness_scale_factor(engine: "EffectsEngine", *, effect_brightness_hw: int) -> float:
    """Compute scaling factor to keep the backdrop at its target brightness.

    If the global hardware brightness is driven higher (by the effect brightness),
    we scale the backdrop down.
    """
    base, _, hw = _resolve_brightness(engine)

    if hw <= 0:
        return 0.0

    if base >= hw:
        return 1.0

    return float(base) / float(hw)


def pulse_brightness_scale_factor(engine: "EffectsEngine") -> float:
    """Compute scaling factor to keep pulses at their target brightness.

    This is expressed relative to the resolved hardware brightness used for
    rendering. Uniform-only backends may transiently raise the hardware
    brightness to make bright pulses possible over a dim backdrop; per-key
    backends keep hardware brightness fixed and rely on per-key color contrast.
    For per-key hardware the reactive slider should therefore control the pulse
    color intensity directly across the full 0..50 range instead of saturating
    as soon as ``reactive_brightness >= hw``.
    """

    _, eff, hw = _resolve_brightness(engine)

    if has_per_key(engine):
        return float(max(0, min(50, int(eff)))) / 50.0

    if hw <= 0:
        return 0.0

    if eff >= hw:
        return 1.0

    return float(eff) / float(hw)


def apply_backdrop_brightness_scale(color_map: Dict[Key, Color], *, factor: float) -> Dict[Key, Color]:
    """Return a scaled copy of a per-key base map."""

    f = float(factor)
    if f >= 0.999:
        return dict(color_map)
    if f <= 0.0:
        return {k: (0, 0, 0) for k in color_map.keys()}
    return {k: scale(rgb, f) for k, rgb in color_map.items()}


def frame_dt_s() -> float:
    return 1.0 / 60.0


def pace(engine: "EffectsEngine", *, min_factor: float = 0.8, max_factor: float = 2.2) -> float:
    """Map UI speed (0..10) to an effect pace multiplier.

    Matches the quadratic mapping used by the SW loops: speed=10 is much faster.
    """

    try:
        s = int(getattr(engine, "speed", 4) or 0)
    except (TypeError, ValueError):
        s = 4

    s = max(0, min(10, s))
    t = float(s) / 10.0
    t = t * t

    min_factor = float(min_factor)
    max_factor = float(max_factor)
    if min_factor == 0.8 and max_factor == 2.2:
        min_factor = 0.25
        max_factor = 10.0

    return float(min_factor + (max_factor - min_factor) * t)


def has_per_key(engine: "EffectsEngine") -> bool:
    return bool(getattr(getattr(engine, "kb", None), "set_key_colors", None))


def base_color_map(engine: "EffectsEngine") -> Dict[Key, Color]:
    base_color_src = getattr(engine, "current_color", None) or (255, 0, 0)
    base_color = (
        int(base_color_src[0]),
        int(base_color_src[1]),
        int(base_color_src[2]),
    )

    per_key = getattr(engine, "per_key_colors", None) or None
    if not per_key:
        return {(r, c): base_color for r in range(NUM_ROWS) for c in range(NUM_COLS)}

    full = build_full_color_grid(
        base_color=base_color,
        per_key_colors=per_key,
        num_rows=NUM_ROWS,
        num_cols=NUM_COLS,
    )

    out: Dict[Key, Color] = {}
    for (r, c), rgb in full.items():
        out[(r, c)] = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
    return out


def render(engine: "EffectsEngine", *, color_map: Dict[Key, Color]) -> None:
    if has_per_key(engine) and render_per_key_frame(
        engine,
        color_map=color_map,
        resolve_brightness=_resolve_brightness,
        logger=logger,
    ):
        return

    render_uniform_frame(
        engine,
        color_map=color_map,
        resolve_brightness=_resolve_brightness,
    )
