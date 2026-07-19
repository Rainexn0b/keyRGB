from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
import os
import threading
import time
from operator import attrgetter
from typing import Callable

_LOGGER = logging.getLogger(__name__)
_INT_COERCION_ERRORS = (TypeError, ValueError, OverflowError)
_ENGINE_RECOVERABLE_RUNTIME_ERRORS = (LookupError, OSError, RuntimeError)
_ENGINE_PROGRAMMING_ERRORS = (TypeError, ValueError)
_ENGINE_ATTR_RUNTIME_ERRORS = _ENGINE_RECOVERABLE_RUNTIME_ERRORS + _ENGINE_PROGRAMMING_ERRORS


class ReactiveRestorePhase(str, Enum):
    NORMAL = "normal"
    FIRST_PULSE_PENDING = "first_pulse_pending"
    DAMPING = "damping"


@dataclass(slots=True)
class ReactiveRenderState:
    """Consolidated state for reactive brightness rendering.

    Lifecycle:
    - Initialised in EffectsEngine.__init__ as ReactiveRenderState()
    - Reset on engine.stop() to clear stale timers
    - Seeded by idle-power transitions for dim/restore ramps
    - Read every frame by resolve_brightness() and the render loop
    - Transition fields are written atomically via seed_transition_atomic()
      under engine.reactive_lock
    """

    # --- Brightness transition animation ---
    # When set, resolve_brightness() animates from _from to _to
    # over _duration_s seconds starting at _started_at.
    # Cleared when the transition completes.
    _reactive_transition_from_brightness: int | None = None
    _reactive_transition_to_brightness: int | None = None
    _reactive_transition_started_at: float | None = None
    _reactive_transition_duration_s: float | None = None

    # --- Post-restore pulse damp ---
    # After an idle wake or temp-dim restore, hardware brightness is
    # low (e.g. 1) and needs to ramp up. During this ramp, reactive
    # pulses would appear as a bright flash if allowed at full intensity.
    # The holdoff delays the streak gate for hardware lifts, and the
    # damp reduces pulse visual scale during the window.
    _reactive_disable_pulse_hw_lift_until: float | None = None
    _reactive_restore_phase: ReactiveRestorePhase = ReactiveRestorePhase.NORMAL
    _reactive_restore_damp_until: float | None = None

    # --- Uniform backend streak gate ---
    # Counts consecutive frames with active pulse on uniform-only backends.
    # Must reach UNIFORM_PULSE_HW_LIFT_STREAK_MIN (6) before a hardware
    # brightness lift is permitted. Reset to 0 on per-key backends.
    _reactive_uniform_hw_streak: int = 0

    # --- Pulse mix tracking ---
    # Tracks the current pulse intensity (0.0..1.0) for the streak gate
    # and visual scale calculation. Rises on keypress, decays per frame.
    _reactive_follow_global_brightness: bool = False
    _reactive_active_pulse_mix: float = 0.0

    # --- Debug-only state change logs ---
    # Each field stores the last-logged tuple so that repeated identical
    # states are suppressed. Only active when KEYRGB_DEBUG_BRIGHTNESS=1.
    _reactive_debug_hw_lift_state: tuple[object, ...] | None = None
    _reactive_debug_pulse_visual_state: tuple[object, ...] | None = None
    _reactive_debug_last_pulse_scale: float = 1.0
    _reactive_debug_render_visual_state: tuple[object, ...] | None = None


_REACTIVE_STATE_ATTR_NAMES = frozenset(ReactiveRenderState.__annotations__)


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
    except _ENGINE_PROGRAMMING_ERRORS as exc:
        active_logger.warning("%s (programming error for attribute %s)", message, name, exc_info=exc)
        return runtime_result
    except _ENGINE_RECOVERABLE_RUNTIME_ERRORS:  # @quality-exception exception-transparency: engine attribute getters/setters may have recoverable runtime side effects during reactive brightness resolution and cleanup
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


def increment_uniform_hw_streak(
    engine: object,
    *,
    per_key_hw: bool,
    logger: logging.Logger,
) -> int:
    if per_key_hw:
        set_engine_attr(engine, "_reactive_uniform_hw_streak", 0, logger=logger)
        return 0
    current = uniform_hw_streak(engine, logger=logger)
    new_value = current + 1
    set_engine_attr(engine, "_reactive_uniform_hw_streak", new_value, logger=logger)
    return new_value


