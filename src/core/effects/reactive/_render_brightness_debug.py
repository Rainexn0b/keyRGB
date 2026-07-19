from __future__ import annotations

import logging

from ._render_brightness_support import (
    coerce_float,
    debug_brightness_enabled,
    read_engine_attr,
    set_engine_attr,
)


def log_hw_lift_decision_change(
    engine: object,
    *,
    logger: logging.Logger,
    reason: str,
    per_key_hw: bool,
    uniform_hw_streak_count: int,
    pulse_mix: float,
    cooldown_active: bool,
    cooldown_remaining_s: float,
    allow_pulse_hw_lift: bool,
    global_hw: int,
    base: int,
    eff: int,
    idle_hw: int,
    hw: int,
    dim_temp_active: bool,
) -> None:
    if not debug_brightness_enabled():
        return

    state = (
        str(reason),
        bool(per_key_hw),
        int(uniform_hw_streak_count),
        round(float(pulse_mix), 3),
        bool(cooldown_active),
        round(max(0.0, float(cooldown_remaining_s)), 1),
        bool(allow_pulse_hw_lift),
        int(global_hw),
        int(base),
        int(eff),
        int(idle_hw),
        int(hw),
        bool(dim_temp_active),
    )
    previous = read_engine_attr(
        engine,
        "_reactive_debug_hw_lift_state",
        missing_default=None,
        error_default=None,
        logger=logger,
    )
    if previous == state:
        return

    set_engine_attr(engine, "_reactive_debug_hw_lift_state", state, logger=logger)
    logger.info(
        "reactive_hw_lift: reason=%s per_key=%s streak=%s pulse_mix=%.3f cooldown=%s cooldown_remaining_s=%.2f allow=%s global=%s base=%s eff=%s idle=%s hw=%s dim=%s",
        reason,
        bool(per_key_hw),
        int(uniform_hw_streak_count),
        float(pulse_mix),
        bool(cooldown_active),
        max(0.0, float(cooldown_remaining_s)),
        bool(allow_pulse_hw_lift),
        int(global_hw),
        int(base),
        int(eff),
        int(idle_hw),
        int(hw),
        bool(dim_temp_active),
    )


def log_pulse_visual_scale_change(
    engine: object,
    *,
    logger: logging.Logger,
    base: int,
    eff: int,
    hw: int,
    target_hw: int,
    visual_hw: int,
    pulse_scale: float,
    contrast_ratio: float,
    contrast_compression: float,
    very_dim_curve: bool,
    post_restore_holdoff_remaining_s: float,
    post_restore_damp: float,
) -> None:
    if not debug_brightness_enabled():
        return

    state = (
        int(base),
        int(eff),
        int(hw),
        int(target_hw),
        int(visual_hw),
        round(float(pulse_scale), 3),
        round(float(contrast_ratio), 3),
        round(float(contrast_compression), 3),
        bool(very_dim_curve),
        round(max(0.0, float(post_restore_holdoff_remaining_s)), 2),
        round(float(post_restore_damp), 3),
    )
    previous = read_engine_attr(
        engine,
        "_reactive_debug_pulse_visual_state",
        missing_default=None,
        error_default=None,
        logger=logger,
    )
    if previous == state:
        return

    set_engine_attr(engine, "_reactive_debug_pulse_visual_state", state, logger=logger)
    set_engine_attr(engine, "_reactive_debug_last_pulse_scale", float(pulse_scale), logger=logger)
    logger.info(
        "reactive_pulse_visual: base=%s eff=%s hw=%s target_hw=%s visual_hw=%s pulse_scale=%.3f contrast_ratio=%.3f contrast_compression=%.3f very_dim_curve=%s holdoff_remaining_s=%.2f post_restore_damp=%.3f",
        int(base),
        int(eff),
        int(hw),
        int(target_hw),
        int(visual_hw),
        float(pulse_scale),
        float(contrast_ratio),
        float(contrast_compression),
        bool(very_dim_curve),
        max(0.0, float(post_restore_holdoff_remaining_s)),
        float(post_restore_damp),
    )


def log_render_visual_scale_change(
    engine: object,
    *,
    logger: logging.Logger,
    brightness_hw: int,
    transition_visual_scale: float,
) -> None:
    if not debug_brightness_enabled():
        return

    raw_pulse_scale = read_engine_attr(
        engine,
        "_reactive_debug_last_pulse_scale",
        missing_default=1.0,
        error_default=1.0,
        logger=logger,
    )
    pulse_scale = coerce_float(raw_pulse_scale, default=1.0)
    if pulse_scale is None:
        pulse_scale = 1.0

    raw_pulse_mix = read_engine_attr(
        engine,
        "_reactive_active_pulse_mix",
        missing_default=0.0,
        error_default=0.0,
        logger=logger,
    )
    pulse_mix = coerce_float(raw_pulse_mix, default=0.0)
    if pulse_mix is None:
        pulse_mix = 0.0

    transition_scale = max(0.0, min(1.0, float(transition_visual_scale)))
    combined_scale = max(0.0, min(1.0, float(pulse_scale) * transition_scale))
    state = (
        int(brightness_hw),
        round(float(pulse_scale), 3),
        round(float(transition_scale), 3),
        round(float(combined_scale), 3),
        round(float(pulse_mix), 3),
    )
    previous = read_engine_attr(
        engine,
        "_reactive_debug_render_visual_state",
        missing_default=None,
        error_default=None,
        logger=logger,
    )
    if previous == state:
        return

    set_engine_attr(engine, "_reactive_debug_render_visual_state", state, logger=logger)
    logger.info(
        "reactive_render_visual: hw=%s pulse_scale=%.3f transition_scale=%.3f combined_scale=%.3f pulse_mix=%.3f",
        int(brightness_hw),
        float(pulse_scale),
        float(transition_scale),
        float(combined_scale),
        float(pulse_mix),
    )
