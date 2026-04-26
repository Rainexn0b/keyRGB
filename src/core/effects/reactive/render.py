from __future__ import annotations

import logging
import time as _time
from operator import attrgetter
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from src.core.effects.matrix_layout import NUM_COLS, NUM_ROWS
from src.core.effects.perkey_animation import build_full_color_grid

from . import _render_brightness_support as _support
from ._render_brightness import (
    resolve_brightness as _resolve_brightness_impl,
    resolve_reactive_transition_brightness as _resolve_reactive_transition_brightness_impl,
    resolve_reactive_transition_visual_scale as _resolve_reactive_transition_visual_scale_impl,
)
from ._render_runtime import render_per_key_frame, render_uniform_frame

logger = logging.getLogger(__name__)
time = _time

# Maximum brightness change per render frame before the stability guard
# clamps. Prevents single-frame jumps (e.g. 3 -> 50) caused by race
# conditions between concurrent brightness writers.
_MAX_BRIGHTNESS_STEP_PER_FRAME: int = 8
_POST_RESTORE_PULSE_VISUAL_HOLDOFF_S: float = 2.0
_POST_RESTORE_PULSE_VISUAL_MIN_FACTOR: float = 0.35

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine

Color = Tuple[int, int, int]
Key = Tuple[int, int]
_INT_COERCION_ERRORS = (TypeError, ValueError)


def _engine_attr_or_default(engine: "EffectsEngine", attr_name: str, *, default: object) -> object:
    try:
        return attrgetter(attr_name)(engine)
    except AttributeError:
        return default


def _keyboard_attr_or_none(engine: "EffectsEngine", attr_name: str) -> object | None:
    kb = _engine_attr_or_default(engine, "kb", default=None)
    if kb is None:
        return None
    try:
        return attrgetter(attr_name)(kb)
    except AttributeError:
        return None


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


def _resolve_transition_visual_scale(engine: "EffectsEngine") -> float:
    return _resolve_reactive_transition_visual_scale_impl(engine, clamp01_fn=clamp01)


def _post_restore_visual_damp(engine: "EffectsEngine") -> tuple[float, float]:
    raw_until = _support.read_engine_attr(
        engine,
        "_reactive_post_restore_visual_damp_until",
        missing_default=None,
        error_default=None,
        logger=logger,
    )
    until_s = _support.coerce_float(raw_until, default=None)
    if until_s is None:
        return 1.0, 0.0

    remaining_s = max(0.0, float(until_s) - float(time.monotonic()))
    if remaining_s <= 0.0:
        return 1.0, 0.0

    progress = 1.0 - min(1.0, remaining_s / _POST_RESTORE_PULSE_VISUAL_HOLDOFF_S)
    damp = _POST_RESTORE_PULSE_VISUAL_MIN_FACTOR + ((1.0 - _POST_RESTORE_PULSE_VISUAL_MIN_FACTOR) * progress)
    return damp, remaining_s


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
    color intensity directly across the full 0..50 range. Any extra suppression
    must stay scoped to explicit post-restore recovery windows so normal low-
    brightness typing still uses the configured reactive level.
    """

    base, eff, hw = _resolve_brightness(engine)

    if has_per_key(engine):
        pulse_scale = float(max(0, min(50, int(eff)))) / 50.0
        target_hw = _steady_target_hw_brightness(engine, base=base)
        visual_hw = min(int(hw), int(target_hw))
        if visual_hw <= 0:
            _support.log_pulse_visual_scale_change(
                engine,
                logger=logger,
                base=base,
                eff=eff,
                hw=hw,
                target_hw=target_hw,
                visual_hw=visual_hw,
                pulse_scale=0.0,
                contrast_ratio=0.0,
                contrast_compression=0.0,
                very_dim_curve=False,
                post_restore_holdoff_remaining_s=0.0,
                post_restore_damp=1.0,
            )
            return 0.0
        if eff <= visual_hw:
            _support.log_pulse_visual_scale_change(
                engine,
                logger=logger,
                base=base,
                eff=eff,
                hw=hw,
                target_hw=target_hw,
                visual_hw=visual_hw,
                pulse_scale=pulse_scale,
                contrast_ratio=1.0,
                contrast_compression=1.0,
                very_dim_curve=False,
                post_restore_holdoff_remaining_s=0.0,
                post_restore_damp=1.0,
            )
            return pulse_scale
        baseline_scale = float(visual_hw) / 50.0
        contrast_ratio = float(visual_hw) / float(eff)
        contrast_compression = 1.0
        very_dim_curve = visual_hw < 10
        final_scale = pulse_scale
        post_restore_damp = 1.0
        post_restore_holdoff_remaining_s = 0.0
        if very_dim_curve and pulse_scale > baseline_scale:
            post_restore_damp, post_restore_holdoff_remaining_s = _post_restore_visual_damp(engine)
            final_scale = baseline_scale + ((pulse_scale - baseline_scale) * post_restore_damp)
        _support.log_pulse_visual_scale_change(
            engine,
            logger=logger,
            base=base,
            eff=eff,
            hw=hw,
            target_hw=target_hw,
            visual_hw=visual_hw,
            pulse_scale=final_scale,
            contrast_ratio=contrast_ratio,
            contrast_compression=contrast_compression,
            very_dim_curve=very_dim_curve,
            post_restore_holdoff_remaining_s=post_restore_holdoff_remaining_s,
            post_restore_damp=post_restore_damp,
        )
        return final_scale

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


def _steady_target_hw_brightness(engine: "EffectsEngine", *, base: int) -> int:
    raw_global_hw = _engine_attr_or_default(engine, "brightness", default=25)
    try:
        global_hw = int(raw_global_hw or 0)  # type: ignore[call-overload]
    except _INT_COERCION_ERRORS:
        global_hw = 25
    global_hw = max(0, min(50, global_hw))
    return max(int(base), global_hw)


def frame_dt_s() -> float:
    return 1.0 / 60.0


def pace(engine: "EffectsEngine", *, min_factor: float = 0.8, max_factor: float = 2.2) -> float:
    """Map UI speed (0..10) to an effect pace multiplier.

    Matches the quadratic mapping used by the SW loops: speed=10 is much faster.
    """

    speed_raw = _engine_attr_or_default(engine, "speed", default=4)
    try:
        s = int(speed_raw or 0)  # type: ignore[call-overload]
    except _INT_COERCION_ERRORS:
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
    return bool(_keyboard_attr_or_none(engine, "set_key_colors"))


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
        resolve_transition_visual_scale=_resolve_transition_visual_scale,
        logger=logger,
    ):
        return

    render_uniform_frame(
        engine,
        color_map=color_map,
        resolve_brightness=_resolve_brightness,
    )
