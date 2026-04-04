from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

from src.core.effects.catalog import REACTIVE_EFFECTS, SW_EFFECTS_SET as SW_EFFECTS
from src.core.utils.safe_attrs import safe_str_attr
from src.tray.protocols import IdlePowerTrayProtocol

from ._actions import apply_idle_action as _apply_idle_action_impl
from ._actions import restore_from_idle as _restore_from_idle_impl
from ._logind import read_logind_idle_seconds as _read_logind_idle_seconds_impl
from ._runtime import IdlePollLoopState, run_idle_power_iteration
from ._utils import build_idle_action_key as _build_idle_action_key_impl
from ._utils import debounce_dim_and_screen_off as _debounce_dim_and_screen_off_impl
from ._utils import should_log_idle_action as _should_log_idle_action_impl
from .policy import IdleAction, compute_idle_action
from .sensors import (
    get_session_id as _get_session_id_impl,
    read_dimmed_state as _read_dimmed_state_impl,
    read_screen_off_state_drm as _read_screen_off_state_drm_impl,
    run as _run_impl,
)


REACTIVE_EFFECTS_SET = frozenset(REACTIVE_EFFECTS)
logger = logging.getLogger(__name__)


def _log_module_exception(msg: str, exc: Exception) -> None:
    logger.error(msg, exc, exc_info=(type(exc), exc, exc.__traceback__))


def _log_tray_exception(tray: IdlePowerTrayProtocol, msg: str, exc: Exception) -> None:
    log_exception = getattr(tray, "_log_exception", None)
    if callable(log_exception):
        try:
            log_exception(msg, exc)
            return
        except Exception as log_exc:  # @quality-exception exception-transparency: tray exception logging is a best-effort callback boundary during idle-power polling
            _log_module_exception("Idle power tray exception logger failed: %s", log_exc)

    _log_module_exception(msg, exc)


def _try_log_event(tray: IdlePowerTrayProtocol, source: str, action: str, **fields: object) -> None:
    log_event = getattr(tray, "_log_event", None)
    if not callable(log_event):
        return
    try:
        log_event(source, action, **fields)
    except Exception as exc:  # @quality-exception exception-transparency: idle-power event logging is a best-effort diagnostic boundary and must not affect polling
        _log_tray_exception(tray, "Idle power event logging failed: %s", exc)


