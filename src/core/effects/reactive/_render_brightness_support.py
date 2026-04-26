from __future__ import annotations

import logging
import os
import time
from operator import attrgetter
from typing import TYPE_CHECKING, Callable, Protocol, cast

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


_LOGGER = logging.getLogger(__name__)
_INT_COERCION_ERRORS = (TypeError, ValueError, OverflowError)
_ENGINE_ATTR_RUNTIME_ERRORS = (LookupError, OSError, RuntimeError, TypeError, ValueError)


class _UniformHwStreakEngine(Protocol):
    _reactive_uniform_hw_streak: int


def run_engine_attr_operation(
    operation: Callable[[], object],
    *,
    handled_errors: tuple[type[BaseException], ...],
    handled_result: object,
    runtime_result: object,
    message: str,
    name: str,
    logger: logging.Logger | None = None,
) -> object:
    active_logger = logger or _LOGGER
    try:
        return operation()
    except handled_errors:
        return handled_result
    except _ENGINE_ATTR_RUNTIME_ERRORS:  # @quality-exception exception-transparency: engine attribute getters/setters may have recoverable runtime side effects during reactive brightness resolution and cleanup
        active_logger.exception(message, name)
        return runtime_result


def read_engine_attr(
    engine: "EffectsEngine",
    name: str,
    *,
    missing_default: object,
    error_default: object,
    logger: logging.Logger | None = None,
) -> object:
    return run_engine_attr_operation(
        lambda: attrgetter(name)(engine),
        handled_errors=(AttributeError,),
        handled_result=missing_default,
        runtime_result=error_default,
        message="Reactive brightness failed to read engine attribute %s",
        name=name,
        logger=logger,
    )


def bool_attr_or_default(engine: "EffectsEngine", name: str, *, default: bool) -> bool:
    try:
        return bool(attrgetter(name)(engine))
    except AttributeError:
        return default


def keyboard_or_none(engine: "EffectsEngine") -> object | None:
    try:
        return engine.kb
    except AttributeError:
        return None


def device_attr_or_none(device: object | None, name: str) -> object | None:
    if device is None:
        return None
    try:
        return attrgetter(name)(device)
    except AttributeError:
        return None


def coerce_int(value: object, *, default: int | None) -> int | None:
    try:
        return int(value)  # type: ignore[call-overload]
    except _INT_COERCION_ERRORS:
        return default


def coerce_float(value: object, *, default: float | None) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except _INT_COERCION_ERRORS:
        return default


def coerce_brightness(value: object, *, default: int | None) -> int | None:
    coerced = coerce_int(value, default=default)
    if coerced is None:
        return None
    return max(0, min(50, coerced))


def debug_brightness_enabled() -> bool:
    return os.environ.get("KEYRGB_DEBUG_BRIGHTNESS") == "1"


def pulse_hw_lift_temporarily_disabled(engine: "EffectsEngine", *, logger: logging.Logger) -> bool:
    raw_until = read_engine_attr(
        engine,
        "_reactive_disable_pulse_hw_lift_until",
        missing_default=None,
        error_default=None,
        logger=logger,
    )
    if raw_until is None:
        return False
    until_s = coerce_float(raw_until, default=None)
    if until_s is None:
        return False
    return float(time.monotonic()) < float(until_s)


def set_uniform_hw_streak(engine: "EffectsEngine", *, value: int, logger: logging.Logger) -> None:
    def set_streak() -> None:
        cast(_UniformHwStreakEngine, engine)._reactive_uniform_hw_streak = max(0, int(value))

    run_engine_attr_operation(
        set_streak,
        handled_errors=(AttributeError, TypeError, ValueError),
        handled_result=None,
        runtime_result=None,
        message="Reactive brightness failed to set engine attribute %s",
        name="_reactive_uniform_hw_streak",
        logger=logger,
    )


def uniform_hw_streak(engine: "EffectsEngine", *, logger: logging.Logger) -> int:
    raw = read_engine_attr(
        engine,
        "_reactive_uniform_hw_streak",
        missing_default=0,
        error_default=0,
        logger=logger,
    )
    value = coerce_int(raw, default=0) or 0
    return max(0, int(value))


def log_hw_lift_decision_change(
    engine: "EffectsEngine",
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

    def set_state() -> None:
        setattr(engine, "_reactive_debug_hw_lift_state", state)

    run_engine_attr_operation(
        set_state,
        handled_errors=(AttributeError, TypeError, ValueError),
        handled_result=None,
        runtime_result=None,
        message="Reactive brightness failed to set engine attribute %s",
        name="_reactive_debug_hw_lift_state",
        logger=logger,
    )
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


def clear_transition_state(engine: "EffectsEngine", *, logger: logging.Logger) -> None:
    for name in (
        "_reactive_transition_from_brightness",
        "_reactive_transition_to_brightness",
        "_reactive_transition_started_at",
        "_reactive_transition_duration_s",
    ):

        def clear_attr() -> None:
            setattr(engine, name, None)

        run_engine_attr_operation(
            clear_attr,
            handled_errors=(AttributeError, TypeError),
            handled_result=None,
            runtime_result=None,
            message="Reactive brightness failed to clear engine attribute %s",
            name=name,
            logger=logger,
        )