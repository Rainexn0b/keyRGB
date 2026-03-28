from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


def resolve_reactive_transition_brightness(
    engine: "EffectsEngine",
    *,
    clamp01_fn: Callable[[float], float],
) -> Optional[tuple[int, bool]]:
    """Return the current transition brightness for reactive temp-dim flows."""

    try:
        start = getattr(engine, "_reactive_transition_from_brightness", None)
        end = getattr(engine, "_reactive_transition_to_brightness", None)
        started_at = getattr(engine, "_reactive_transition_started_at", None)
        duration_s = getattr(engine, "_reactive_transition_duration_s", None)
    except Exception:
        return None

    if start is None or end is None or started_at is None or duration_s is None:
        return None

    try:
        start_i = max(0, min(50, int(start)))
        end_i = max(0, min(50, int(end)))
        duration = max(0.0, float(duration_s))
        started = float(started_at)
    except Exception:
        return None

    if duration <= 0.0 or start_i == end_i:
        _clear_transition_state(engine)
        return end_i, bool(end_i >= start_i)

    elapsed = max(0.0, float(time.monotonic()) - started)
    if elapsed >= duration:
        _clear_transition_state(engine)
        return end_i, bool(end_i >= start_i)

    t = clamp01_fn(elapsed / duration)
    current = int(round(start_i + (end_i - start_i) * t))
    return current, bool(end_i >= start_i)


def resolve_brightness(
    engine: "EffectsEngine",
    *,
    max_step_per_frame: int,
    clamp01_fn: Callable[[float], float],
    logger: logging.Logger,
) -> tuple[int, int, int]:
    """Resolve (base_hw, effect_hw, hw_brightness) for mixed-content rendering."""

    try:
        eff = int(getattr(engine, "reactive_brightness", getattr(engine, "brightness", 25)) or 0)
    except Exception:
        eff = 25
    eff = max(0, min(50, eff))

    try:
        global_hw = int(getattr(engine, "brightness", 25) or 0)
    except Exception:
        global_hw = 25
    global_hw = max(0, min(50, global_hw))

    base = 0
    try:
        if getattr(engine, "per_key_colors", None):
            base = int(getattr(engine, "per_key_brightness", 0) or 0)
    except Exception:
        pass
    base = max(0, min(50, base))

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

    dim_temp_active = bool(getattr(engine, "_dim_temp_active", False))
    per_key_hw = bool(getattr(getattr(engine, "kb", None), "set_key_colors", None))

    pulse_mix = 0.0
    allow_pulse_hw_lift = False
    if dim_temp_active:
        hw = global_hw
        idle_hw = hw
    else:
        try:
            pulse_mix = float(getattr(engine, "_reactive_active_pulse_mix", 0.0) or 0.0)
        except Exception:
            pulse_mix = 0.0
        pulse_mix = clamp01_fn(pulse_mix)

        hw = max(global_hw, base)
        idle_hw = hw
        allow_pulse_hw_lift = (not per_key_hw) and pulse_mix > 0.0 and eff > hw
        if allow_pulse_hw_lift:
            pulse_hw = int(round(float(hw) + (float(eff - hw) * pulse_mix)))
            hw = max(hw, pulse_hw)

    policy_cap: int | None = None
    try:
        raw_cap = getattr(engine, "_hw_brightness_cap", None)
        if raw_cap is not None:
            policy_cap = max(0, min(50, int(raw_cap)))
    except Exception:
        pass

    if policy_cap is not None:
        hw = min(hw, policy_cap)

    hw = max(0, min(50, hw))

    try:
        prev = getattr(engine, "_last_rendered_brightness", None)
        prev_i = int(prev) if prev is not None else 0
        delta = hw - prev_i
        guard_active = abs(delta) > max_step_per_frame
        if guard_active and dim_temp_active and delta < 0:
            guard_active = False
        if guard_active and allow_pulse_hw_lift and delta > 0:
            guard_active = False
        if guard_active and (not per_key_hw) and delta < 0 and prev_i > idle_hw and eff > idle_hw:
            guard_active = False
        if guard_active:
            hw = prev_i + (max_step_per_frame if delta > 0 else -max_step_per_frame)
            hw = max(0, min(50, hw))
            if os.environ.get("KEYRGB_DEBUG_BRIGHTNESS") == "1":
                logger.info(
                    "brightness_guard: clamped %s->%s (prev=%s, cap=%s, dim=%s)",
                    prev_i + delta,
                    hw,
                    prev_i,
                    policy_cap,
                    dim_temp_active,
                )
    except Exception:
        pass

    return base, eff, hw


def _clear_transition_state(engine: "EffectsEngine") -> None:
    try:
        engine._reactive_transition_from_brightness = None
        engine._reactive_transition_to_brightness = None
        engine._reactive_transition_started_at = None
        engine._reactive_transition_duration_s = None
    except Exception:
        pass