from __future__ import annotations

import logging
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