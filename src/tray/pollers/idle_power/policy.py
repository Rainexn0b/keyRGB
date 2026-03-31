from __future__ import annotations

from typing import Literal, Optional


IdleAction = Optional[Literal["turn_off", "restore", "dim_to_temp", "restore_brightness"]]


def compute_idle_action(
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
    if now > 0 and last_resume_at > 0:
        if (now - last_resume_at) < 3.0:
            return None

    if not power_management_enabled:
        return None

    if not screen_dim_sync_enabled:
        if dimmed is None:
            if is_off and (not idle_forced_off):
                return "restore"
        return None

    if user_forced_off or power_forced_off:
        return None

    if int(brightness) <= 0:
        return None

    dimmed_effective: Optional[bool] = True if bool(screen_off) else dimmed

    if dimmed_effective is None:
        if dim_temp_active:
            return None
        if is_off and (not idle_forced_off):
            return "restore"
        return None

    if dimmed_effective is True:
        mode = str(screen_dim_sync_mode or "off").strip().lower()
        if mode == "temp":
            if bool(screen_off):
                if not is_off:
                    return "turn_off"
                return None

            if bool(dim_temp_active):
                return None

            if not is_off:
                return "dim_to_temp"
            return None

        if not is_off:
            return "turn_off"
        return None

    if dimmed_effective is False:
        if dim_temp_active:
            return "restore_brightness"

        if is_off:
            return "restore"
        return None

    return None
