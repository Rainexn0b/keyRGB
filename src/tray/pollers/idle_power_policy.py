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
    # Resume grace period: ignore screen_off/dimmed for 3s after wake.
    # On many systems, DRM/DPMS state takes time to update after resume, and
    # we'd otherwise immediately turn the keyboard off again (undoing restore).
    if now > 0 and last_resume_at > 0:
        if (now - last_resume_at) < 3.0:
            return None

    if not power_management_enabled:
        return None

    if not screen_dim_sync_enabled:
        # If the feature is disabled, do not force off on dim events.
        # Still allow restoring lighting if it is unexpectedly off.
        if dimmed is None:
            if is_off and (not idle_forced_off):
                return "restore"
        return None

    if user_forced_off or power_forced_off:
        return None

    if int(brightness) <= 0:
        return None

    # Some desktops turn the display off via DPMS without changing backlight
    # brightness. Treat "screen off" as an effective dimmed signal.
    dimmed_effective: Optional[bool] = True if bool(screen_off) else dimmed

    # When we can't determine dim state, be conservative: don't force off and
    # don't restore temp brightness, but still allow restoring lighting if it is
    # unexpectedly off.
    if dimmed_effective is None:
        if dim_temp_active:
            return None
        if is_off and (not idle_forced_off):
            return "restore"
        return None

    if dimmed_effective is True:
        mode = str(screen_dim_sync_mode or "off").strip().lower()
        if mode == "temp":
            # In temp mode, dimming normally reduces to a temporary brightness.
            # But if the display is actually off (backlight at 0), match it by
            # turning the keyboard off.
            if bool(screen_off):
                if not is_off:
                    return "turn_off"
                return None

            # Already in temporary-dim state: do not keep re-applying the action.
            # Re-applying can restart fades and cause visible flicker.
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

        # Not dimmed: restore if lighting is off (either we forced it off due to
        # dimming, or firmware/EC did something odd).
        if is_off:
            return "restore"
        return None

    return None
