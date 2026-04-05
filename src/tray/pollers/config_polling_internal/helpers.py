from __future__ import annotations

import logging

from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
from src.core.effects.software_targets import normalize_software_effect_target
from src.core.utils.safe_attrs import safe_int_attr
from src.tray.controllers.software_target_controller import configure_engine_software_targets
from src.tray.controllers.software_target_controller import restore_secondary_software_targets
from src.tray.controllers.software_target_controller import turn_off_secondary_software_targets
from src.tray.protocols import ConfigPollingTrayProtocol


logger = logging.getLogger(__name__)


def _log_module_exception(msg: str, exc: Exception) -> None:
    logger.error(msg, exc, exc_info=(type(exc), exc, exc.__traceback__))


def _log_tray_exception(tray: ConfigPollingTrayProtocol, msg: str, exc: Exception) -> None:
    try:
        tray._log_exception(msg, exc)
        return
    except Exception as log_exc:  # @quality-exception exception-transparency: tray exception logger is a best-effort diagnostic boundary
        _log_module_exception("Config polling tray exception logger failed: %s", log_exc)
    _log_module_exception(msg, exc)


def _try_log_event(tray: ConfigPollingTrayProtocol, source: str, action: str, **fields: object) -> None:
    try:
        tray._log_event(source, action, **fields)
    except Exception as exc:  # @quality-exception exception-transparency: event logging must never break config polling
        _log_tray_exception(tray, "Config polling event logging failed: %s", exc)


def _safe_state_for_log(tray: ConfigPollingTrayProtocol, state_for_log_fn, state):
    try:
        return state_for_log_fn(state)
    except Exception as exc:  # @quality-exception exception-transparency: debug-state serialization; best-effort
        _log_tray_exception(tray, "Failed to serialize config polling state for logs: %s", exc)
        return None


def _call_tray_callback(tray: ConfigPollingTrayProtocol, callback_name: str, *, error_msg: str) -> None:
    callback = getattr(tray, callback_name, None)
    if not callable(callback):
        return
    try:
        callback()
    except (  # @quality-exception exception-transparency: tray callbacks are best-effort during config polling
        Exception
    ) as exc:
        _log_tray_exception(tray, error_msg, exc)


def _set_engine_attr_best_effort(
    tray: ConfigPollingTrayProtocol,
    attr: str,
    value: object,
    *,
    error_msg: str,
) -> None:
    engine = getattr(tray, "engine", None)
    try:
        setattr(engine, attr, value)
    except AttributeError:
        return
    except (  # @quality-exception exception-transparency: engine sync; tolerates backend-specific setters
        Exception
    ) as exc:
        _log_tray_exception(tray, error_msg, exc)


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
        enable_user_mode(brightness=brightness, save=True)
    except TypeError:
        try:
            enable_user_mode(brightness=brightness)
        except Exception as exc:  # @quality-exception exception-transparency: per-key backend fallback still crosses a runtime backend boundary
            _log_tray_exception(tray, "Failed to enable per-key user mode fallback: %s", exc)
    except Exception as exc:  # @quality-exception exception-transparency: user-mode enable; runtime backend boundary
        _log_tray_exception(tray, "Failed to enable per-key user mode: %s", exc)


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
    try:
        tray.engine.turn_off()
    except Exception as exc:  # @quality-exception exception-transparency: engine shutdown is a runtime backend boundary during config polling
        last_apply_warn_at = _throttled_log_exception(
            tray,
            "Failed to turn off engine: %s",
            exc,
            monotonic_fn=monotonic_fn,
            last_warn_at=last_apply_warn_at,
        )
    if (
        str(getattr(current, "software_effect_target", "keyboard") or "keyboard")
        == SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
    ):
        turn_off_secondary_software_targets(tray)
    tray.is_off = True
    _call_tray_callback(
        tray,
        "_refresh_ui",
        error_msg="Failed to refresh tray UI after turning off from config: %s",
    )
    return last_apply_warn_at


def _sync_reactive(tray: ConfigPollingTrayProtocol, current) -> None:
    reactive_brightness = getattr(
        current,
        "reactive_brightness",
        safe_int_attr(
            tray.config,
            "reactive_brightness",
            default=safe_int_attr(tray.config, "brightness", default=0),
        ),
    )
    try:
        reactive_brightness = int(reactive_brightness or 0)
    except (TypeError, ValueError, OverflowError):
        reactive_brightness = 0

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


def _sync_software_target_policy(tray: ConfigPollingTrayProtocol, current) -> None:
    target = normalize_software_effect_target(getattr(current, "software_effect_target", "keyboard"))
    try:
        tray.config.software_effect_target = target
    except AttributeError:
        pass
    except Exception as exc:  # @quality-exception exception-transparency: config persistence failure must not block runtime target sync
        _log_tray_exception(tray, "Failed to persist software effect target during config polling: %s", exc)
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
    configured_map = getattr(tray.config, "per_key_colors", None)
    if configured_map is None:
        configured_map = {}
    color_map = configured_map

    if 0 < len(configured_map) < (ite_num_rows * ite_num_cols):
        color_map = dict(configured_map)
        base = tuple(current.color)
        for r in range(ite_num_rows):
            for c in range(ite_num_cols):
                color_map.setdefault((r, c), base)

    with tray.engine.kb_lock:
        _enable_user_mode_best_effort(tray, brightness=int(current.brightness))
        tray.engine.kb.set_key_colors(
            color_map,
            brightness=current.brightness,
            enable_user_mode=True,
        )
    if (
        str(getattr(current, "software_effect_target", "keyboard") or "keyboard")
        == SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
    ):
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
    if (
        str(getattr(current, "software_effect_target", "keyboard") or "keyboard")
        == SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
    ):
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
