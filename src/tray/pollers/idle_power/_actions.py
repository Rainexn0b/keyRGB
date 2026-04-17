from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Optional, Protocol, cast

from src.core.utils.logging_utils import log_throttled
from src.core.utils.safe_attrs import safe_int_attr
from src.tray.controllers._power._transition_constants import (
    SOFT_ON_FADE_DURATION_S,
    SOFT_ON_START_BRIGHTNESS,
)
from src.tray.pollers.idle_power._action_execution import execute_idle_action
from src.tray.pollers.idle_power._transition_actions import (
    refresh_ui_best_effort,
    start_current_effect_for_idle_restore,
)
from src.tray.protocols import IdlePowerTrayProtocol


logger = logging.getLogger(__name__)
_RECOVERABLE_EFFECT_NAME_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_RECOVERABLE_BRIGHTNESS_WRITE_EXCEPTIONS = (AttributeError, OSError, OverflowError, RuntimeError, ValueError)
_IDLE_POWER_RUNTIME_BOUNDARY_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _log_idle_power_exception(
    *,
    key: str,
    level: int,
    msg: str,
    exc: Exception,
) -> None:
    log_throttled(
        logger,
        key,
        interval_s=60.0,
        level=level,
        msg=msg,
        exc=exc,
    )


def _call_runtime_boundary(
    fn: Callable[[], object],
    *,
    key: str | None = None,
    level: int = logging.ERROR,
    msg: str | None = None,
    on_recoverable: Callable[[Exception], None] | None = None,
) -> bool:
    try:
        fn()
        return True
    except _IDLE_POWER_RUNTIME_BOUNDARY_EXCEPTIONS as exc:  # @quality-exception exception-transparency: idle-power actions cross tray callbacks and runtime boundaries; must remain non-fatal for the polling loop
        if on_recoverable is not None:
            on_recoverable(exc)
            return False

        assert key is not None
        assert msg is not None
        _log_idle_power_exception(key=key, level=level, msg=msg, exc=exc)
        return False


def _tray_log_exception_or_none(tray: object) -> Callable[[str, Exception], None] | None:
    try:
        log_exception = cast(IdlePowerTrayProtocol, tray)._log_exception
    except AttributeError:
        return None
    if not callable(log_exception):
        return None
    return cast(Callable[[str, Exception], None], log_exception)


class _DimTempStateTray(Protocol):
    _dim_temp_active: bool
    _dim_temp_target_brightness: int | None


def _dim_temp_state_matches(tray: object, *, target_brightness: int) -> bool:
    try:
        dim_temp_active = cast(_DimTempStateTray, tray)._dim_temp_active
    except AttributeError:
        dim_temp_active = False
    try:
        dim_temp_target = cast(_DimTempStateTray, tray)._dim_temp_target_brightness
    except AttributeError:
        dim_temp_target = -1
    try:
        return bool(dim_temp_active) and int(dim_temp_target or -1) == int(target_brightness)
    except (TypeError, ValueError):
        return False


def _log_tray_boundary_exception(
    tray: object,
    *,
    msg: str,
    exc: Exception,
    fallback_key: str,
    fallback_level: int,
    fallback_msg: str,
) -> None:
    log_exception = _tray_log_exception_or_none(tray)
    if callable(log_exception) and _call_runtime_boundary(
        lambda: log_exception(msg, exc),
        key=f"{fallback_key}.logger",
        level=logging.ERROR,
        msg="Idle-power tray exception logger failed",
    ):
        return

    _log_idle_power_exception(
        key=fallback_key,
        level=fallback_level,
        msg=fallback_msg,
        exc=exc,
    )


def _set_engine_hw_brightness_cap(engine: object, brightness: int | None) -> None:
    """Set/clear the reactive render brightness cap on the engine.

    Used by temp-dim flows so reactive effects do not raise hardware
    brightness above a temporary policy target. Also propagates the
    ``_dim_temp_active`` flag so ``_resolve_brightness()`` can lock HW
    brightness to the dim target.
    """

    try:
        if brightness is None:
            engine._hw_brightness_cap = None  # type: ignore[attr-defined]
            engine._dim_temp_active = False  # type: ignore[attr-defined]
            return

        engine._hw_brightness_cap = max(0, min(50, int(brightness)))  # type: ignore[attr-defined]
        engine._dim_temp_active = True  # type: ignore[attr-defined]
    except (AttributeError, TypeError, ValueError):
        return


