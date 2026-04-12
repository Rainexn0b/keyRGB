from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from src.core.utils.safe_attrs import safe_bool_attr, safe_int_attr, safe_str_attr
from src.tray.protocols import IdlePowerTrayProtocol

from .policy import IdleAction


_IDLE_POWER_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


@dataclass
class IdlePollLoopState:
    last_error_at: float = 0.0
    last_action_key: str | None = None
    dimmed_true_streak: int = 0
    dimmed_false_streak: int = 0
    screen_off_true_streak: int = 0


def _log_idle_action_best_effort(
    tray: IdlePowerTrayProtocol,
    *,
    action: IdleAction,
    dimmed: Optional[bool],
    screen_off: bool,
    brightness: int,
    dim_sync_enabled: bool,
    dim_sync_mode: str,
    dim_temp_brightness: int,
) -> None:
    try:
        tray._log_event(
            "idle_power",
            str(action),
            dimmed=dimmed,
            screen_off=bool(screen_off),
            config_brightness=int(brightness),
            dim_sync_enabled=bool(dim_sync_enabled),
            dim_sync_mode=str(dim_sync_mode),
            dim_temp_brightness=int(dim_temp_brightness),
            is_off=bool(tray.is_off),
            user_forced_off=bool(tray._user_forced_off),
            power_forced_off=bool(tray._power_forced_off),
            idle_forced_off=bool(tray._idle_forced_off),
            dim_temp_active=bool(tray._dim_temp_active),
        )
    except _IDLE_POWER_RUNTIME_EXCEPTIONS:  # @quality-exception exception-transparency: idle action event logging crosses a runtime callback boundary and polling must stay non-fatal without recursive hot-path logging
        return


def _reload_idle_power_config_best_effort(tray: IdlePowerTrayProtocol) -> None:
    reload_config = getattr(tray.config, "reload", None)
    if not callable(reload_config):
        return

    try:
        reload_config()
    except _IDLE_POWER_RUNTIME_EXCEPTIONS:  # @quality-exception exception-transparency: per-iteration config reload is a runtime config/file boundary and idle power polling must keep running when refresh fails
        return


def run_idle_power_iteration(
    tray: IdlePowerTrayProtocol,
    *,
    loop_state: IdlePollLoopState,
    idle_timeout_s: float,
    session_id: str | None,
    now_monotonic_fn: Callable[[], float],
    ensure_idle_state_fn: Callable[[IdlePowerTrayProtocol], None],
    read_dimmed_state_fn: Callable[[IdlePowerTrayProtocol], Optional[bool]],
    read_screen_off_state_drm_fn: Callable[[], Optional[bool]],
    debounce_dim_and_screen_off_fn: Callable[..., tuple[Optional[bool], bool, int, int, int]],
    read_logind_idle_seconds_fn: Callable[..., Optional[float]],
    effective_screen_dim_sync_enabled_fn: Callable[[IdlePowerTrayProtocol, bool], bool],
    compute_idle_action_fn: Callable[..., IdleAction],
    build_idle_action_key_fn: Callable[..., str],
    should_log_idle_action_fn: Callable[..., bool],
    apply_idle_action_fn: Callable[..., None],
) -> None:
    ensure_idle_state_fn(tray)

    _reload_idle_power_config_best_effort(tray)

    dimmed = read_dimmed_state_fn(tray)
    screen_off = bool(tray._dim_screen_off) or bool(read_screen_off_state_drm_fn())

    (
        dimmed,
        screen_off,
        loop_state.dimmed_true_streak,
        loop_state.dimmed_false_streak,
        loop_state.screen_off_true_streak,
    ) = debounce_dim_and_screen_off_fn(
        dimmed_raw=dimmed,
        screen_off_raw=bool(screen_off),
        dimmed_true_streak=loop_state.dimmed_true_streak,
        dimmed_false_streak=loop_state.dimmed_false_streak,
        screen_off_true_streak=loop_state.screen_off_true_streak,
        debounce_polls_dimmed_true=3,
        debounce_polls_dimmed_false=6,
        debounce_polls_screen_off_true=4,
    )

    if dimmed is None and session_id:
        idle_s = read_logind_idle_seconds_fn(session_id=session_id)
        dimmed = None if idle_s is None else (float(idle_s) >= float(idle_timeout_s))

    power_mgmt_enabled = safe_bool_attr(tray.config, "power_management_enabled", default=True)
    brightness = safe_int_attr(tray.config, "brightness", default=0)

    dim_sync_enabled_requested = safe_bool_attr(tray.config, "screen_dim_sync_enabled", default=True)
    dim_sync_enabled = effective_screen_dim_sync_enabled_fn(tray, bool(dim_sync_enabled_requested))
    dim_sync_mode = safe_str_attr(tray.config, "screen_dim_sync_mode", default="off") or "off"
    dim_temp_brightness = safe_int_attr(tray.config, "screen_dim_temp_brightness", default=5, min_v=1, max_v=50)

    action = compute_idle_action_fn(
        dimmed=dimmed,
        screen_off=bool(screen_off),
        idle_timeout_s=float(idle_timeout_s),
        is_off=bool(tray.is_off),
        idle_forced_off=bool(tray._idle_forced_off),
        dim_temp_active=bool(tray._dim_temp_active),
        power_management_enabled=bool(power_mgmt_enabled),
        screen_dim_sync_enabled=bool(dim_sync_enabled),
        screen_dim_sync_mode=str(dim_sync_mode),
        screen_dim_temp_brightness=int(dim_temp_brightness),
        brightness=int(brightness),
        user_forced_off=bool(tray._user_forced_off),
        power_forced_off=bool(tray._power_forced_off),
        last_resume_at=float(tray._last_resume_at),
        now=now_monotonic_fn(),
    )

    action_key = build_idle_action_key_fn(
        action=action,
        dimmed=dimmed,
        screen_off=bool(screen_off),
        brightness=int(brightness),
        dim_sync_mode=str(dim_sync_mode),
        dim_temp_brightness=int(dim_temp_brightness),
    )

    if should_log_idle_action_fn(
        action=action,
        action_key=action_key,
        last_action_key=loop_state.last_action_key,
    ):
        loop_state.last_action_key = action_key
        _log_idle_action_best_effort(
            tray,
            action=action,
            dimmed=dimmed,
            screen_off=bool(screen_off),
            brightness=int(brightness),
            dim_sync_enabled=bool(dim_sync_enabled),
            dim_sync_mode=str(dim_sync_mode),
            dim_temp_brightness=int(dim_temp_brightness),
        )

    apply_idle_action_fn(tray, action=action, dim_temp_brightness=int(dim_temp_brightness))
