from __future__ import annotations

import logging
import random  # noqa: F401  -- accessed as api.random by _fade_loop
import sys
from typing import TYPE_CHECKING

from src.core.effects import colors, matrix_layout
from src.core.effects.reactive import utils as reactive_utils

from . import _base_maps as base_maps
from . import _engine_color_state as engine_color_state
from . import _fade_loop
from . import _ripple_helpers as ripple_helpers
from . import _ripple_loop
from . import _runtime_inputs as runtime_inputs
from . import input as reactive_input
from . import render as render_runtime

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


logger = logging.getLogger(__name__)

NUM_COLS = matrix_layout.NUM_COLS
NUM_ROWS = matrix_layout.NUM_ROWS

_Pulse = reactive_utils._Pulse
_RainbowPulse = reactive_utils._RainbowPulse
_PressSource = reactive_utils._PressSource
_age_pulses_in_place = reactive_utils._age_pulses_in_place
_brightness_boost_pulse = reactive_utils._brightness_boost_pulse
_pick_contrasting_highlight = reactive_utils._pick_contrasting_highlight
_ripple_radius = reactive_utils._ripple_radius
_ripple_weight = reactive_utils._ripple_weight

hsv_to_rgb = colors.hsv_to_rgb

get_engine_manual_reactive_color = engine_color_state.get_engine_manual_reactive_color
get_engine_reactive_color = engine_color_state.get_engine_reactive_color

build_frame_base_maps = base_maps.build_frame_base_maps
get_engine_color_map_buffer = base_maps.get_engine_color_map_buffer

build_fade_overlay_into = ripple_helpers.build_fade_overlay_into
build_ripple_color_map_into = ripple_helpers.build_ripple_color_map_into
build_ripple_overlay_into = ripple_helpers.build_ripple_overlay_into
get_engine_overlay_buffer = ripple_helpers.get_engine_overlay_buffer

create_press_source = runtime_inputs.create_press_source
load_slot_keymap = runtime_inputs.load_slot_keymap
mapped_slot_cells = runtime_inputs.mapped_slot_cells

load_active_profile_slot_keymap = reactive_input.load_active_profile_slot_keymap
reactive_synthetic_fallback_enabled = reactive_input.reactive_synthetic_fallback_enabled
try_open_evdev_keyboards = reactive_input.try_open_evdev_keyboards

Color = render_runtime.Color
backdrop_brightness_scale_factor = render_runtime.backdrop_brightness_scale_factor
frame_dt_s = render_runtime.frame_dt_s
mix = render_runtime.mix
pace = render_runtime.pace
pulse_brightness_scale_factor = render_runtime.pulse_brightness_scale_factor
render = render_runtime.render
scale = render_runtime.scale


def _set_reactive_active_pulse_mix(engine: "EffectsEngine", *, target: float) -> None:
    """Update the live reactive pulse mix with a short tail decay.

    Ripple/fade overlays can disappear abruptly when the last pulse ages out,
    which would drop the entire keyboard from lifted hardware brightness back to
    idle in one frame.  Preserve a tiny decay tail so the end of the effect is
    less perceptible keyboard-wide.
    """

    try:
        prev = float(getattr(engine, "_reactive_active_pulse_mix", 0.0) or 0.0)
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


def _render_uniform_fallback(engine: "EffectsEngine", *, rgb: Color) -> None:
    color_map = get_engine_color_map_buffer(engine, "_reactive_uniform_fallback_map")
    color_map.clear()
    color_map[(0, 0)] = rgb
    render(engine, color_map=color_map)


def _reactive_api() -> object:
    return sys.modules[__name__]


def run_reactive_fade(engine: "EffectsEngine") -> None:
    _fade_loop.run_reactive_fade_loop(engine, api=_reactive_api())


def run_reactive_ripple(engine: "EffectsEngine") -> None:
    _ripple_loop.run_reactive_ripple_loop(engine, api=_reactive_api())
