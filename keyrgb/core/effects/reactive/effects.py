from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, cast

from . import (
    _base_maps,
    _fade_loop,
    _render_brightness_support as _support,
    _ripple_loop,
    render as _render_runtime,
)
from ._constants import (
    FIRST_ACTIVITY_POST_RESTORE_VISUAL_DAMP_S,
    FIRST_ACTIVITY_PULSE_LIFT_HOLDOFF_S,
    PULSE_MIX_DECAY_STEP,
    PULSE_MIX_INITIAL_RISE_STEP,
    PULSE_MIX_RISE_STEP,
)
from ._effects_api import build_reactive_api
from .utils import _ripple_radius, _ripple_weight  # noqa: F401 – backward-compat re-exports

if TYPE_CHECKING:
    from keyrgb.core.effects.engine import EffectsEngine


logger = logging.getLogger(__name__)

# see _constants.py


def _reactive_active_pulse_mix_or_default(engine: EffectsEngine, *, default: float) -> float:
    raw_value = _support.read_engine_attr(
        engine,
        "_reactive_active_pulse_mix",
        missing_default=default,
        error_default=default,
        logger=logger,
    )
    value = _support.coerce_float(raw_value, default=default)
    return default if value is None else value


def _set_reactive_active_pulse_mix(engine: EffectsEngine, *, target: float) -> None:
    """Update the live reactive pulse mix with a short tail decay.

    Ripple/fade overlays can disappear abruptly when the last pulse ages out,
    which would drop the entire keyboard from lifted hardware brightness back to
    idle in one frame.  Preserve a tiny decay tail so the end of the effect is
    less perceptible keyboard-wide.
    """

    try:
        prev = _reactive_active_pulse_mix_or_default(engine, default=0.0)
    except (TypeError, ValueError):
        prev = 0.0

    target_f = max(0.0, min(1.0, float(target)))
    if prev <= 0.0 and target_f > 0.0:
        current_until_raw = _support.read_engine_attr(
            engine,
            "_reactive_disable_pulse_hw_lift_until",
            missing_default=0.0,
            error_default=0.0,
            logger=logger,
        )
        current_until = _support.coerce_float(current_until_raw, default=0.0) or 0.0
        holdoff_until = float(time.monotonic()) + FIRST_ACTIVITY_PULSE_LIFT_HOLDOFF_S
        _support.set_engine_attr(
            engine,
            "_reactive_disable_pulse_hw_lift_until",
            max(current_until, holdoff_until),
            logger=logger,
        )

        restore_phase = _support.restore_phase_or_default(
            engine,
            default=_support.ReactiveRestorePhase.NORMAL,
            logger=logger,
        )
        if restore_phase is _support.ReactiveRestorePhase.FIRST_PULSE_PENDING:
            visual_damp_until = float(time.monotonic()) + FIRST_ACTIVITY_POST_RESTORE_VISUAL_DAMP_S
            current_visual_until_raw = _support.read_engine_attr(
                engine,
                "_reactive_restore_damp_until",
                missing_default=0.0,
                error_default=0.0,
                logger=logger,
            )
            current_visual_until = _support.coerce_float(current_visual_until_raw, default=0.0) or 0.0
            _support.set_engine_attr(
                engine,
                "_reactive_restore_damp_until",
                max(current_visual_until, visual_damp_until),
                logger=logger,
            )
            _support.set_engine_attr(
                engine,
                "_reactive_restore_phase",
                _support.ReactiveRestorePhase.DAMPING,
                logger=logger,
            )

    if target_f <= 0.0 and prev > 0.0:
        next_mix = max(0.0, prev - PULSE_MIX_DECAY_STEP)
    elif target_f > prev:
        # Prevent a single-frame jump (for example on first overlapping keypresses
        # after idle) from immediately reaching full pulse-lift strength.
        rise_step = PULSE_MIX_INITIAL_RISE_STEP if prev <= 0.0 else PULSE_MIX_RISE_STEP
        next_mix = min(target_f, prev + rise_step)
    else:
        next_mix = target_f

    _support.set_engine_attr(engine, "_reactive_active_pulse_mix", float(next_mix), logger=logger)


def _render_uniform_fallback(engine: EffectsEngine, *, rgb: tuple[int, int, int]) -> None:
    color_map = _base_maps.get_engine_color_map_buffer(engine, "_reactive_uniform_fallback_map")
    color_map.clear()
    color_map[(0, 0)] = rgb
    _render_runtime.render(engine, color_map=color_map)


# ---------------------------------------------------------------------------
# Build immutable API facades (replaces globals().update + sys.modules cast)
# ---------------------------------------------------------------------------
_fade_api = build_reactive_api(
    set_reactive_active_pulse_mix=_set_reactive_active_pulse_mix,
    render_uniform_fallback=_render_uniform_fallback,
)
_ripple_api = build_reactive_api(
    set_reactive_active_pulse_mix=_set_reactive_active_pulse_mix,
    render_uniform_fallback=_render_uniform_fallback,
)


def run_reactive_fade(engine: EffectsEngine) -> None:
    _fade_loop.run_reactive_fade_loop(engine, api=cast(_fade_loop._ReactiveFadeApiProtocol, _fade_api))


def run_reactive_ripple(engine: EffectsEngine) -> None:
    _ripple_loop.run_reactive_ripple_loop(engine, api=cast(_ripple_loop._ReactiveRippleApiProtocol, _ripple_api))
