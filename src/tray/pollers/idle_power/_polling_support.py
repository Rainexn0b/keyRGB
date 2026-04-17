from __future__ import annotations

from collections.abc import Callable
import os
from typing import TYPE_CHECKING, Optional, cast

from src.core.utils.safe_attrs import safe_str_attr


if TYPE_CHECKING:
    from src.tray.protocols import IdlePowerTrayProtocol

    from ._runtime import IdlePollLoopState
else:
    IdlePowerTrayProtocol = object


_IDLE_POWER_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def tray_log_exception_or_none(tray: object) -> Callable[..., object] | None:
    try:
        log_exception = cast(IdlePowerTrayProtocol, tray)._log_exception
    except AttributeError:
        return None
    if not callable(log_exception):
        return None
    return cast(Callable[..., object], log_exception)


def tray_log_event_or_none(tray: object) -> Callable[..., object] | None:
    try:
        log_event = cast(IdlePowerTrayProtocol, tray)._log_event
    except AttributeError:
        return None
    if not callable(log_event):
        return None
    return cast(Callable[..., object], log_event)


def call_best_effort(
    func: Callable[..., object] | None,
    *args: object,
    on_recoverable: Callable[[Exception], None],
    **kwargs: object,
) -> bool:
    if not callable(func):
        return False

    try:
        func(*args, **kwargs)
        return True
    except _IDLE_POWER_RUNTIME_EXCEPTIONS as exc:  # @quality-exception exception-transparency: idle-power keeps recoverable runtime failures at one best-effort seam for tray diagnostics and the polling loop so logger/event survivability errors stay non-fatal while unexpected defects still propagate
        on_recoverable(exc)
        return False


def recover_idle_power_polling_error(
    tray: IdlePowerTrayProtocol,
    loop_state: IdlePollLoopState,
    exc: Exception,
    *,
    monotonic_fn: Callable[[], float],
    log_tray_exception_fn: Callable[[IdlePowerTrayProtocol, str, Exception], None],
) -> None:
    now = monotonic_fn()
    if now - loop_state.last_error_at <= 30.0:
        return

    loop_state.last_error_at = now
    log_tray_exception_fn(tray, "Idle power polling error: %s", exc)


def ensure_idle_state(tray: IdlePowerTrayProtocol) -> None:
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


def effective_screen_dim_sync_enabled(
    tray: IdlePowerTrayProtocol,
    requested_enabled: bool,
    *,
    try_log_event_fn: Callable[..., None],
) -> bool:
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
                tray._dim_sync_suppressed_logged = True
                try_log_event_fn(
                    tray,
                    "idle_power",
                    "dim_sync_suppressed",
                    backend=str(backend_name),
                    env_override="KEYRGB_ALLOW_DIM_SYNC_ASUSCTL",
                )
            return False

    return True


def poll_idle_power_loop(
    tray: IdlePowerTrayProtocol,
    *,
    idle_timeout_s: float,
    create_loop_state_fn: Callable[[], IdlePollLoopState],
    get_session_id_fn: Callable[[], Optional[str]],
    run_idle_power_iteration_fn: Callable[..., None],
    now_monotonic_fn: Callable[[], float],
    sleep_fn: Callable[[float], None],
    ensure_idle_state_fn: Callable[[IdlePowerTrayProtocol], None],
    read_dimmed_state_fn: Callable[[IdlePowerTrayProtocol], Optional[bool]],
    read_screen_off_state_drm_fn: Callable[[], Optional[bool]],
    debounce_dim_and_screen_off_fn: Callable[..., tuple[Optional[bool], bool, int, int, int]],
    read_logind_idle_seconds_fn: Callable[..., Optional[float]],
    effective_screen_dim_sync_enabled_fn: Callable[[IdlePowerTrayProtocol, bool], bool],
    compute_idle_action_fn: Callable[..., object],
    build_idle_action_key_fn: Callable[..., str],
    should_log_idle_action_fn: Callable[..., bool],
    apply_idle_action_fn: Callable[..., None],
    call_best_effort_fn: Callable[..., bool],
    recover_idle_power_polling_error_fn: Callable[[IdlePowerTrayProtocol, IdlePollLoopState, Exception], None],
) -> None:
    loop_state = create_loop_state_fn()
    session_id = get_session_id_fn()

    while True:
        call_best_effort_fn(
            run_idle_power_iteration_fn,
            tray,
            loop_state=loop_state,
            idle_timeout_s=float(idle_timeout_s),
            session_id=session_id,
            now_monotonic_fn=now_monotonic_fn,
            ensure_idle_state_fn=ensure_idle_state_fn,
            read_dimmed_state_fn=read_dimmed_state_fn,
            read_screen_off_state_drm_fn=read_screen_off_state_drm_fn,
            debounce_dim_and_screen_off_fn=debounce_dim_and_screen_off_fn,
            read_logind_idle_seconds_fn=read_logind_idle_seconds_fn,
            effective_screen_dim_sync_enabled_fn=effective_screen_dim_sync_enabled_fn,
            compute_idle_action_fn=compute_idle_action_fn,
            build_idle_action_key_fn=build_idle_action_key_fn,
            should_log_idle_action_fn=should_log_idle_action_fn,
            apply_idle_action_fn=apply_idle_action_fn,
            on_recoverable=lambda exc: recover_idle_power_polling_error_fn(tray, loop_state, exc),
        )
        sleep_fn(0.5)
