from __future__ import annotations

import random
import sys
from collections.abc import MutableMapping
from typing import cast

from src.core.effects import colors, matrix_layout
from src.core.effects.reactive import utils as reactive_utils

from . import _base_maps as base_maps
from . import _engine_color_state as engine_color_state
from . import _ripple_helpers as ripple_helpers
from . import _runtime_inputs as runtime_inputs
from . import input as reactive_input
from . import render as render_runtime
from ._fade_loop import _ReactiveFadeApiProtocol
from ._ripple_loop import _ReactiveRippleApiProtocol

_REACTIVE_EFFECT_EXPORTS: dict[str, object] = {
    "NUM_COLS": matrix_layout.NUM_COLS,
    "NUM_ROWS": matrix_layout.NUM_ROWS,
    "_Pulse": reactive_utils._Pulse,
    "_RainbowPulse": reactive_utils._RainbowPulse,
    "_PressSource": reactive_utils._PressSource,
    "_age_pulses_in_place": reactive_utils._age_pulses_in_place,
    "_brightness_boost_pulse": reactive_utils._brightness_boost_pulse,
    "_pick_contrasting_highlight": reactive_utils._pick_contrasting_highlight,
    "_ripple_radius": reactive_utils._ripple_radius,
    "_ripple_weight": reactive_utils._ripple_weight,
    "hsv_to_rgb": colors.hsv_to_rgb,
    "get_engine_manual_reactive_color": engine_color_state.get_engine_manual_reactive_color,
    "get_engine_reactive_color": engine_color_state.get_engine_reactive_color,
    "build_frame_base_maps": base_maps.build_frame_base_maps,
    "get_engine_color_map_buffer": base_maps.get_engine_color_map_buffer,
    "build_fade_overlay_into": ripple_helpers.build_fade_overlay_into,
    "build_ripple_color_map_into": ripple_helpers.build_ripple_color_map_into,
    "build_ripple_overlay_into": ripple_helpers.build_ripple_overlay_into,
    "get_engine_overlay_buffer": ripple_helpers.get_engine_overlay_buffer,
    "create_press_source": runtime_inputs.create_press_source,
    "load_slot_keymap": runtime_inputs.load_slot_keymap,
    "mapped_slot_cells": runtime_inputs.mapped_slot_cells,
    "load_active_profile_slot_keymap": reactive_input.load_active_profile_slot_keymap,
    "reactive_synthetic_fallback_enabled": reactive_input.reactive_synthetic_fallback_enabled,
    "try_open_evdev_keyboards": reactive_input.try_open_evdev_keyboards,
    "Color": render_runtime.Color,
    "backdrop_brightness_scale_factor": render_runtime.backdrop_brightness_scale_factor,
    "frame_dt_s": render_runtime.frame_dt_s,
    "mix": render_runtime.mix,
    "pace": render_runtime.pace,
    "pulse_brightness_scale_factor": render_runtime.pulse_brightness_scale_factor,
    "random": random,
    "render": render_runtime.render,
    "scale": render_runtime.scale,
}


def bind_reactive_effect_exports(module_globals: MutableMapping[str, object]) -> None:
    module_globals.update(_REACTIVE_EFFECT_EXPORTS)


def reactive_fade_api_for(module_name: str) -> _ReactiveFadeApiProtocol:
    return cast(_ReactiveFadeApiProtocol, sys.modules[module_name])


def reactive_ripple_api_for(module_name: str) -> _ReactiveRippleApiProtocol:
    return cast(_ReactiveRippleApiProtocol, sys.modules[module_name])
