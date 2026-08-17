from __future__ import annotations

import random
from dataclasses import dataclass

from src.core.effects import colors, matrix_layout
from src.core.effects.reactive import utils as reactive_utils

from . import (
    _base_maps as base_maps,
    _engine_color_state as engine_color_state,
    _ripple_helpers as ripple_helpers,
    _runtime_inputs as runtime_inputs,
    input as reactive_input,
    render as render_runtime,
)


@dataclass(frozen=True, slots=True)
class ReactiveApiFacade:
    """Explicit immutable dependency object shared by reactive loops."""

    NUM_COLS: int
    NUM_ROWS: int
    _Pulse: object
    _RainbowPulse: object
    _PressSource: object
    _age_pulses_in_place: object
    _brightness_boost_pulse: object
    _pick_contrasting_highlight: object
    _ripple_radius: object
    _ripple_weight: object
    hsv_to_rgb: object
    get_engine_manual_reactive_color: object
    get_engine_reactive_color: object
    build_frame_base_maps: object
    get_engine_color_map_buffer: object
    build_fade_overlay_into: object
    build_ripple_color_map_into: object
    build_ripple_overlay_into: object
    get_engine_overlay_buffer: object
    create_press_source: object
    load_slot_keymap: object
    mapped_slot_cells: object
    load_active_profile_slot_keymap: object
    reactive_synthetic_fallback_enabled: object
    try_open_evdev_keyboards: object
    backdrop_brightness_scale_factor: object
    frame_dt_s: object
    mix: object
    pace: object
    pulse_brightness_scale_factor: object
    reactive_auto_pulse_saturation: object
    reactive_visual_mode: object
    random: object
    render: object
    scale: object
    _set_reactive_active_pulse_mix: object
    _render_uniform_fallback: object


def build_reactive_api(
    *,
    set_reactive_active_pulse_mix: object,
    render_uniform_fallback: object,
) -> ReactiveApiFacade:
    """Build the concrete dependency facade without module-global injection."""

    return ReactiveApiFacade(
        NUM_COLS=matrix_layout.NUM_COLS,
        NUM_ROWS=matrix_layout.NUM_ROWS,
        _Pulse=reactive_utils._Pulse,
        _RainbowPulse=reactive_utils._RainbowPulse,
        _PressSource=reactive_utils._PressSource,
        _age_pulses_in_place=reactive_utils._age_pulses_in_place,
        _brightness_boost_pulse=reactive_utils._brightness_boost_pulse,
        _pick_contrasting_highlight=reactive_utils._pick_contrasting_highlight,
        _ripple_radius=reactive_utils._ripple_radius,
        _ripple_weight=reactive_utils._ripple_weight,
        hsv_to_rgb=colors.hsv_to_rgb,
        get_engine_manual_reactive_color=engine_color_state.get_engine_manual_reactive_color,
        get_engine_reactive_color=engine_color_state.get_engine_reactive_color,
        build_frame_base_maps=base_maps.build_frame_base_maps,
        get_engine_color_map_buffer=base_maps.get_engine_color_map_buffer,
        build_fade_overlay_into=ripple_helpers.build_fade_overlay_into,
        build_ripple_color_map_into=ripple_helpers.build_ripple_color_map_into,
        build_ripple_overlay_into=ripple_helpers.build_ripple_overlay_into,
        get_engine_overlay_buffer=ripple_helpers.get_engine_overlay_buffer,
        create_press_source=runtime_inputs.create_press_source,
        load_slot_keymap=runtime_inputs.load_slot_keymap,
        mapped_slot_cells=runtime_inputs.mapped_slot_cells,
        load_active_profile_slot_keymap=reactive_input.load_active_profile_slot_keymap,
        reactive_synthetic_fallback_enabled=reactive_input.reactive_synthetic_fallback_enabled,
        try_open_evdev_keyboards=reactive_input.try_open_evdev_keyboards,
        backdrop_brightness_scale_factor=render_runtime.backdrop_brightness_scale_factor,
        frame_dt_s=render_runtime.frame_dt_s,
        mix=render_runtime.mix,
        pace=render_runtime.pace,
        pulse_brightness_scale_factor=render_runtime.pulse_brightness_scale_factor,
        reactive_auto_pulse_saturation=render_runtime.reactive_auto_pulse_saturation,
        reactive_visual_mode=render_runtime.reactive_visual_mode,
        random=random,
        render=render_runtime.render,
        scale=render_runtime.scale,
        _set_reactive_active_pulse_mix=set_reactive_active_pulse_mix,
        _render_uniform_fallback=render_uniform_fallback,
    )
