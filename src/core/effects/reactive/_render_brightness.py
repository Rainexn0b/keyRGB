from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING, Callable, Optional

from ._render_brightness_guard import apply_brightness_step_guard
from . import _render_brightness_support as _support

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


_LOGGER = logging.getLogger(__name__)
_MISSING = object()
_UNIFORM_PULSE_HW_LIFT_STREAK_MIN = 6


def _can_lift_hw_brightness(
    *,
    per_key_hw: bool,
    uniform_hw_streak_count: int,
    pulse_mix: float,
    effective_brightness: int,
    current_hw_brightness: int,
    cooldown_active: bool,
) -> bool:
    """Return whether a uniform-only backend may temporarily raise hardware brightness.

    Per-key backends keep hardware brightness fixed and express reactive intensity
    through per-key color contrast instead. Uniform-only backends need a short
    stable-frame gate before lifting hardware brightness so the first keypress of
    a burst does not produce an immediate full-frame spike.
    """

    if per_key_hw:
        return False
    if uniform_hw_streak_count < _UNIFORM_PULSE_HW_LIFT_STREAK_MIN:
        return False
    return pulse_mix > 0.0 and effective_brightness > current_hw_brightness and not cooldown_active


def _resolve_hw_brightness_with_pulse_mix(
    engine: "EffectsEngine",
    *,
    global_hw: int,
    base: int,
    eff: int,
    dim_temp_active: bool,
    clamp01_fn: Callable[[float], float],
    logger: logging.Logger,
) -> tuple[int, int, bool, bool]:
    per_key_hw = bool(_support.device_attr_or_none(_support.keyboard_or_none(engine), "set_key_colors"))
    if per_key_hw:
        _support.set_uniform_hw_streak(engine, value=0, logger=_LOGGER)
        uniform_hw_streak_count = 0
    else:
        uniform_hw_streak_count = _support.uniform_hw_streak(engine, logger=_LOGGER) + 1
        _support.set_uniform_hw_streak(engine, value=uniform_hw_streak_count, logger=_LOGGER)

    allow_pulse_hw_lift = False
    pulse_mix = 0.0
    cooldown_active = False
    cooldown_remaining_s = 0.0
    reason = "idle"
    if dim_temp_active:
        hw = global_hw
        idle_hw = hw
        reason = "dim_temp_active"
    else:
        raw_pulse_mix = _support.read_engine_attr(
            engine,
            "_reactive_active_pulse_mix",
            missing_default=0.0,
            error_default=0.0,
            logger=logger,
        )
        pulse_mix = _support.coerce_float(raw_pulse_mix or 0.0, default=0.0) or 0.0
        if pulse_mix is None:
            pulse_mix = 0.0
        pulse_mix = clamp01_fn(pulse_mix)

        raw_until = _support.read_engine_attr(
            engine,
            "_reactive_disable_pulse_hw_lift_until",
            missing_default=None,
            error_default=None,
            logger=logger,
        )
        until_s = _support.coerce_float(raw_until, default=None)
        if until_s is not None:
            cooldown_remaining_s = max(0.0, float(until_s) - float(time.monotonic()))

        hw = max(global_hw, base)
        idle_hw = hw
        cooldown_active = _support.pulse_hw_lift_temporarily_disabled(engine, logger=_LOGGER)
        allow_pulse_hw_lift = _can_lift_hw_brightness(
            per_key_hw=per_key_hw,
            uniform_hw_streak_count=uniform_hw_streak_count,
            pulse_mix=pulse_mix,
            effective_brightness=eff,
            current_hw_brightness=hw,
            cooldown_active=cooldown_active,
        )
        if allow_pulse_hw_lift:
            pulse_hw = int(round(float(hw) + (float(eff - hw) * pulse_mix)))
            hw = max(hw, pulse_hw)

        if per_key_hw:
            reason = "per_key_hw"
        elif pulse_mix <= 0.0:
            reason = "no_pulse"
        elif uniform_hw_streak_count < _UNIFORM_PULSE_HW_LIFT_STREAK_MIN:
            reason = "streak_gate"
        elif eff <= hw:
            reason = "eff_not_above_hw"
        elif cooldown_active:
            reason = "cooldown"
        elif allow_pulse_hw_lift:
            reason = "allowed"

    _support.log_hw_lift_decision_change(
        engine,
        logger=logger,
        reason=reason,
        per_key_hw=per_key_hw,
        uniform_hw_streak_count=uniform_hw_streak_count,
        pulse_mix=float(pulse_mix),
        cooldown_active=cooldown_active,
        cooldown_remaining_s=float(cooldown_remaining_s),
        allow_pulse_hw_lift=allow_pulse_hw_lift,
        global_hw=global_hw,
        base=base,
        eff=eff,
        idle_hw=idle_hw,
        hw=hw,
        dim_temp_active=dim_temp_active,
    )
    return hw, idle_hw, allow_pulse_hw_lift, per_key_hw


