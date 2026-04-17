from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TypeVar

from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
from src.tray.controllers.software_target_controller import configure_engine_software_targets
from src.tray.controllers.software_target_controller import restore_secondary_software_targets
from src.tray.controllers.software_target_controller import turn_off_secondary_software_targets
from src.tray.protocols import ConfigPollingTrayProtocol

from ._apply_support import build_perkey_color_map
from ._apply_support import current_software_effect_target
from ._apply_support import has_all_uniform_capable_target
from ._apply_support import reactive_sync_values


logger = logging.getLogger(__name__)

_T = TypeVar("_T")

_CONFIG_POLLING_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_TRAY_LOG_WRITE_EXCEPTIONS = (OSError, RuntimeError, ValueError)
_ENGINE_ATTR_SYNC_EXCEPTIONS = (LookupError, OSError, RuntimeError, TypeError, ValueError)
_ENABLE_USER_MODE_SAVE_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, ValueError)
_CONFIG_PERSIST_SYNC_EXCEPTIONS = (LookupError, OSError, RuntimeError, TypeError, ValueError)


def _log_module_exception(msg: str, exc: Exception) -> None:
    logger.error(msg, exc, exc_info=(type(exc), exc, exc.__traceback__))


def _run_recoverable_boundary(
    action: Callable[[], _T],
    *,
    runtime_exceptions: tuple[type[Exception], ...],
    on_recoverable: Callable[[Exception], _T],
) -> _T:
    try:
        return action()
    except runtime_exceptions as exc:  # @quality-exception exception-transparency: diagnostic-only helper callbacks and best-effort tray logger writes must contain recoverable runtime failures while unexpected defects still propagate
        return on_recoverable(exc)


def _log_tray_exception(tray: ConfigPollingTrayProtocol, msg: str, exc: Exception) -> None:
    def _recover_logger_write(log_exc: Exception) -> None:
        _log_module_exception("Config polling tray exception logger failed: %s", log_exc)
        _log_module_exception(msg, exc)

    _run_recoverable_boundary(
        lambda: tray._log_exception(msg, exc),
        runtime_exceptions=_TRAY_LOG_WRITE_EXCEPTIONS,
        on_recoverable=_recover_logger_write,
    )


def _run_diagnostic_boundary(
    tray: ConfigPollingTrayProtocol,
    action: Callable[[], _T],
    *,
    error_msg: str,
    default: _T | None = None,
    runtime_exceptions: tuple[type[Exception], ...] = _CONFIG_POLLING_RUNTIME_EXCEPTIONS,
) -> _T | None:
    def _recover_boundary(exc: Exception) -> _T | None:
        _log_tray_exception(tray, error_msg, exc)
        return default

    return _run_recoverable_boundary(
        action,
        runtime_exceptions=runtime_exceptions,
        on_recoverable=_recover_boundary,
    )


def _try_log_event(tray: ConfigPollingTrayProtocol, source: str, action: str, **fields: object) -> None:
    _run_diagnostic_boundary(
        tray,
        lambda: tray._log_event(source, action, **fields),
        error_msg="Config polling event logging failed: %s",
    )


def _safe_state_for_log(tray: ConfigPollingTrayProtocol, state_for_log_fn, state):
    return _run_diagnostic_boundary(
        tray,
        lambda: state_for_log_fn(state),
        error_msg="Failed to serialize config polling state for logs: %s",
    )


def _call_tray_callback(tray: ConfigPollingTrayProtocol, callback_name: str, *, error_msg: str) -> None:
    callback = getattr(tray, callback_name, None)
    if not callable(callback):
        return
    _run_diagnostic_boundary(tray, callback, error_msg=error_msg)


def _set_engine_attr_best_effort(
    tray: ConfigPollingTrayProtocol,
    attr: str,
    value: object,
    *,
    error_msg: str,
) -> None:
    engine = getattr(tray, "engine", None)
    if engine is None:
        return
    try:
        _run_diagnostic_boundary(
            tray,
            lambda: setattr(engine, attr, value),
            error_msg=error_msg,
            runtime_exceptions=_ENGINE_ATTR_SYNC_EXCEPTIONS,
        )
    except AttributeError:
        return


def _throttled_log_exception(
    tray: ConfigPollingTrayProtocol,
    msg: str,
    exc: Exception,
    *,
    monotonic_fn,
    last_warn_at: float,
    interval: float = 60.0,
) -> float:
    now = float(monotonic_fn())
    if now - last_warn_at <= interval:
        return last_warn_at
    _log_tray_exception(tray, msg, exc)
    return now


def _enable_user_mode_best_effort(tray: ConfigPollingTrayProtocol, *, brightness: int) -> None:
    enable_user_mode = getattr(getattr(tray.engine, "kb", None), "enable_user_mode", None)
    if not callable(enable_user_mode):
        return
    try:
        _run_diagnostic_boundary(
            tray,
            lambda: enable_user_mode(brightness=brightness, save=True),
            error_msg="Failed to enable per-key user mode: %s",
            runtime_exceptions=_ENABLE_USER_MODE_SAVE_EXCEPTIONS,
        )
    except TypeError:
        _run_diagnostic_boundary(
            tray,
            lambda: enable_user_mode(brightness=brightness),
            error_msg="Failed to enable per-key user mode fallback: %s",
        )


def _log_detected_change(tray: ConfigPollingTrayProtocol, last_applied, current, cause: str, state_for_log_fn):
    old_state = _safe_state_for_log(tray, state_for_log_fn, last_applied)
    new_state = _safe_state_for_log(tray, state_for_log_fn, current)
    _try_log_event(
        tray,
        "config",
        "detected_change",
        cause=str(cause or "unknown"),
        old=old_state,
        new=new_state,
    )