def _set_reactive_transition(
    engine: object,
    *,
    target_brightness: int,
    duration_s: float,
) -> None:
    """Seed a render-time reactive brightness transition."""

    try:
        current_i = safe_int_attr(
            engine,
            "_last_rendered_brightness",
            default=safe_int_attr(engine, "brightness", default=target_brightness),
            min_v=0,
            max_v=50,
        )
        target_i = max(0, min(50, int(target_brightness)))
        engine._reactive_transition_from_brightness = current_i  # type: ignore[attr-defined]
        engine._reactive_transition_to_brightness = target_i  # type: ignore[attr-defined]
        engine._reactive_transition_started_at = float(time.monotonic())  # type: ignore[attr-defined]
        engine._reactive_transition_duration_s = max(0.0, float(duration_s))  # type: ignore[attr-defined]
    except (AttributeError, TypeError, ValueError):
        return


def _set_brightness_best_effort(
    engine: object,
    brightness: int,
    *,
    apply_to_hardware: bool,
    fade: bool,
    fade_duration_s: float,
) -> None:
    """Call engine.set_brightness with compatibility fallbacks."""

    try:
        set_brightness = getattr(engine, "set_brightness", None)
        if not callable(set_brightness):
            return
        set_brightness_fn = cast(Callable[..., object], set_brightness)

        set_brightness_fn(
            int(brightness),
            apply_to_hardware=bool(apply_to_hardware),
            fade=bool(fade),
            fade_duration_s=float(fade_duration_s),
        )
        return
    except TypeError:
        _call_runtime_boundary(
            lambda: set_brightness_fn(int(brightness), apply_to_hardware=bool(apply_to_hardware)),
            key="idle_power.set_brightness_compat",
            level=logging.WARNING,
            msg="Idle-power compatibility brightness write failed",
        )
    except _RECOVERABLE_BRIGHTNESS_WRITE_EXCEPTIONS as exc:
        _log_idle_power_exception(
            key="idle_power.set_brightness_best_effort",
            level=logging.WARNING,
            msg="Idle-power brightness update failed",
            exc=exc,
        )


def restore_from_idle(tray: IdlePowerTrayProtocol) -> None:
    tray.is_off = False
    tray._idle_forced_off = False
    if hasattr(tray, "engine"):
        _set_engine_hw_brightness_cap(tray.engine, None)

    try:
        if hasattr(tray, "engine"):
            tray.engine.current_color = (0, 0, 0)
    except (AttributeError, TypeError):
        pass

    try:
        if safe_int_attr(tray.config, "brightness", default=0) == 0:
            tray.config.brightness = safe_int_attr(tray, "_last_brightness", default=25)
    except (AttributeError, TypeError, ValueError):
        pass

    _call_runtime_boundary(
        lambda: start_current_effect_for_idle_restore(
            tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
        ),
        on_recoverable=lambda exc: _log_tray_boundary_exception(
            tray,
            msg="Failed to restore lighting after idle: %s",
            exc=exc,
            fallback_key="idle_power.restore_from_idle",
            fallback_level=logging.ERROR,
            fallback_msg="Failed to restore lighting after idle",
        ),
    )

    refresh_ui_best_effort(
        tray,
        key="idle_power.restore_refresh_ui",
        msg="Idle-power UI refresh failed after restore",
        call_runtime_boundary=_call_runtime_boundary,
        warning_level=logging.WARNING,
    )


def apply_idle_action(
    tray: IdlePowerTrayProtocol,
    *,
    action: Optional[str],
    dim_temp_brightness: int,
    restore_from_idle_fn: Callable[[IdlePowerTrayProtocol], None],
    reactive_effects_set: frozenset[str],
    sw_effects_set: frozenset[str],
) -> None:
    execute_idle_action(
        tray,
        action=action,
        dim_temp_brightness=dim_temp_brightness,
        restore_from_idle_fn=restore_from_idle_fn,
        reactive_effects_set=reactive_effects_set,
        sw_effects_set=sw_effects_set,
        call_runtime_boundary=_call_runtime_boundary,
        dim_temp_state_matches=_dim_temp_state_matches,
        log_idle_power_exception=_log_idle_power_exception,
        set_engine_hw_brightness_cap=_set_engine_hw_brightness_cap,
        set_reactive_transition=_set_reactive_transition,
        set_brightness_best_effort=_set_brightness_best_effort,
        recoverable_effect_name_exceptions=_RECOVERABLE_EFFECT_NAME_EXCEPTIONS,
    )
