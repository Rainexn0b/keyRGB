from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from . import _fade_loop
from . import _ripple_loop
from ._effects_api import bind_reactive_effect_exports, reactive_fade_api_for, reactive_ripple_api_for

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


logger = logging.getLogger(__name__)

bind_reactive_effect_exports(globals())


def _reactive_active_pulse_mix_or_default(engine: "EffectsEngine", *, default: float) -> float:
    try:
        return float(engine._reactive_active_pulse_mix or 0.0)
    except AttributeError:
        return default


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
    if target_f <= 0.0 and prev > 0.0:
        next_mix = max(0.0, prev - 0.34)
    else:
        next_mix = target_f

    try:
        engine._reactive_active_pulse_mix = float(next_mix)
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
