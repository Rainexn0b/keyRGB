from __future__ import annotations

import threading
import time
from typing import Any, Optional

from src.core.effects.catalog import SW_EFFECTS_SET as SW_EFFECTS

from .idle_power_policy import IdleAction, compute_idle_action
from .idle_power_sensors import (
    get_session_id as _get_session_id_impl,
    read_dimmed_state as _read_dimmed_state_impl,
    read_screen_off_state_drm as _read_screen_off_state_drm_impl,
    run as _run_impl,
)


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
    """Read idle time via logind IdleHint, best-effort.

    Note: logind IdleHint timing is DE-controlled.
    """

    out = _run(
        [
            "loginctl",
            "show-session",
            session_id,
            "-p",
            "IdleHint",
            "-p",
            "IdleSinceHintMonotonic",
        ],
        timeout_s=1.0,
    )
    if out is None:
        return None

    idle_hint_s: Optional[str] = None
    idle_since_us_s: Optional[str] = None
    for raw_line in out.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k == "IdleHint":
            idle_hint_s = v
        elif k == "IdleSinceHintMonotonic":
            idle_since_us_s = v

    if idle_hint_s is None:
        return None

    s = idle_hint_s.strip().lower()
    if s in {"yes", "true", "1"}:
        is_idle = True
    elif s in {"no", "false", "0"}:
        is_idle = False
    else:
        return None

    if not is_idle:
        return 0.0

    try:
        idle_since_us = int((idle_since_us_s or "").strip())
        # logind returns microseconds from the monotonic clock.
        now_us = int(time.monotonic() * 1_000_000)
        idle_us = max(0, now_us - idle_since_us)
        return idle_us / 1_000_000.0
    except Exception:
        return None


def _restore_from_idle(tray: Any) -> None:
    tray.is_off = False
    tray._idle_forced_off = False

    # Best-effort: if brightness is 0, fall back to last brightness.
    try:
        if int(getattr(tray.config, "brightness", 0) or 0) == 0:
            tray.config.brightness = int(getattr(tray, "_last_brightness", 25) or 25)
    except Exception:
        pass

    try:
        tray._start_current_effect()
    except Exception:
        try:
            tray._log_exception("Failed to restore lighting after idle", Exception("restore failed"))
        except Exception:
            pass

    try:
        tray._refresh_ui()
    except Exception:
        pass


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
        debounce_polls = 2

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

                # Debounce dimmed/screen-off detection.
                if dimmed is True:
                    dimmed_true_streak += 1
                    dimmed_false_streak = 0
                elif dimmed is False:
                    dimmed_false_streak += 1
                    dimmed_true_streak = 0
                else:
                    dimmed_true_streak = 0
                    dimmed_false_streak = 0

                if bool(screen_off):
                    screen_off_true_streak += 1
                else:
                    screen_off_true_streak = 0

                if dimmed_true_streak >= debounce_polls:
                    dimmed = True
                elif dimmed_false_streak >= debounce_polls:
                    dimmed = False
                else:
                    dimmed = None

                screen_off = bool(screen_off_true_streak >= debounce_polls)

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
                )

                action_key = None
                try:
                    action_key = (
                        f"{action}|dimmed={dimmed}|screen_off={bool(screen_off)}|"
                        f"bri={int(brightness)}|dim_mode={str(dim_sync_mode)}|dim_tmp={int(dim_temp_brightness)}"
                    )
                except Exception:
                    action_key = str(action)

                is_real_action = bool(action) and str(action) != "none"
                if action_key is not None and action_key != last_action_key and is_real_action:
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

                if action == "turn_off":
                    tray._dim_temp_active = False
                    tray._dim_temp_target_brightness = None
                    try:
                        tray.engine.stop()
                    except Exception:
                        pass
                    try:
                        tray.engine.turn_off()
                    except Exception:
                        pass

                    tray.is_off = True
                    tray._idle_forced_off = True
                    try:
                        tray._refresh_ui()
                    except Exception:
                        pass

                elif action == "dim_to_temp":
                    # Do not fight explicit user/power forced off (already gated).
                    # Do not turn on lighting if it's currently off.
                    if not bool(getattr(tray, "is_off", False)):
                        tray._dim_temp_active = True
                        tray._dim_temp_target_brightness = int(dim_temp_brightness)
                        try:
                            effect = str(getattr(getattr(tray, "config", None), "effect", "none") or "none")
                            is_sw_effect = effect == "perkey" or effect in SW_EFFECTS
                            tray.engine.set_brightness(int(dim_temp_brightness), apply_to_hardware=not is_sw_effect)
                        except Exception:
                            pass

                elif action == "restore_brightness":
                    tray._dim_temp_active = False
                    tray._dim_temp_target_brightness = None
                    # Restore to current config brightness (it may have been changed while dimmed).
                    try:
                        target = int(getattr(tray.config, "brightness", 0) or 0)
                    except Exception:
                        target = 0
                    if target > 0 and not bool(getattr(tray, "is_off", False)):
                        try:
                            effect = str(getattr(getattr(tray, "config", None), "effect", "none") or "none")
                            is_sw_effect = effect == "perkey" or effect in SW_EFFECTS
                            tray.engine.set_brightness(int(target), apply_to_hardware=not is_sw_effect)
                        except Exception:
                            pass

                elif action == "restore":
                    # Only auto-restore if this wasn't an explicit user off.
                    if not bool(getattr(tray, "_user_forced_off", False)) and not bool(
                        getattr(tray, "_power_forced_off", False)
                    ):
                        tray._dim_temp_active = False
                        tray._dim_temp_target_brightness = None
                        _restore_from_idle(tray)

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
