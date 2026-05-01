from __future__ import annotations

from typing import Literal, Optional

from ._constants import (
    POST_RESUME_IDLE_ACTION_SUPPRESSION_S,
    POST_TURN_OFF_RESTORE_SUPPRESSION_S,
)

IdleAction = Optional[Literal["turn_off", "restore", "dim_to_temp", "restore_brightness"]]

# see _constants.py


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
    last_idle_turn_off_at: float = 0.0,
    last_resume_at: float = 0.0,
    now: float = 0.0,
) -> IdleAction:
    if now > 0 and last_resume_at > 0:
        if (now - last_resume_at) < POST_RESUME_IDLE_ACTION_SUPPRESSION_S:
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
            if (not bool(screen_off)) and now > 0 and last_idle_turn_off_at > 0:
                if (now - last_idle_turn_off_at) < POST_TURN_OFF_RESTORE_SUPPRESSION_S:
                    return None
            return "restore"
        return None

    return None
