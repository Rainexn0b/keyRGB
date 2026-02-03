from __future__ import annotations

import threading
import time
from typing import Any, Optional

from src.core.effects.catalog import REACTIVE_EFFECTS, SW_EFFECTS_SET as SW_EFFECTS
from .idle_power_policy import IdleAction, compute_idle_action
from .idle_power_sensors import (
    get_session_id as _get_session_id_impl,
    read_dimmed_state as _read_dimmed_state_impl,
    read_screen_off_state_drm as _read_screen_off_state_drm_impl,
    run as _run_impl,
)

from ._idle_power_actions import apply_idle_action as _apply_idle_action_impl
from ._idle_power_actions import restore_from_idle as _restore_from_idle_impl
from ._idle_power_logind import (
    read_logind_idle_seconds as _read_logind_idle_seconds_impl,
)
from ._idle_power_utils import build_idle_action_key as _build_idle_action_key_impl
from ._idle_power_utils import (
    debounce_dim_and_screen_off as _debounce_dim_and_screen_off_impl,
)
from ._idle_power_utils import should_log_idle_action as _should_log_idle_action_impl


REACTIVE_EFFECTS_SET = frozenset(REACTIVE_EFFECTS)


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


def _ensure_idle_state(tray: Any) -> None:
    if not hasattr(tray, "_idle_forced_off"):
        tray._idle_forced_off = False
    if not hasattr(tray, "_user_forced_off"):
        tray._user_forced_off = False
    if not hasattr(tray, "_power_forced_off"):
        tray._power_forced_off = False
    if not hasattr(tray, "_dim_backlight_baselines"):
        tray._dim_backlight_baselines = {}
    if not hasattr(tray, "_dim_temp_active"):
        tray._dim_temp_active = False
    if not hasattr(tray, "_dim_temp_target_brightness"):
        tray._dim_temp_target_brightness = None


def _read_dimmed_state(tray: Any) -> Optional[bool]:
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


def _restore_from_idle(tray: Any) -> None:
    return _restore_from_idle_impl(tray)


