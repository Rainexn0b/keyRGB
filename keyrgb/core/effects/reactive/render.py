from __future__ import annotations

import logging
import time as _time
from operator import attrgetter
from typing import TYPE_CHECKING

from keyrgb.core.backends.base import supports_per_key_output
from keyrgb.core.effects.matrix_layout import geometry_for_engine
from keyrgb.core.effects.perkey_animation import build_full_color_grid

from ._constants import MAX_BRIGHTNESS_STEP_PER_FRAME
from ._render_brightness import (
    resolve_brightness as _resolve_brightness_impl,
    resolve_reactive_transition_brightness as _resolve_reactive_transition_brightness_impl,
    resolve_reactive_transition_visual_scale as _resolve_reactive_transition_visual_scale_impl,
)
from ._render_brightness_support import (  # noqa: F401 - preserved facade for external/test imports
    ReactiveRestorePhase as _ReactiveRestorePhase,
    restore_phase_or_default as _restore_phase_or_default,
)
from ._render_post_restore import (
    post_restore_frame_scale as _post_restore_frame_scale,
)
from ._render_runtime import render_per_key_frame, render_uniform_frame

logger = logging.getLogger(__name__)
# Monkeypatch seam: tests patch ``render.time.monotonic``; post-restore reads it via this module.
time = _time
_REACTIVE_VISUAL_MODES = frozenset({"subtle", "vivid"})

# see _constants.py

if TYPE_CHECKING:
    from keyrgb.core.effects.engine import EffectsEngine

Color = tuple[int, int, int]
Key = tuple[int, int]
_INT_COERCION_ERRORS = (TypeError, ValueError)


def _engine_attr_or_default(engine: EffectsEngine, attr_name: str, *, default: object) -> object:
    try:
        return attrgetter(attr_name)(engine)
    except AttributeError:
        return default


def clamp01(x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    return x


def reactive_visual_mode(engine: EffectsEngine, *, default: str = "vivid") -> str:
    raw = _engine_attr_or_default(engine, "reactive_visual_mode", default=default)
    try:
        normalized = str(raw or default).strip().lower()
    except _INT_COERCION_ERRORS:
        return default
    return normalized if normalized in _REACTIVE_VISUAL_MODES else default


def reactive_auto_pulse_saturation(engine: EffectsEngine) -> float:
    return 0.72 if reactive_visual_mode(engine, default="vivid") == "subtle" else 1.0


def _apply_reactive_pulse_visual_curve(scale: float, *, visual_mode: str) -> float:
    clamped = clamp01(scale)
    if visual_mode != "subtle":
        return clamped
    return clamp01(clamped**1.35)


def mix(a: Color, b: Color, t: float) -> Color:
    tt = clamp01(t)
    return (
        round(a[0] + (b[0] - a[0]) * tt),
        round(a[1] + (b[1] - a[1]) * tt),
        round(a[2] + (b[2] - a[2]) * tt),
    )


def scale(rgb: Color, s: float) -> Color:
    ss = clamp01(s)
    return (round(rgb[0] * ss), round(rgb[1] * ss), round(rgb[2] * ss))


def _resolve_reactive_transition_brightness(engine: EffectsEngine) -> tuple[int, bool] | None:
    return _resolve_reactive_transition_brightness_impl(engine, clamp01_fn=clamp01)


def _resolve_brightness(engine: EffectsEngine) -> tuple[int, int, int]:
    return _resolve_brightness_impl(
        engine,
        max_step_per_frame=MAX_BRIGHTNESS_STEP_PER_FRAME,
        clamp01_fn=clamp01,
        logger=logger,
    )


def _resolve_transition_visual_scale(engine: EffectsEngine) -> float:
    scale = _resolve_reactive_transition_visual_scale_impl(engine, clamp01_fn=clamp01)
    # Soft-on full-matrix steps after long idle black are backdrop-only
    # (pulse_mix=0). Pulse damp cannot soften them; fold a milder whole-frame
    # ease while the restore frame envelope is active. This envelope is
    # independent of the pulse restore phase and monotonic from FRAME_MIN to
    # 1.0 over the configured fade duration, so a FIRST_PULSE_PENDING→DAMPING
    # flip does not cause a discontinuity. Pulse damp may continue after the
    # frame envelope ends.
    return clamp01(float(scale) * _post_restore_frame_scale(engine))


def backdrop_brightness_scale_factor(engine: EffectsEngine, *, effect_brightness_hw: int) -> float:
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


def apply_backdrop_brightness_scale(color_map: dict[Key, Color], *, factor: float) -> dict[Key, Color]:
    """Return a scaled copy of a per-key base map."""

    f = float(factor)
    if f >= 0.999:
        return dict(color_map)
    if f <= 0.0:
        return {k: (0, 0, 0) for k in color_map}
    return {k: scale(rgb, f) for k, rgb in color_map.items()}


def frame_dt_s() -> float:
    return 1.0 / 60.0


def pace(engine: EffectsEngine, *, min_factor: float = 0.25, max_factor: float = 10.0) -> float:
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

    return float(min_factor + (max_factor - min_factor) * t)


def has_per_key(engine: EffectsEngine) -> bool:
    return supports_per_key_output(getattr(engine, "backend_caps", None), getattr(engine, "kb", None))


def base_color_map(engine: EffectsEngine) -> dict[Key, Color]:
    base_color_src = getattr(engine, "current_color", None) or (255, 0, 0)
    base_color = (
        int(base_color_src[0]),
        int(base_color_src[1]),
        int(base_color_src[2]),
    )
    geometry = geometry_for_engine(engine)

    per_key = getattr(engine, "per_key_colors", None) or None
    if not per_key:
        return {(r, c): base_color for r in range(geometry.rows) for c in range(geometry.cols)}

    full = build_full_color_grid(
        base_color=base_color,
        per_key_colors=per_key,
        num_rows=geometry.rows,
        num_cols=geometry.cols,
    )

    out: dict[Key, Color] = {}
    for (r, c), rgb in full.items():
        out[(r, c)] = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
    return out


def render(engine: EffectsEngine, *, color_map: dict[Key, Color]) -> None:
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


from ._render_pulse_scale import (  # noqa: F401 - preserved facade for external/test imports
    _post_fade_reactive_release_scale,
    pulse_brightness_scale_factor,
)
