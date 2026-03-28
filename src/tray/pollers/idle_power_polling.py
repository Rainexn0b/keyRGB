from __future__ import annotations

import os
import threading
import time
from typing import Optional

from src.core.effects.catalog import REACTIVE_EFFECTS, SW_EFFECTS_SET as SW_EFFECTS
from src.core.utils.safe_attrs import safe_str_attr
from src.tray.protocols import IdlePowerTrayProtocol

from ._idle_power_actions import apply_idle_action as _apply_idle_action_impl
from ._idle_power_actions import restore_from_idle as _restore_from_idle_impl
from ._idle_power_logind import read_logind_idle_seconds as _read_logind_idle_seconds_impl
from ._idle_power_runtime import IdlePollLoopState, run_idle_power_iteration
from ._idle_power_utils import build_idle_action_key as _build_idle_action_key_impl
from ._idle_power_utils import debounce_dim_and_screen_off as _debounce_dim_and_screen_off_impl
from ._idle_power_utils import should_log_idle_action as _should_log_idle_action_impl
from .idle_power_policy import IdleAction, compute_idle_action
from .idle_power_sensors import (
    get_session_id as _get_session_id_impl,
    read_dimmed_state as _read_dimmed_state_impl,
    read_screen_off_state_drm as _read_screen_off_state_drm_impl,
    run as _run_impl,
)


REACTIVE_EFFECTS_SET = frozenset(REACTIVE_EFFECTS)


def _effective_screen_dim_sync_enabled(tray: IdlePowerTrayProtocol, requested_enabled: bool) -> bool:
    if not requested_enabled:
        return False

    backend = getattr(tray, "backend", None)
    backend_name = safe_str_attr(backend, "name", default="") if backend is not None else ""

    # On ASUS systems, asusd/asusctl can independently manage keyboard
    # backlight on screen dim/off. Default to not fighting it.
    if backend_name.startswith("asusctl"):
        allow = os.environ.get("KEYRGB_ALLOW_DIM_SYNC_ASUSCTL", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not allow:
            if not getattr(tray, "_dim_sync_suppressed_logged", False):
                setattr(tray, "_dim_sync_suppressed_logged", True)
                log_event = getattr(tray, "_log_event", None)
                if callable(log_event):
                    try:
                        log_event(
                            "idle_power",
                            "dim_sync_suppressed",
                            backend=str(backend_name),
                            env_override="KEYRGB_ALLOW_DIM_SYNC_ASUSCTL",
                        )
                    except Exception:
                        pass
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
    missing = object()

    if getattr(tray, "_idle_forced_off", missing) is missing:
        tray._idle_forced_off = False
    if getattr(tray, "_user_forced_off", missing) is missing:
        tray._user_forced_off = False
    if getattr(tray, "_power_forced_off", missing) is missing:
        tray._power_forced_off = False
    if getattr(tray, "_dim_backlight_baselines", missing) is missing:
        tray._dim_backlight_baselines = {}
    if getattr(tray, "_dim_backlight_dimmed", missing) is missing:
        tray._dim_backlight_dimmed = {}
    if getattr(tray, "_dim_temp_active", missing) is missing:
        tray._dim_temp_active = False
    if getattr(tray, "_dim_temp_target_brightness", missing) is missing:
        tray._dim_temp_target_brightness = None
    if getattr(tray, "_dim_screen_off", missing) is missing:
        tray._dim_screen_off = False
    if getattr(tray, "_last_resume_at", missing) is missing:
        tray._last_resume_at = 0.0


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
    """Power-management: sync keyboard lighting with display dimming.

    Desired behavior:
    - When the desktop dims the display, KeyRGB turns the keyboard LEDs off.
    - When the display returns to normal brightness, KeyRGB restores lighting.

    Implementation notes:
    - Uses kernel backlight brightness (/sys/class/backlight) to infer "dimmed".
    - Falls back to systemd-logind idle hint as a coarse signal when backlight
      state can't be read.
    - Best-effort only; never crashes the tray.
    """

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

            except Exception as exc:
                now = time.monotonic()
                if now - loop_state.last_error_at > 30.0:
                    loop_state.last_error_at = now
                    try:
                        tray._log_exception("Idle power polling error: %s", exc)
                    except Exception:
                        pass

    threading.Thread(target=poll_idle_power, daemon=True).start()


__all__ = [
    "start_idle_power_polling",
    "_compute_idle_action",
]