def resolve_reactive_transition_brightness(
    engine: "EffectsEngine",
    *,
    clamp01_fn: Callable[[float], float],
) -> Optional[tuple[int, bool]]:
    """Return the current transition brightness for reactive temp-dim flows."""

    transition = _resolve_reactive_transition_progress(engine, clamp01_fn=clamp01_fn)
    if transition is None:
        return None

    current_f, rising = transition
    if rising:
        return int(math.ceil(current_f)), True

    return int(round(current_f)), False


def resolve_reactive_transition_visual_scale(
    engine: "EffectsEngine",
    *,
    clamp01_fn: Callable[[float], float],
) -> float:
    """Return a fractional scale for rising per-key transitions.

    During low-brightness restore ramps the hardware brightness must stay
    integer-valued, which can make `1 -> 5` restores visibly step.  We smooth
    the written per-key frame by scaling it against the ceiled transition level
    so the overall visible intensity can still move fractionally between those
    hardware steps.
    """

    transition = _resolve_reactive_transition_progress(engine, clamp01_fn=clamp01_fn)
    if transition is None:
        return 1.0

    current_f, rising = transition
    if not rising:
        return 1.0

    quantized = int(math.ceil(current_f))
    if quantized <= 0:
        return 0.0

    return clamp01_fn(float(current_f) / float(quantized))


def _resolve_reactive_transition_progress(
    engine: "EffectsEngine",
    *,
    clamp01_fn: Callable[[float], float],
) -> Optional[tuple[float, bool]]:
    """Return the in-flight reactive transition brightness as a float."""

    start = _support.read_engine_attr(
        engine,
        "_reactive_transition_from_brightness",
        missing_default=None,
        error_default=None,
    )
    end = _support.read_engine_attr(
        engine,
        "_reactive_transition_to_brightness",
        missing_default=None,
        error_default=None,
    )
    started_at = _support.read_engine_attr(
        engine,
        "_reactive_transition_started_at",
        missing_default=None,
        error_default=None,
    )
    duration_s = _support.read_engine_attr(
        engine,
        "_reactive_transition_duration_s",
        missing_default=None,
        error_default=None,
    )

    if start is None or end is None or started_at is None or duration_s is None:
        return None

    start_i = _support.coerce_brightness(start, default=None)
    end_i = _support.coerce_brightness(end, default=None)
    duration = _support.coerce_float(duration_s, default=None)
    started = _support.coerce_float(started_at, default=None)
    if start_i is None or end_i is None or duration is None or started is None:
        return None

    duration = max(0.0, duration)
    rising = bool(end_i >= start_i)

    if duration <= 0.0 or start_i == end_i:
        _support.clear_transition_state(engine, logger=_LOGGER)
        return float(end_i), rising

    elapsed = max(0.0, float(time.monotonic()) - started)
    if elapsed >= duration:
        _support.clear_transition_state(engine, logger=_LOGGER)
        return float(end_i), rising

    t = clamp01_fn(elapsed / duration)
    current = float(start_i) + (float(end_i - start_i) * t)
    return current, rising


