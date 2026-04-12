from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Optional, Protocol, cast

from src.core.utils.logging_utils import log_throttled
from src.core.utils.safe_attrs import safe_int_attr
from src.tray.controllers._power._transition_constants import (
    SOFT_OFF_FADE_DURATION_S,
    SOFT_ON_FADE_DURATION_S,
    SOFT_ON_START_BRIGHTNESS,
)
from src.tray.pollers.idle_power._transition_actions import (
    apply_dim_temp_brightness,
    apply_restore_brightness,
    read_effect_name,
    refresh_ui_best_effort,
    start_current_effect_for_idle_restore,
)
from src.tray.protocols import IdlePowerTrayProtocol


logger = logging.getLogger(__name__)
_RECOVERABLE_EFFECT_NAME_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_RECOVERABLE_BRIGHTNESS_WRITE_EXCEPTIONS = (AttributeError, OSError, OverflowError, RuntimeError, ValueError)
_IDLE_POWER_CALLBACK_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
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
    key: str,
    level: int,
    msg: str,
) -> bool:
    try:
        fn()
        return True
    except _IDLE_POWER_RUNTIME_BOUNDARY_EXCEPTIONS as exc:  # @quality-exception exception-transparency: idle-power actions cross tray callbacks and runtime boundaries; must remain non-fatal for the polling loop
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
    if callable(log_exception):
        try:
            log_exception(msg, exc)
            return
        except _IDLE_POWER_CALLBACK_RUNTIME_EXCEPTIONS as log_exc:  # @quality-exception exception-transparency: tray exception logging is a best-effort callback boundary during idle-power recovery
            _log_idle_power_exception(
                key=f"{fallback_key}.logger",
                level=logging.ERROR,
                msg="Idle-power tray exception logger failed",
                exc=log_exc,
            )

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

    try:
        start_current_effect_for_idle_restore(
            tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
        )
    except _IDLE_POWER_RUNTIME_BOUNDARY_EXCEPTIONS as exc:  # @quality-exception exception-transparency: idle-power restore crosses tray callback wiring and lighting startup boundaries; best-effort
        _log_tray_boundary_exception(
            tray,
            msg="Failed to restore lighting after idle: %s",
            exc=exc,
            fallback_key="idle_power.restore_from_idle",
            fallback_level=logging.ERROR,
            fallback_msg="Failed to restore lighting after idle",
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
    if action == "turn_off":
        tray._dim_temp_active = False
        tray._dim_temp_target_brightness = None
        _set_engine_hw_brightness_cap(tray.engine, None)
        _call_runtime_boundary(
            lambda: tray.engine.stop(),
            key="idle_power.turn_off.stop_engine",
            level=logging.WARNING,
            msg="Idle-power turn-off failed while stopping engine",
        )
        _call_runtime_boundary(
            lambda: tray.engine.turn_off(fade=True, fade_duration_s=SOFT_OFF_FADE_DURATION_S),
            key="idle_power.turn_off.turn_off",
            level=logging.WARNING,
            msg="Idle-power turn-off failed while writing off state",
        )

        tray.is_off = True
        tray._idle_forced_off = True
        refresh_ui_best_effort(
            tray,
            key="idle_power.turn_off.refresh_ui",
            msg="Idle-power UI refresh failed after turn-off",
            call_runtime_boundary=_call_runtime_boundary,
            warning_level=logging.WARNING,
        )
        return

    if action == "dim_to_temp":
        if not bool(tray.is_off):
            if _dim_temp_state_matches(tray, target_brightness=dim_temp_brightness):
                return
            tray._dim_temp_active = True
            tray._dim_temp_target_brightness = int(dim_temp_brightness)
            effect = read_effect_name(
                tray.config,
                log_key="idle_power.dim_to_temp.effect_name",
                log_msg="Idle-power dim-to-temp could not read effect name; falling back to none",
                log_idle_power_exception=_log_idle_power_exception,
                warning_level=logging.WARNING,
                recoverable_effect_name_exceptions=_RECOVERABLE_EFFECT_NAME_EXCEPTIONS,
            )
            _call_runtime_boundary(
                lambda: apply_dim_temp_brightness(
                    tray,
                    effect=effect,
                    dim_temp_brightness=dim_temp_brightness,
                    reactive_effects_set=reactive_effects_set,
                    sw_effects_set=sw_effects_set,
                    soft_off_fade_duration_s=SOFT_OFF_FADE_DURATION_S,
                    set_reactive_transition=_set_reactive_transition,
                    set_brightness_best_effort=_set_brightness_best_effort,
                ),
                key="idle_power.dim_to_temp.apply",
                level=logging.WARNING,
                msg="Idle-power dim-to-temp apply failed",
            )
        return

    if action == "restore_brightness":
        tray._dim_temp_active = False
        tray._dim_temp_target_brightness = None
        config = tray.config
        target = safe_int_attr(config, "brightness", default=0)
        perkey_target = safe_int_attr(config, "perkey_brightness", default=0)
        effect = read_effect_name(
            config,
            log_key="idle_power.restore_brightness.read_state",
            log_msg="Idle-power restore could not read brightness state; using safe defaults",
            log_idle_power_exception=_log_idle_power_exception,
            warning_level=logging.WARNING,
            recoverable_effect_name_exceptions=_RECOVERABLE_EFFECT_NAME_EXCEPTIONS,
        )
        if target > 0 and not bool(tray.is_off):
            _call_runtime_boundary(
                lambda: apply_restore_brightness(
                    tray,
                    effect=effect,
                    target=target,
                    perkey_target=perkey_target,
                    reactive_effects_set=reactive_effects_set,
                    sw_effects_set=sw_effects_set,
                    soft_on_fade_duration_s=SOFT_ON_FADE_DURATION_S,
                    set_reactive_transition=_set_reactive_transition,
                    set_engine_hw_brightness_cap=_set_engine_hw_brightness_cap,
                    set_brightness_best_effort=_set_brightness_best_effort,
                ),
                key="idle_power.restore_brightness.apply",
                level=logging.WARNING,
                msg="Idle-power restore-brightness apply failed",
            )
        return

    if action == "restore":
        if not bool(tray._user_forced_off) and not bool(tray._power_forced_off):
            tray._dim_temp_active = False
            tray._dim_temp_target_brightness = None
            if hasattr(tray, "engine"):
                _set_engine_hw_brightness_cap(tray.engine, None)
            restore_from_idle_fn(tray)
        return