def _effective_screen_dim_sync_enabled(tray: IdlePowerTrayProtocol, requested_enabled: bool) -> bool:
    if not requested_enabled:
        return False

    backend = vars(tray).get("backend")
    backend_name = safe_str_attr(backend, "name", default="") if backend is not None else ""

    if backend_name.startswith("asusctl"):
        allow = os.environ.get("KEYRGB_ALLOW_DIM_SYNC_ASUSCTL", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not allow:
            if not tray._dim_sync_suppressed_logged:
                setattr(tray, "_dim_sync_suppressed_logged", True)
                _try_log_event(
                    tray,
                    "idle_power",
                    "dim_sync_suppressed",
                    backend=str(backend_name),
                    env_override="KEYRGB_ALLOW_DIM_SYNC_ASUSCTL",
                )
            return False

    return True


def _compute_idle_action(
    *,
    dimmed: Optional[bool],
    screen_off: bool,
    is_off: bool,
    idle_forced_off: bool,
    dim_temp_active: bool,
    idle_timeout_s: float,
    power_management_enabled: bool,
    screen_dim_sync_enabled: bool,
    screen_dim_sync_mode: str,
    screen_dim_temp_brightness: int,
    brightness: int,
    user_forced_off: bool,
    power_forced_off: bool,
    last_resume_at: float = 0.0,
    now: float = 0.0,
) -> IdleAction:
    return compute_idle_action(
        dimmed=dimmed,
        screen_off=screen_off,
        is_off=is_off,
        idle_forced_off=idle_forced_off,
        dim_temp_active=dim_temp_active,
        idle_timeout_s=idle_timeout_s,
        power_management_enabled=power_management_enabled,
        screen_dim_sync_enabled=screen_dim_sync_enabled,
        screen_dim_sync_mode=screen_dim_sync_mode,
        screen_dim_temp_brightness=screen_dim_temp_brightness,
        brightness=brightness,
        user_forced_off=user_forced_off,
        power_forced_off=power_forced_off,
        last_resume_at=last_resume_at,
        now=now,
    )


def _ensure_idle_state(tray: IdlePowerTrayProtocol) -> None:
    tray_vars = vars(tray)

    if "_idle_forced_off" not in tray_vars:
        tray._idle_forced_off = False
    if "_user_forced_off" not in tray_vars:
        tray._user_forced_off = False
    if "_power_forced_off" not in tray_vars:
        tray._power_forced_off = False
    if "_dim_backlight_baselines" not in tray_vars:
        tray._dim_backlight_baselines = {}
    if "_dim_backlight_dimmed" not in tray_vars:
        tray._dim_backlight_dimmed = {}
    if "_dim_temp_active" not in tray_vars:
        tray._dim_temp_active = False
    if "_dim_temp_target_brightness" not in tray_vars:
        tray._dim_temp_target_brightness = None
    if "_dim_screen_off" not in tray_vars:
        tray._dim_screen_off = False
    if "_last_resume_at" not in tray_vars:
        tray._last_resume_at = 0.0
    if "_dim_sync_suppressed_logged" not in tray_vars:
        tray._dim_sync_suppressed_logged = False


def _read_dimmed_state(tray: IdlePowerTrayProtocol) -> Optional[bool]:
    return _read_dimmed_state_impl(tray)


def _read_screen_off_state_drm() -> Optional[bool]:
    return _read_screen_off_state_drm_impl()


def _run(argv: list[str], *, timeout_s: float = 1.0) -> Optional[str]:
    return _run_impl(argv, timeout_s=timeout_s)


def _get_session_id() -> Optional[str]:
    return _get_session_id_impl()


def _read_logind_idle_seconds(*, session_id: str) -> Optional[float]:
    return _read_logind_idle_seconds_impl(
        session_id=session_id,
        run_fn=lambda argv, timeout_s: _run(argv, timeout_s=timeout_s),
        monotonic_fn=time.monotonic,
    )


def _restore_from_idle(tray: IdlePowerTrayProtocol) -> None:
    return _restore_from_idle_impl(tray)


def _apply_idle_action(
    tray: IdlePowerTrayProtocol,
    *,
    action: IdleAction,
    dim_temp_brightness: int,
) -> None:
    return _apply_idle_action_impl(
        tray,
        action=action,
        dim_temp_brightness=int(dim_temp_brightness),
        restore_from_idle_fn=_restore_from_idle,
        reactive_effects_set=REACTIVE_EFFECTS_SET,
        sw_effects_set=SW_EFFECTS,
    )


def _debounce_dim_and_screen_off(
    *,
    dimmed_raw: Optional[bool],
    screen_off_raw: bool,
    dimmed_true_streak: int,
    dimmed_false_streak: int,
    screen_off_true_streak: int,
    debounce_polls_dimmed_true: int,
    debounce_polls_dimmed_false: int,
    debounce_polls_screen_off_true: int,
) -> tuple[Optional[bool], bool, int, int, int]:
    return _debounce_dim_and_screen_off_impl(
        dimmed_raw=dimmed_raw,
        screen_off_raw=screen_off_raw,
        dimmed_true_streak=dimmed_true_streak,
        dimmed_false_streak=dimmed_false_streak,
        screen_off_true_streak=screen_off_true_streak,
        debounce_polls_dimmed_true=debounce_polls_dimmed_true,
        debounce_polls_dimmed_false=debounce_polls_dimmed_false,
        debounce_polls_screen_off_true=debounce_polls_screen_off_true,
    )


def _build_idle_action_key(
    *,
    action: IdleAction,
    dimmed: Optional[bool],
    screen_off: bool,
    brightness: int,
    dim_sync_mode: str,
    dim_temp_brightness: int,
) -> str:
    return _build_idle_action_key_impl(
        action=action,
        dimmed=dimmed,
        screen_off=bool(screen_off),
        brightness=int(brightness),
        dim_sync_mode=str(dim_sync_mode),
        dim_temp_brightness=int(dim_temp_brightness),
    )


def _should_log_idle_action(
    *,
    action: IdleAction,
    action_key: str,
    last_action_key: Optional[str],
) -> bool:
    return _should_log_idle_action_impl(
        action=action,
        action_key=str(action_key),
        last_action_key=last_action_key,
    )


def start_idle_power_polling(
    tray: IdlePowerTrayProtocol,
    *,
    ite_num_rows: int,
    ite_num_cols: int,
    idle_timeout_s: float = 60.0,
) -> None:
    """Power-management: sync keyboard lighting with display dimming."""

    _ensure_idle_state(tray)

    def poll_idle_power() -> None:
        loop_state = IdlePollLoopState()
        session_id = _get_session_id()

        while True:
            try:
                run_idle_power_iteration(
                    tray,
                    loop_state=loop_state,
                    idle_timeout_s=float(idle_timeout_s),
                    session_id=session_id,
                    now_monotonic_fn=time.monotonic,
                    ensure_idle_state_fn=_ensure_idle_state,
                    read_dimmed_state_fn=_read_dimmed_state,
                    read_screen_off_state_drm_fn=_read_screen_off_state_drm,
                    debounce_dim_and_screen_off_fn=_debounce_dim_and_screen_off,
                    read_logind_idle_seconds_fn=_read_logind_idle_seconds,
                    effective_screen_dim_sync_enabled_fn=_effective_screen_dim_sync_enabled,
                    compute_idle_action_fn=_compute_idle_action,
                    build_idle_action_key_fn=_build_idle_action_key,
                    should_log_idle_action_fn=_should_log_idle_action,
                    apply_idle_action_fn=_apply_idle_action,
                )

                time.sleep(0.5)

            except Exception as exc:  # @quality-exception exception-transparency: idle-power polling crosses runtime policy, sensor, backend, and tray callback boundaries and must remain non-fatal for tray survivability
                now = time.monotonic()
                if now - loop_state.last_error_at > 30.0:
                    loop_state.last_error_at = now
                    _log_tray_exception(tray, "Idle power polling error: %s", exc)

    threading.Thread(target=poll_idle_power, daemon=True).start()


__all__ = [
    "start_idle_power_polling",
    "_compute_idle_action",
]