def _apply_idle_action(
    tray: Any,
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
    tray: Any,
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
        last_error_at = 0.0

        last_action_key: Optional[str] = None

        # Debounce dim/off signals to avoid rare transient false positives from
        # sysfs/DRM reads (which can briefly report 0/Off during modesets).
        dimmed_true_streak = 0
        dimmed_false_streak = 0
        screen_off_true_streak = 0
        # Asymmetric debounce: dim quickly, restore more slowly.
        #
        # Rationale: some systems report backlight brightness that can wobble
        # around the “dimmed” threshold while idle, which can cause repeated
        # dim↔restore brightness writes (visible as intermittent flicker on
        # USB-controlled devices).
        # NOTE: On some systems (notably KDE on certain AMD/NVIDIA setups),
        # backlight/DRM state can briefly jitter during normal operation,
        # which can cause visible keyboard "flashes" if we react too quickly.
        # These values trade a small delay for much better stability.
        debounce_polls_dimmed_true = 3
        debounce_polls_dimmed_false = 6
        debounce_polls_screen_off_true = 4

        session_id = _get_session_id()

        while True:
            try:
                _ensure_idle_state(tray)

                # Always reload config here as well (best-effort). While the tray
                # has a dedicated config polling thread, reloading in this loop
                # ensures settings changes (especially screen-dim sync mode) take
                # effect even if the config polling thread is delayed or not
                # running for some reason.
                try:
                    tray.config.reload()
                except Exception:
                    pass

                dimmed = _read_dimmed_state(tray)
                # Screen-off can be inferred from backlight reaching 0, or from
                # DRM DPMS state when the desktop powers the display down.
                screen_off_backlight = bool(getattr(tray, "_dim_screen_off", False))
                screen_off_drm = _read_screen_off_state_drm()
                screen_off = bool(screen_off_backlight) or bool(screen_off_drm)

                (
                    dimmed,
                    screen_off,
                    dimmed_true_streak,
                    dimmed_false_streak,
                    screen_off_true_streak,
                ) = _debounce_dim_and_screen_off(
                    dimmed_raw=dimmed,
                    screen_off_raw=bool(screen_off),
                    dimmed_true_streak=dimmed_true_streak,
                    dimmed_false_streak=dimmed_false_streak,
                    screen_off_true_streak=screen_off_true_streak,
                    debounce_polls_dimmed_true=debounce_polls_dimmed_true,
                    debounce_polls_dimmed_false=debounce_polls_dimmed_false,
                    debounce_polls_screen_off_true=debounce_polls_screen_off_true,
                )

                # Coarse fallback when we can't infer dim state from backlight.
                if dimmed is None and session_id:
                    idle_s = _read_logind_idle_seconds(session_id=session_id)
                    dimmed = None if idle_s is None else (float(idle_s) >= float(idle_timeout_s))

                try:
                    power_mgmt_enabled = bool(getattr(tray.config, "power_management_enabled", True))
                    brightness = int(getattr(tray.config, "brightness", 0) or 0)

                    dim_sync_enabled = bool(getattr(tray.config, "screen_dim_sync_enabled", True))
                    dim_sync_mode = str(getattr(tray.config, "screen_dim_sync_mode", "off") or "off")
                    dim_temp_brightness = int(getattr(tray.config, "screen_dim_temp_brightness", 5) or 5)
                except Exception:
                    power_mgmt_enabled = True
                    brightness = 0
                    dim_sync_enabled = True
                    dim_sync_mode = "off"
                    dim_temp_brightness = 5

                if dim_temp_brightness < 1:
                    dim_temp_brightness = 1
                if dim_temp_brightness > 50:
                    dim_temp_brightness = 50

                action = _compute_idle_action(
                    dimmed=dimmed,
                    screen_off=bool(screen_off),
                    idle_timeout_s=float(idle_timeout_s),
                    is_off=bool(getattr(tray, "is_off", False)),
                    idle_forced_off=bool(getattr(tray, "_idle_forced_off", False)),
                    dim_temp_active=bool(getattr(tray, "_dim_temp_active", False)),
                    power_management_enabled=bool(power_mgmt_enabled),
                    screen_dim_sync_enabled=bool(dim_sync_enabled),
                    screen_dim_sync_mode=str(dim_sync_mode),
                    screen_dim_temp_brightness=int(dim_temp_brightness),
                    brightness=int(brightness),
                    user_forced_off=bool(getattr(tray, "_user_forced_off", False)),
                    power_forced_off=bool(getattr(tray, "_power_forced_off", False)),
                    last_resume_at=float(getattr(tray, "_last_resume_at", 0.0)),
                    now=time.monotonic(),
                )

                action_key = _build_idle_action_key_impl(
                    action=action,
                    dimmed=dimmed,
                    screen_off=bool(screen_off),
                    brightness=int(brightness),
                    dim_sync_mode=str(dim_sync_mode),
                    dim_temp_brightness=int(dim_temp_brightness),
                )

                if _should_log_idle_action_impl(
                    action=action,
                    action_key=action_key,
                    last_action_key=last_action_key,
                ):
                    last_action_key = action_key
                    log_event = getattr(tray, "_log_event", None)
                    if callable(log_event):
                        try:
                            log_event(
                                "idle_power",
                                str(action),
                                dimmed=dimmed,
                                screen_off=bool(screen_off),
                                config_brightness=int(brightness),
                                dim_sync_enabled=bool(dim_sync_enabled),
                                dim_sync_mode=str(dim_sync_mode),
                                dim_temp_brightness=int(dim_temp_brightness),
                                is_off=bool(getattr(tray, "is_off", False)),
                                user_forced_off=bool(getattr(tray, "_user_forced_off", False)),
                                power_forced_off=bool(getattr(tray, "_power_forced_off", False)),
                                idle_forced_off=bool(getattr(tray, "_idle_forced_off", False)),
                                dim_temp_active=bool(getattr(tray, "_dim_temp_active", False)),
                            )
                        except Exception:
                            pass

                _apply_idle_action(tray, action=action, dim_temp_brightness=int(dim_temp_brightness))

                time.sleep(0.5)

            except Exception as exc:
                now = time.monotonic()
                if now - last_error_at > 30.0:
                    last_error_at = now
                    try:
                        tray._log_exception("Idle power polling error: %s", exc)
                    except Exception:
                        pass

    threading.Thread(target=poll_idle_power, daemon=True).start()


__all__ = [
    "start_idle_power_polling",
    "_compute_idle_action",
]
