from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


_LOGGER = logging.getLogger(__name__)
_MISSING = object()
_INT_COERCION_ERRORS = (TypeError, ValueError, OverflowError)


def _read_engine_attr(
    engine: "EffectsEngine",
    name: str,
    *,
    missing_default: object,
    error_default: object,
    logger: logging.Logger | None = None,
) -> object:
    active_logger = logger or _LOGGER
    try:
        return getattr(engine, name)
    except AttributeError:
        return missing_default
    except Exception:  # @quality-exception exception-transparency: engine attribute getters may have arbitrary runtime side effects beyond AttributeError
        active_logger.exception("Reactive brightness failed to read engine attribute %s", name)
        return error_default


def _coerce_int(value: object, *, default: int | None) -> int | None:
    try:
        return int(value)  # type: ignore[call-overload]
    except _INT_COERCION_ERRORS:
        return default


def _coerce_float(value: object, *, default: float | None) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except _INT_COERCION_ERRORS:
        return default


def _coerce_brightness(value: object, *, default: int | None) -> int | None:
    coerced = _coerce_int(value, default=default)
    if coerced is None:
        return None
    return max(0, min(50, coerced))


def resolve_reactive_transition_brightness(
    engine: "EffectsEngine",
    *,
    clamp01_fn: Callable[[float], float],
) -> Optional[tuple[int, bool]]:
    """Return the current transition brightness for reactive temp-dim flows."""

    start = _read_engine_attr(
        engine,
        "_reactive_transition_from_brightness",
        missing_default=None,
        error_default=None,
    )
    end = _read_engine_attr(
        engine,
        "_reactive_transition_to_brightness",
        missing_default=None,
        error_default=None,
    )
    started_at = _read_engine_attr(
        engine,
        "_reactive_transition_started_at",
        missing_default=None,
        error_default=None,
    )
    duration_s = _read_engine_attr(
        engine,
        "_reactive_transition_duration_s",
        missing_default=None,
        error_default=None,
    )

    if start is None or end is None or started_at is None or duration_s is None:
        return None

    start_i = _coerce_brightness(start, default=None)
    end_i = _coerce_brightness(end, default=None)
    duration = _coerce_float(duration_s, default=None)
    started = _coerce_float(started_at, default=None)
    if start_i is None or end_i is None or duration is None or started is None:
        return None

    duration = max(0.0, duration)

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

    raw_eff = _read_engine_attr(
        engine,
        "reactive_brightness",
        missing_default=_MISSING,
        error_default=25,
        logger=logger,
    )
    if raw_eff is _MISSING:
        raw_eff = _read_engine_attr(
            engine,
            "brightness",
            missing_default=25,
            error_default=25,
            logger=logger,
        )
    eff = _coerce_brightness(raw_eff or 0, default=25)
    if eff is None:
        eff = 25

    raw_global_hw = _read_engine_attr(
        engine,
        "brightness",
        missing_default=25,
        error_default=25,
        logger=logger,
    )
    global_hw = _coerce_brightness(raw_global_hw or 0, default=25)
    if global_hw is None:
        global_hw = 25

    base = 0
    if _read_engine_attr(
        engine,
        "per_key_colors",
        missing_default=None,
        error_default=None,
        logger=logger,
    ):
        raw_base = _read_engine_attr(
            engine,
            "per_key_brightness",
            missing_default=0,
            error_default=0,
            logger=logger,
        )
        base = _coerce_brightness(raw_base or 0, default=0) or 0

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
        raw_pulse_mix = _read_engine_attr(
            engine,
            "_reactive_active_pulse_mix",
            missing_default=0.0,
            error_default=0.0,
            logger=logger,
        )
        pulse_mix = _coerce_float(raw_pulse_mix or 0.0, default=0.0) or 0.0
        if pulse_mix is None:
            pulse_mix = 0.0
        pulse_mix = clamp01_fn(pulse_mix)

        hw = max(global_hw, base)
        idle_hw = hw
        allow_pulse_hw_lift = (not per_key_hw) and pulse_mix > 0.0 and eff > hw
        if allow_pulse_hw_lift:
            pulse_hw = int(round(float(hw) + (float(eff - hw) * pulse_mix)))
            hw = max(hw, pulse_hw)

    policy_cap: int | None = None
    raw_cap = _read_engine_attr(
        engine,
        "_hw_brightness_cap",
        missing_default=None,
        error_default=None,
        logger=logger,
    )
    if raw_cap is not None:
        policy_cap = _coerce_brightness(raw_cap, default=None)

    if policy_cap is not None:
        hw = min(hw, policy_cap)

    hw = max(0, min(50, hw))

    prev = _read_engine_attr(
        engine,
        "_last_rendered_brightness",
        missing_default=None,
        error_default=None,
        logger=logger,
    )
    prev_i = 0 if prev is None else _coerce_int(prev, default=None)
    if prev_i is not None:
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

    return base, eff, hw


def _clear_transition_state(engine: "EffectsEngine") -> None:
    for name in (
        "_reactive_transition_from_brightness",
        "_reactive_transition_to_brightness",
        "_reactive_transition_started_at",
        "_reactive_transition_duration_s",
    ):
        try:
            setattr(engine, name, None)
        except (AttributeError, TypeError):
            continue
        except Exception:  # @quality-exception exception-transparency: engine attribute setters may fail unexpectedly beyond AttributeError/TypeError during reactive brightness cleanup
            _LOGGER.exception("Reactive brightness failed to clear engine attribute %s", name)