def _handle_forced_off(tray: ConfigPollingTrayProtocol, last_applied, current, cause: str, state_for_log_fn):
    if not tray.is_off:
        return False

    if not (bool(tray._user_forced_off) or bool(tray._power_forced_off) or bool(tray._idle_forced_off)):
        return False

    _log_detected_change(tray, last_applied, current, cause, state_for_log_fn)
    _try_log_event(
        tray,
        "config",
        "skipped_forced_off",
        cause=str(cause or "unknown"),
        is_off=True,
        user_forced_off=bool(tray._user_forced_off),
        power_forced_off=bool(tray._power_forced_off),
        idle_forced_off=bool(tray._idle_forced_off),
    )
    _call_tray_callback(
        tray,
        "_update_menu",
        error_msg="Failed to update tray menu after forced-off config change: %s",
    )
    return True


def _apply_turn_off(tray: ConfigPollingTrayProtocol, current, cause: str, monotonic_fn, last_apply_warn_at: float):
    _try_log_event(
        tray,
        "config",
        "apply_turn_off",
        cause=str(cause or "unknown"),
        brightness=0,
    )

    def _recover_turn_off(exc: Exception) -> None:
        nonlocal last_apply_warn_at
        last_apply_warn_at = _throttled_log_exception(
            tray,
            "Failed to turn off engine: %s",
            exc,
            monotonic_fn=monotonic_fn,
            last_warn_at=last_apply_warn_at,
        )

    _run_recoverable_boundary(
        lambda: tray.engine.turn_off(),
        runtime_exceptions=_CONFIG_POLLING_RUNTIME_EXCEPTIONS,
        on_recoverable=_recover_turn_off,
    )
    if has_all_uniform_capable_target(current):
        turn_off_secondary_software_targets(tray)
    tray.is_off = True
    _call_tray_callback(
        tray,
        "_refresh_ui",
        error_msg="Failed to refresh tray UI after turning off from config: %s",
    )
    return last_apply_warn_at


def _sync_reactive(tray: ConfigPollingTrayProtocol, current) -> None:
    reactive_brightness, reactive_trail_percent = reactive_sync_values(current, tray.config)

    _set_engine_attr_best_effort(
        tray,
        "reactive_use_manual_color",
        bool(current.reactive_use_manual),
        error_msg="Failed to apply reactive manual-color flag during config polling: %s",
    )
    _set_engine_attr_best_effort(
        tray,
        "reactive_color",
        tuple(current.reactive_color),
        error_msg="Failed to apply reactive color during config polling: %s",
    )
    _set_engine_attr_best_effort(
        tray,
        "reactive_brightness",
        reactive_brightness,
        error_msg="Failed to apply reactive brightness during config polling: %s",
    )
    _set_engine_attr_best_effort(
        tray,
        "reactive_trail_percent",
        reactive_trail_percent,
        error_msg="Failed to apply reactive trail percent during config polling: %s",
    )


def _sync_software_target_policy(tray: ConfigPollingTrayProtocol, current) -> None:
    target = current_software_effect_target(current)
    try:
        _run_diagnostic_boundary(
            tray,
            lambda: setattr(tray.config, "software_effect_target", target),
            error_msg="Failed to persist software effect target during config polling: %s",
            runtime_exceptions=_CONFIG_PERSIST_SYNC_EXCEPTIONS,
        )
    except AttributeError:
        pass
    configure_engine_software_targets(tray)
    if target != SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE:
        if not bool(getattr(tray, "is_off", False)):
            restore_secondary_software_targets(tray)


def _apply_perkey(
    tray: ConfigPollingTrayProtocol, current, ite_num_rows: int, ite_num_cols: int, *, cause: str
) -> None:
    perkey_keys = 0 if current.perkey_sig is None else len(current.perkey_sig)
    _try_log_event(
        tray,
        "config",
        "apply_perkey",
        cause=str(cause or "unknown"),
        brightness=int(current.brightness),
        perkey_keys=int(perkey_keys),
    )
    tray.engine.stop()
    color_map = build_perkey_color_map(
        tray.config,
        ite_num_rows=ite_num_rows,
        ite_num_cols=ite_num_cols,
        base_color=tuple(current.color),
    )

    with tray.engine.kb_lock:
        _enable_user_mode_best_effort(tray, brightness=int(current.brightness))
        tray.engine.kb.set_key_colors(
            color_map,
            brightness=current.brightness,
            enable_user_mode=True,
        )
    if has_all_uniform_capable_target(current):
        restore_secondary_software_targets(tray)


def _apply_uniform(tray: ConfigPollingTrayProtocol, current, *, cause: str) -> None:
    _try_log_event(
        tray,
        "config",
        "apply_uniform",
        cause=str(cause or "unknown"),
        brightness=int(current.brightness),
        color=tuple(current.color),
    )
    tray.engine.stop()
    with tray.engine.kb_lock:
        tray.engine.kb.set_color(current.color, brightness=current.brightness)
    if has_all_uniform_capable_target(current):
        restore_secondary_software_targets(tray)


def _apply_effect(tray: ConfigPollingTrayProtocol, current, *, cause: str) -> None:
    _try_log_event(
        tray,
        "config",
        "apply_effect",
        cause=str(cause or "unknown"),
        effect=str(current.effect),
        speed=int(current.speed),
        brightness=int(current.brightness),
        color=tuple(current.color),
    )
    tray._start_current_effect()
