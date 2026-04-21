from __future__ import annotations

from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
from src.tray.controllers.software_target_controller import configure_engine_software_targets
from src.tray.controllers.software_target_controller import restore_secondary_software_targets
from src.tray.controllers.software_target_controller import turn_off_secondary_software_targets
from src.tray.protocols import ConfigPollingTrayProtocol

from ._apply_support import build_perkey_color_map
from ._apply_support import current_software_effect_target
from ._apply_support import has_all_uniform_capable_target
from ._apply_support import reactive_sync_values
from . import _boundaries


_CONFIG_POLLING_RUNTIME_EXCEPTIONS = _boundaries._CONFIG_POLLING_RUNTIME_EXCEPTIONS
_TRAY_LOG_WRITE_EXCEPTIONS = _boundaries._TRAY_LOG_WRITE_EXCEPTIONS
_ENGINE_ATTR_SYNC_EXCEPTIONS = _boundaries._ENGINE_ATTR_SYNC_EXCEPTIONS
_ENABLE_USER_MODE_SAVE_EXCEPTIONS = _boundaries._ENABLE_USER_MODE_SAVE_EXCEPTIONS
_CONFIG_PERSIST_SYNC_EXCEPTIONS = _boundaries._CONFIG_PERSIST_SYNC_EXCEPTIONS


def _log_module_exception(msg: str, exc: Exception) -> None:
    _boundaries._log_module_exception(msg, exc)


def _run_recoverable_boundary(action, *, runtime_exceptions, on_recoverable):
    return _boundaries._run_recoverable_boundary(
        action,
        runtime_exceptions=runtime_exceptions,
        on_recoverable=on_recoverable,
    )


def _log_tray_exception(tray: ConfigPollingTrayProtocol, msg: str, exc: Exception) -> None:
    _boundaries._log_tray_exception(
        tray,
        msg,
        exc,
        log_module_exception_fn=_log_module_exception,
        run_recoverable_boundary_fn=_run_recoverable_boundary,
    )


def _run_diagnostic_boundary(
    tray: ConfigPollingTrayProtocol,
    action,
    *,
    error_msg: str,
    default=None,
    runtime_exceptions=_CONFIG_POLLING_RUNTIME_EXCEPTIONS,
):
    return _boundaries._run_diagnostic_boundary(
        tray,
        action,
        error_msg=error_msg,
        default=default,
        runtime_exceptions=runtime_exceptions,
        log_tray_exception_fn=_log_tray_exception,
        run_recoverable_boundary_fn=_run_recoverable_boundary,
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


# Import and re-export callback implementations for test monkeypatch compatibility.
# The actual implementation is in _apply_callbacks.py.
from . import _apply_callbacks

_handle_forced_off = _apply_callbacks._handle_forced_off
_apply_turn_off = _apply_callbacks._apply_turn_off
_sync_reactive = _apply_callbacks._sync_reactive
_sync_software_target_policy = _apply_callbacks._sync_software_target_policy
_apply_perkey = _apply_callbacks._apply_perkey
_apply_uniform = _apply_callbacks._apply_uniform
_apply_effect = _apply_callbacks._apply_effect
