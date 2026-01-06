from __future__ import annotations

from typing import Optional, Tuple


def debounce_dim_and_screen_off(
    *,
    dimmed_raw: Optional[bool],
    screen_off_raw: bool,
    dimmed_true_streak: int,
    dimmed_false_streak: int,
    screen_off_true_streak: int,
    debounce_polls_dimmed_true: int,
    debounce_polls_dimmed_false: int,
    debounce_polls_screen_off_true: int,
) -> Tuple[Optional[bool], bool, int, int, int]:
    """Debounce dimmed/screen-off signals.

    Returns:
        (dimmed, screen_off, dimmed_true_streak, dimmed_false_streak, screen_off_true_streak)
    """

    if dimmed_raw is True:
        dimmed_true_streak += 1
        dimmed_false_streak = 0
    elif dimmed_raw is False:
        dimmed_false_streak += 1
        dimmed_true_streak = 0
    else:
        dimmed_true_streak = 0
        dimmed_false_streak = 0

    if bool(screen_off_raw):
        screen_off_true_streak += 1
    else:
        screen_off_true_streak = 0

    if dimmed_true_streak >= debounce_polls_dimmed_true:
        dimmed = True
    elif dimmed_false_streak >= debounce_polls_dimmed_false:
        dimmed = False
    else:
        dimmed = None

    screen_off = bool(screen_off_true_streak >= debounce_polls_screen_off_true)
    return (
        dimmed,
        screen_off,
        dimmed_true_streak,
        dimmed_false_streak,
        screen_off_true_streak,
    )


def build_idle_action_key(
    *,
    action: Optional[str],
    dimmed: Optional[bool],
    screen_off: bool,
    brightness: int,
    dim_sync_mode: str,
    dim_temp_brightness: int,
) -> str:
    try:
        return (
            f"{action}|dimmed={dimmed}|screen_off={bool(screen_off)}|"
            f"bri={int(brightness)}|dim_mode={str(dim_sync_mode)}|dim_tmp={int(dim_temp_brightness)}"
        )
    except Exception:
        return str(action)


def should_log_idle_action(*, action: Optional[str], action_key: str, last_action_key: Optional[str]) -> bool:
    is_real_action = bool(action) and str(action) != "none"
    if not is_real_action:
        return False
    if last_action_key is None:
        return True
    return bool(action_key != last_action_key)
