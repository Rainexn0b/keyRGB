from __future__ import annotations

import logging
import time as _time
from operator import attrgetter
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from src.core.effects.matrix_layout import NUM_COLS, NUM_ROWS
from src.core.effects.perkey_animation import build_full_color_grid

from . import _render_brightness_support as _support
from ._constants import MAX_BRIGHTNESS_STEP_PER_FRAME
from ._render_brightness import (
    resolve_brightness as _resolve_brightness_impl,
    resolve_reactive_transition_brightness as _resolve_reactive_transition_brightness_impl,
    resolve_reactive_transition_visual_scale as _resolve_reactive_transition_visual_scale_impl,
)
from ._render_post_restore import (
    post_restore_frame_scale as _post_restore_frame_scale,
    post_restore_visual_damp as _post_restore_visual_damp,
)
from ._render_runtime import render_per_key_frame, render_uniform_frame

logger = logging.getLogger(__name__)
# Monkeypatch seam: tests patch ``render.time.monotonic``; post-restore reads it via this module.
time = _time
_REACTIVE_VISUAL_MODES = frozenset({"subtle", "vivid"})

# see _constants.py

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


def reactive_visual_mode(engine: "EffectsEngine", *, default: str = "vivid") -> str:
    raw = _engine_attr_or_default(engine, "reactive_visual_mode", default=default)
    try:
        normalized = str(raw or default).strip().lower()
    except _INT_COERCION_ERRORS:
        return default
    return normalized if normalized in _REACTIVE_VISUAL_MODES else default


def reactive_auto_pulse_saturation(engine: "EffectsEngine") -> float:
    return 0.72 if reactive_visual_mode(engine, default="vivid") == "subtle" else 1.0


def _apply_reactive_pulse_visual_curve(scale: float, *, visual_mode: str) -> float:
    clamped = clamp01(scale)
    if visual_mode != "subtle":
        return clamped
    return clamp01(clamped**1.35)


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
        max_step_per_frame=MAX_BRIGHTNESS_STEP_PER_FRAME,
        clamp01_fn=clamp01,
        logger=logger,
    )


def _resolve_transition_visual_scale(engine: "EffectsEngine") -> float:
    scale = _resolve_reactive_transition_visual_scale_impl(engine, clamp01_fn=clamp01)
    # Soft-on full-matrix steps after long idle black are backdrop-only
    # (pulse_mix=0). Pulse damp cannot soften them; fold a milder whole-frame
    # ease while the restore damp window is active.
    return clamp01(float(scale) * _post_restore_frame_scale(engine))


def backdrop_brightness_scale_factor(engine: "EffectsEngine", *, effect_brightness_hw: int) -> float:
    """Compute scaling factor to keep the backdrop at its target brightness.

    When uniform-only backends lift hardware brightness for a pulse, the
    backdrop must be scaled down proportionally so its perceived brightness
    stays at the user's configured base level. This avoids the backdrop
    becoming too bright during pulse-lift frames.

    Per-key backends never lift hardware brightness (invariant #2), so this
    factor is always 1.0 for per-key rendering and only relevant for uniform.

    The factor is: base_hw / hw_brightness, clamped to [0, 1].
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
    must stay scoped to explicit post-restore recovery windows (any steady
    brightness) so normal typing outside those windows keeps the configured
    reactive level.
    """

    base, eff, hw = _resolve_brightness(engine)
    visual_mode = reactive_visual_mode(engine, default="vivid")

    if has_per_key(engine):
        pulse_scale = _apply_reactive_pulse_visual_curve(
            float(max(0, min(50, int(eff)))) / 50.0,
            visual_mode=visual_mode,
        )
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

        # Post-restore damp must apply at any steady brightness (not only the
        # very-dim curve). Nesting damp under visual_hw < 10 left normal bases
        # (e.g. 20) undamped on typing-wake after long idle off — deck-wide flash.
        post_restore_damp, post_restore_holdoff_remaining_s = _post_restore_visual_damp(engine)
        very_dim_curve = visual_hw < 10

        if eff <= visual_hw:
            final_scale = float(pulse_scale) * float(post_restore_damp)
            _support.log_pulse_visual_scale_change(
                engine,
                logger=logger,
                base=base,
                eff=eff,
                hw=hw,
                target_hw=target_hw,
                visual_hw=visual_hw,
                pulse_scale=final_scale,
                contrast_ratio=1.0,
                contrast_compression=1.0,
                very_dim_curve=very_dim_curve,
                post_restore_holdoff_remaining_s=post_restore_holdoff_remaining_s,
                post_restore_damp=post_restore_damp,
            )
            return final_scale

        baseline_scale = float(visual_hw) / 50.0
        contrast_ratio = float(visual_hw) / float(eff)
        contrast_compression = 1.0
        # damp=1.0 outside restore windows => final_scale == pulse_scale.
        if pulse_scale > baseline_scale:
            final_scale = baseline_scale + ((pulse_scale - baseline_scale) * float(post_restore_damp))
        else:
            final_scale = float(pulse_scale) * float(post_restore_damp)
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

    return _apply_reactive_pulse_visual_curve(float(eff) / float(hw), visual_mode=visual_mode)


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


def pace(engine: "EffectsEngine", *, min_factor: float = 0.25, max_factor: float = 10.0) -> float:
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

    return float(float(min_factor) + (float(max_factor) - float(min_factor)) * t)


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
