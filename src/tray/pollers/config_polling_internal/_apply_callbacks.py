"""Config polling callback implementations (policy + side effects).

These functions implement the "what specific lighting modes to apply" decisions.
They rely on helpers.py scaffold for "how to apply safely" infrastructure.
"""

from __future__ import annotations

from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
from src.tray.protocols import ConfigPollingTrayProtocol

from ._apply_support import build_perkey_color_map
from ._apply_support import current_software_effect_target
from ._apply_support import has_all_uniform_capable_target
from ._apply_support import reactive_sync_values
from . import helpers as _helpers


def _handle_forced_off(tray: ConfigPollingTrayProtocol, last_applied, current, cause: str, state_for_log_fn):
    if not tray.is_off:
        return False

    if not (bool(tray._user_forced_off) or bool(tray._power_forced_off) or bool(tray._idle_forced_off)):
        return False

    _helpers._log_detected_change(tray, last_applied, current, cause, state_for_log_fn)
    _helpers._try_log_event(
        tray,
        "config",
        "skipped_forced_off",
        cause=str(cause or "unknown"),
        is_off=True,
        user_forced_off=bool(tray._user_forced_off),
        power_forced_off=bool(tray._power_forced_off),
        idle_forced_off=bool(tray._idle_forced_off),
    )
    _helpers._call_tray_callback(
        tray,
        "_update_menu",
        error_msg="Failed to update tray menu after forced-off config change: %s",
    )
    return True


def _apply_turn_off(tray: ConfigPollingTrayProtocol, current, cause: str, monotonic_fn, last_apply_warn_at: float):
    _helpers._try_log_event(
        tray,
        "config",
        "apply_turn_off",
        cause=str(cause or "unknown"),
        brightness=0,
    )

    def _recover_turn_off(exc: Exception) -> None:
        nonlocal last_apply_warn_at
        last_apply_warn_at = _helpers._throttled_log_exception(
            tray,
            "Failed to turn off engine: %s",
            exc,
            monotonic_fn=monotonic_fn,
            last_warn_at=last_apply_warn_at,
        )

    _helpers._run_recoverable_boundary(
        lambda: tray.engine.turn_off(),
        runtime_exceptions=_helpers._CONFIG_POLLING_RUNTIME_EXCEPTIONS,
        on_recoverable=_recover_turn_off,
    )
    if has_all_uniform_capable_target(current):
        _helpers.turn_off_secondary_software_targets(tray)
    tray.is_off = True
    _helpers._call_tray_callback(
        tray,
        "_refresh_ui",
        error_msg="Failed to refresh tray UI after turning off from config: %s",
    )
    return last_apply_warn_at


def _sync_reactive(tray: ConfigPollingTrayProtocol, current) -> None:
    reactive_brightness, reactive_trail_percent = reactive_sync_values(current, tray.config)

    _helpers._set_engine_attr_best_effort(
        tray,
        "reactive_use_manual_color",
        bool(current.reactive_use_manual),
        error_msg="Failed to apply reactive manual-color flag during config polling: %s",
    )
    _helpers._set_engine_attr_best_effort(
        tray,
        "reactive_color",
        tuple(current.reactive_color),
        error_msg="Failed to apply reactive color during config polling: %s",
    )
    _helpers._set_engine_attr_best_effort(
        tray,
        "reactive_brightness",
        reactive_brightness,
        error_msg="Failed to apply reactive brightness during config polling: %s",
    )
    _helpers._set_engine_attr_best_effort(
        tray,
        "reactive_trail_percent",
        reactive_trail_percent,
        error_msg="Failed to apply reactive trail percent during config polling: %s",
    )


def _sync_software_target_policy(tray: ConfigPollingTrayProtocol, current) -> None:
    target = current_software_effect_target(current)
    try:
        _helpers._run_diagnostic_boundary(
            tray,
            lambda: setattr(tray.config, "software_effect_target", target),
            error_msg="Failed to persist software effect target during config polling: %s",
            runtime_exceptions=_helpers._CONFIG_PERSIST_SYNC_EXCEPTIONS,
        )
    except AttributeError:
        pass
    _helpers.configure_engine_software_targets(tray)
    if target != SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE:
        if not bool(getattr(tray, "is_off", False)):
            _helpers.restore_secondary_software_targets(tray)


def _apply_perkey(
    tray: ConfigPollingTrayProtocol, current, ite_num_rows: int, ite_num_cols: int, *, cause: str
) -> None:
    perkey_keys = 0 if current.perkey_sig is None else len(current.perkey_sig)
    _helpers._try_log_event(
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
        _helpers._enable_user_mode_best_effort(tray, brightness=int(current.brightness))
        tray.engine.kb.set_key_colors(
            color_map,
            brightness=current.brightness,
            enable_user_mode=True,
        )
    if has_all_uniform_capable_target(current):
        _helpers.restore_secondary_software_targets(tray)


def _apply_uniform(tray: ConfigPollingTrayProtocol, current, *, cause: str) -> None:
    _helpers._try_log_event(
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
        _helpers.restore_secondary_software_targets(tray)


def _apply_effect(tray: ConfigPollingTrayProtocol, current, *, cause: str) -> None:
    _helpers._try_log_event(
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