def resolve_brightness(
    engine: "EffectsEngine",
    *,
    max_step_per_frame: int,
    clamp01_fn: Callable[[float], float],
    logger: logging.Logger,
) -> tuple[int, int, int]:
    """Resolve (base_hw, effect_hw, hw_brightness) for mixed-content rendering."""

    raw_eff = _support.read_engine_attr(
        engine,
        "reactive_brightness",
        missing_default=_MISSING,
        error_default=25,
        logger=logger,
    )
    if raw_eff is _MISSING:
        raw_eff = _support.read_engine_attr(
            engine,
            "brightness",
            missing_default=25,
            error_default=25,
            logger=logger,
        )
    eff = _support.coerce_brightness(raw_eff or 0, default=25)
    if eff is None:
        eff = 25

    raw_global_hw = _support.read_engine_attr(
        engine,
        "brightness",
        missing_default=25,
        error_default=25,
        logger=logger,
    )
    global_hw = _support.coerce_brightness(raw_global_hw or 0, default=25)
    if global_hw is None:
        global_hw = 25

    base = 0
    if _support.read_engine_attr(
        engine,
        "per_key_colors",
        missing_default=None,
        error_default=None,
        logger=logger,
    ):
        raw_base = _support.read_engine_attr(
            engine,
            "per_key_brightness",
            missing_default=0,
            error_default=0,
            logger=logger,
        )
        base = _support.coerce_brightness(raw_base or 0, default=0) or 0

    transition = resolve_reactive_transition_brightness(engine, clamp01_fn=clamp01_fn)
    if transition is not None:
        transition_brightness, rising = transition
        eff = min(eff, transition_brightness)
        if rising:
            global_hw = min(global_hw, transition_brightness)
            base = min(base, transition_brightness)
        else:
            global_hw = max(global_hw, transition_brightness)
            base = max(base, transition_brightness)

    if _support.bool_attr_or_default(engine, "_reactive_follow_global_brightness", default=False):
        eff = min(eff, global_hw)
        base = min(base, global_hw)

    dim_temp_active = _support.bool_attr_or_default(engine, "_dim_temp_active", default=False)
    hw, idle_hw, allow_pulse_hw_lift, per_key_hw = _resolve_hw_brightness_with_pulse_mix(
        engine,
        global_hw=global_hw,
        base=base,
        eff=eff,
        dim_temp_active=dim_temp_active,
        clamp01_fn=clamp01_fn,
        logger=logger,
    )

    policy_cap: int | None = None
    raw_cap = _support.read_engine_attr(
        engine,
        "_hw_brightness_cap",
        missing_default=None,
        error_default=None,
        logger=logger,
    )
    if raw_cap is not None:
        policy_cap = _support.coerce_brightness(raw_cap, default=None)

    if policy_cap is not None:
        hw = min(hw, policy_cap)

    hw = max(0, min(50, hw))

    prev = _support.read_engine_attr(
        engine,
        "_last_rendered_brightness",
        missing_default=None,
        error_default=None,
        logger=logger,
    )
    prev_i = 0 if prev is None else _support.coerce_int(prev, default=None)
    hw = apply_brightness_step_guard(
        hw=hw,
        prev_i=prev_i,
        max_step_per_frame=max_step_per_frame,
        dim_temp_active=dim_temp_active,
        allow_pulse_hw_lift=allow_pulse_hw_lift,
        per_key_hw=per_key_hw,
        idle_hw=idle_hw,
        eff=eff,
        policy_cap=policy_cap,
        logger=logger,
    )

    return base, eff, hw


def _clear_transition_state(engine: "EffectsEngine") -> None:
    _support.clear_transition_state(engine, logger=_LOGGER)
