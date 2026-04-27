from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from . import _fade_loop
from . import _ripple_loop
from . import _render_brightness_support as _support
from ._effects_api import bind_reactive_effect_exports, reactive_fade_api_for, reactive_ripple_api_for

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


logger = logging.getLogger(__name__)
_PULSE_MIX_DECAY_STEP = 0.34
_PULSE_MIX_RISE_STEP = 0.45
_PULSE_MIX_INITIAL_RISE_STEP = 0.18
_FIRST_ACTIVITY_PULSE_LIFT_HOLDOFF_S = 0.30
_FIRST_ACTIVITY_POST_RESTORE_VISUAL_DAMP_S = 2.0

bind_reactive_effect_exports(globals())


def _reactive_active_pulse_mix_or_default(engine: "EffectsEngine", *, default: float) -> float:
    raw_value = _support.read_engine_attr(
        engine,
        "_reactive_active_pulse_mix",
        missing_default=default,
        error_default=default,
        logger=logger,
    )
    value = _support.coerce_float(raw_value, default=default)
    return default if value is None else value


def _set_reactive_active_pulse_mix(engine: "EffectsEngine", *, target: float) -> None:
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
        holdoff_until = float(time.monotonic()) + _FIRST_ACTIVITY_PULSE_LIFT_HOLDOFF_S
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
            visual_damp_until = float(time.monotonic()) + _FIRST_ACTIVITY_POST_RESTORE_VISUAL_DAMP_S
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
        next_mix = max(0.0, prev - _PULSE_MIX_DECAY_STEP)
    elif target_f > prev:
        # Prevent a single-frame jump (for example on first overlapping keypresses
        # after idle) from immediately reaching full pulse-lift strength.
        rise_step = _PULSE_MIX_INITIAL_RISE_STEP if prev <= 0.0 else _PULSE_MIX_RISE_STEP
        next_mix = min(target_f, prev + rise_step)
    else:
        next_mix = target_f

    _support.set_engine_attr(engine, "_reactive_active_pulse_mix", float(next_mix), logger=logger)
    try:
        setattr(engine, "_reactive_active_pulse_mix", float(next_mix))
    except (AttributeError, TypeError, ValueError):
        logger.exception("Failed to cache reactive pulse mix")


def _render_uniform_fallback(engine: "EffectsEngine", *, rgb: tuple[int, int, int]) -> None:
    api = reactive_fade_api_for(__name__)
    color_map = api.get_engine_color_map_buffer(engine, "_reactive_uniform_fallback_map")
    color_map.clear()
    color_map[(0, 0)] = rgb
    api.render(engine, color_map=color_map)


def run_reactive_fade(engine: "EffectsEngine") -> None:
    _fade_loop.run_reactive_fade_loop(engine, api=reactive_fade_api_for(__name__))


def run_reactive_ripple(engine: "EffectsEngine") -> None:
    _ripple_loop.run_reactive_ripple_loop(engine, api=reactive_ripple_api_for(__name__))
