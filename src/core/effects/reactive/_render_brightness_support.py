from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
import os
import time
from operator import attrgetter
from typing import Callable

_LOGGER = logging.getLogger(__name__)
_INT_COERCION_ERRORS = (TypeError, ValueError, OverflowError)
_ENGINE_ATTR_RUNTIME_ERRORS = (LookupError, OSError, RuntimeError, TypeError, ValueError)


class ReactiveRestorePhase(str, Enum):
    NORMAL = "normal"
    FIRST_PULSE_PENDING = "first_pulse_pending"
    DAMPING = "damping"


@dataclass(slots=True)
class ReactiveRenderState:
    _compat_mirror_to_engine: bool = True
    _reactive_transition_from_brightness: int | None = None
    _reactive_transition_to_brightness: int | None = None
    _reactive_transition_started_at: float | None = None
    _reactive_transition_duration_s: float | None = None
    _reactive_disable_pulse_hw_lift_until: float | None = None
    _reactive_restore_phase: ReactiveRestorePhase = ReactiveRestorePhase.NORMAL
    _reactive_restore_damp_until: float | None = None
    _reactive_uniform_hw_streak: int = 0
    _reactive_follow_global_brightness: bool = False
    _reactive_active_pulse_mix: float = 0.0
    _reactive_debug_hw_lift_state: tuple[object, ...] | None = None
    _reactive_debug_pulse_visual_state: tuple[object, ...] | None = None
    _reactive_debug_last_pulse_scale: float = 1.0
    _reactive_debug_render_visual_state: tuple[object, ...] | None = None


_REACTIVE_STATE_ATTR_NAMES = frozenset(
    name for name in ReactiveRenderState.__annotations__ if name != "_compat_mirror_to_engine"
)


def _is_reactive_state_attr(name: str) -> bool:
    return name in _REACTIVE_STATE_ATTR_NAMES


def _copy_reactive_state_attrs(source: object, state: ReactiveRenderState) -> None:
    for name in _REACTIVE_STATE_ATTR_NAMES:
        try:
            value = attrgetter(name)(source)
        except AttributeError:
            continue
        try:
            setattr(state, name, value)
        except (AttributeError, TypeError, ValueError):
            continue

    try:
        legacy_until = attrgetter("_reactive_post_restore_visual_damp_until")(source)
    except AttributeError:
        legacy_until = None
    try:
        legacy_pending = bool(attrgetter("_reactive_post_restore_visual_damp_pending")(source))
    except AttributeError:
        legacy_pending = False
    except (TypeError, ValueError):
        legacy_pending = False

    legacy_until_value: float | None
    try:
        legacy_until_value = float(legacy_until) if legacy_until is not None else None
    except _INT_COERCION_ERRORS:
        legacy_until_value = None

    if legacy_pending:
        state._reactive_restore_phase = ReactiveRestorePhase.FIRST_PULSE_PENDING
        state._reactive_restore_damp_until = legacy_until_value
    elif legacy_until_value is not None:
        state._reactive_restore_phase = ReactiveRestorePhase.DAMPING
        state._reactive_restore_damp_until = legacy_until_value


def ensure_reactive_state(engine: object) -> ReactiveRenderState:
    try:
        state = attrgetter("_reactive_state")(engine)
    except AttributeError:
        state = None
    if isinstance(state, ReactiveRenderState):
        return state

    hydrated = ReactiveRenderState()
    if state is not None:
        _copy_reactive_state_attrs(state, hydrated)
    _copy_reactive_state_attrs(engine, hydrated)
    try:
        setattr(engine, "_reactive_state", hydrated)
    except (AttributeError, TypeError, ValueError):
        pass
    return hydrated


def _attr_target(engine: object, name: str) -> object:
    if _is_reactive_state_attr(name):
        return ensure_reactive_state(engine)
    return engine


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
    engine: object,
    name: str,
    *,
    missing_default: object,
    error_default: object,
    logger: logging.Logger | None = None,
) -> object:
    target = _attr_target(engine, name)
    return run_engine_attr_operation(
        lambda: attrgetter(name)(target),
        handled_errors=(AttributeError,),
        handled_result=missing_default,
        runtime_result=error_default,
        message="Reactive brightness failed to read engine attribute %s",
        name=name,
        logger=logger,
    )


def bool_attr_or_default(engine: object, name: str, *, default: bool) -> bool:
    target = _attr_target(engine, name)
    try:
        return bool(attrgetter(name)(target))
    except AttributeError:
        return default


def restore_phase_or_default(
    engine: object,
    *,
    default: ReactiveRestorePhase,
    logger: logging.Logger | None = None,
) -> ReactiveRestorePhase:
    raw_value = read_engine_attr(
        engine,
        "_reactive_restore_phase",
        missing_default=default,
        error_default=default,
        logger=logger,
    )
    if isinstance(raw_value, ReactiveRestorePhase):
        return raw_value
    try:
        return ReactiveRestorePhase(str(raw_value))
    except ValueError:
        return default


def set_engine_attr(
    engine: object,
    name: str,
    value: object,
    *,
    logger: logging.Logger | None = None,
    message: str = "Reactive brightness failed to set engine attribute %s",
) -> None:
    target = _attr_target(engine, name)

    def set_attr() -> None:
        setattr(target, name, value)

    run_engine_attr_operation(
        set_attr,
        handled_errors=(AttributeError, TypeError, ValueError),
        handled_result=None,
        runtime_result=None,
        message=message,
        name=name,
        logger=logger,
    )


def set_engine_compat_attr(
    engine: object,
    name: str,
    value: object,
    *,
    logger: logging.Logger | None = None,
    message: str = "Reactive brightness failed to set engine attribute %s",
) -> None:
    target = _attr_target(engine, name)
    if target is engine:
        return
    try:
        compat_mirror_to_engine = bool(attrgetter("_compat_mirror_to_engine")(target))
    except AttributeError:
        compat_mirror_to_engine = True
    if not compat_mirror_to_engine:
        return

    def set_attr() -> None:
        setattr(engine, name, value)

    run_engine_attr_operation(
        set_attr,
        handled_errors=(AttributeError, TypeError, ValueError),
        handled_result=None,
        runtime_result=None,
        message=message,
        name=name,
        logger=logger,
    )


def keyboard_or_none(engine: object) -> object | None:
    try:
        return getattr(engine, "kb")
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


def pulse_hw_lift_temporarily_disabled(engine: object, *, logger: logging.Logger) -> bool:
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


def set_uniform_hw_streak(engine: object, *, value: int, logger: logging.Logger) -> None:
    set_engine_attr(engine, "_reactive_uniform_hw_streak", max(0, int(value)), logger=logger)


def uniform_hw_streak(engine: object, *, logger: logging.Logger) -> int:
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


def clear_transition_state(engine: object, *, logger: logging.Logger) -> None:
    for name in (
        "_reactive_transition_from_brightness",
        "_reactive_transition_to_brightness",
        "_reactive_transition_started_at",
        "_reactive_transition_duration_s",
    ):
        set_engine_attr(
            engine,
            name,
            None,
            logger=logger,
            message="Reactive brightness failed to clear engine attribute %s",
        )
        set_engine_compat_attr(
            engine,
            name,
            None,
            logger=logger,
            message="Reactive brightness failed to clear engine attribute %s",
        )