_PENDING_RESTORE_SEED_ATTR = "_pending_reactive_restore_seed"


@dataclass(frozen=True, slots=True)
class ReactiveRestoreSeed:
    """Restore damp timers applied onto a fresh ReactiveRenderState after stop()."""

    disable_pulse_hw_lift_until: float
    restore_damp_until: float
    restore_phase: ReactiveRestorePhase = ReactiveRestorePhase.FIRST_PULSE_PENDING


def build_reactive_restore_seed(*, fade_in_duration_s: float, now: float | None = None) -> ReactiveRestoreSeed:
    """Build restore damp timers for idle full-off → on wake."""

    current = float(time.monotonic() if now is None else now)
    fade_s = float(fade_in_duration_s)
    return ReactiveRestoreSeed(
        disable_pulse_hw_lift_until=current + max(2.0, fade_s + 0.75),
        restore_damp_until=current + max(4.0, fade_s + 2.75),
        restore_phase=ReactiveRestorePhase.FIRST_PULSE_PENDING,
    )


def queue_reactive_restore_seed(engine: object, seed: ReactiveRestoreSeed) -> None:
    """Queue a seed so the next ``ReactiveRenderState()`` reset inherits it.

    ``engine.stop()`` rebuilds reactive state and would otherwise clear restore
    damp before the render thread's first frames, racing post-start seeding.
    """

    try:
        setattr(engine, _PENDING_RESTORE_SEED_ATTR, seed)
    except (AttributeError, TypeError):
        return


def apply_queued_reactive_restore_seed(engine: object) -> bool:
    """Apply and clear a queued restore seed onto the current reactive state."""

    try:
        seed = getattr(engine, _PENDING_RESTORE_SEED_ATTR, None)
    except (AttributeError, TypeError):
        return False
    if not isinstance(seed, ReactiveRestoreSeed):
        return False
    try:
        setattr(engine, _PENDING_RESTORE_SEED_ATTR, None)
    except (AttributeError, TypeError):
        pass
    return apply_reactive_restore_seed(engine, seed)


def apply_reactive_restore_seed(engine: object, seed: ReactiveRestoreSeed) -> bool:
    """Write restore damp timers onto the live reactive state."""

    try:
        state = ensure_reactive_state(engine)
        state._reactive_disable_pulse_hw_lift_until = float(seed.disable_pulse_hw_lift_until)
        state._reactive_restore_damp_until = float(seed.restore_damp_until)
        state._reactive_restore_phase = seed.restore_phase
        return True
    except (AttributeError, TypeError, ValueError):
        return False


def seed_reactive_restore_windows(engine: object, *, fade_in_duration_s: float, now: float | None = None) -> bool:
    """Queue + apply restore damp (call before and after effect start on idle wake)."""

    seed = build_reactive_restore_seed(fade_in_duration_s=fade_in_duration_s, now=now)
    queue_reactive_restore_seed(engine, seed)
    return apply_reactive_restore_seed(engine, seed)


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


def seed_transition_atomic(
    state: ReactiveRenderState,
    lock: threading.Lock,
    *,
    from_brightness: int,
    to_brightness: int,
    started_at: float,
    duration_s: float,
) -> None:
    with lock:
        state._reactive_transition_from_brightness = from_brightness
        state._reactive_transition_to_brightness = to_brightness
        state._reactive_transition_started_at = started_at
        state._reactive_transition_duration_s = duration_s


def read_transition_atomic(
    state: ReactiveRenderState,
    lock: threading.Lock,
) -> tuple[int | None, int | None, float | None, float | None]:
    with lock:
        return (
            state._reactive_transition_from_brightness,
            state._reactive_transition_to_brightness,
            state._reactive_transition_started_at,
            state._reactive_transition_duration_s,
        )


def clear_transition_atomic(
    state: ReactiveRenderState,
    lock: threading.Lock,
) -> None:
    with lock:
        state._reactive_transition_from_brightness = None
        state._reactive_transition_to_brightness = None
        state._reactive_transition_started_at = None
        state._reactive_transition_duration_s = None


# Re-export debug log helpers for stable import path (split for LOC / D14).
from . import _render_brightness_debug as _debug  # noqa: E402

log_hw_lift_decision_change = _debug.log_hw_lift_decision_change
log_pulse_visual_scale_change = _debug.log_pulse_visual_scale_change
log_render_visual_scale_change = _debug.log_render_visual_scale_change
