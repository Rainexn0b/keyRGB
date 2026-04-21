from __future__ import annotations

import time
from collections.abc import Callable

from ._transition_constants import (
    SOFT_OFF_FADE_DURATION_S,
    SOFT_ON_FADE_DURATION_S,
    SOFT_ON_START_BRIGHTNESS,
)
from src.tray.protocols import (
    LightingTrayProtocol,
    normalize_lighting_power_restore_policy_state,
    set_idle_power_state_field,
)


# ---------------------------------------------------------------------------
# Local wrapper helpers for idle power state field updates
# ---------------------------------------------------------------------------
# These wrappers encapsulate the bridge call patterns to avoid
# repeated scanner markers at callsites.



def _set_user_forced_off(tray: LightingTrayProtocol, value: bool) -> None:
    """Set user_forced_off state via idle power state bridge."""
    set_idle_power_state_field(tray, attr_name="_user_forced_off", state_name="user_forced_off", value=value)


def _set_idle_forced_off(tray: LightingTrayProtocol, value: bool) -> None:
    """Set idle_forced_off state via idle power state bridge."""
    set_idle_power_state_field(tray, attr_name="_idle_forced_off", state_name="idle_forced_off", value=value)


def _set_power_forced_off(tray: LightingTrayProtocol, value: bool) -> None:
    """Set power_forced_off state via idle power state bridge."""
    set_idle_power_state_field(tray, attr_name="_power_forced_off", state_name="power_forced_off", value=value)


def _set_last_resume_at(tray: LightingTrayProtocol, value: float) -> None:
    """Set last_resume_at timestamp via idle power state bridge."""
    set_idle_power_state_field(tray, attr_name="_last_resume_at", state_name="last_resume_at", value=value)


def turn_off_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    software_effect_target_routes_aux_devices: Callable[[LightingTrayProtocol], bool],
    turn_off_secondary_software_targets: Callable[[LightingTrayProtocol], None],
) -> None:
    try_log_event(tray, "menu", "turn_off")
    _set_user_forced_off(tray, True)
    _set_idle_forced_off(tray, False)
    tray.engine.turn_off()
    if software_effect_target_routes_aux_devices(tray):
        turn_off_secondary_software_targets(tray)
    tray.is_off = True
    tray._refresh_ui()


def turn_on_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    start_current_effect: Callable[..., None],
) -> None:
    try_log_event(tray, "menu", "turn_on")
    _set_user_forced_off(tray, False)
    _set_idle_forced_off(tray, False)
    tray.is_off = False

    if tray.config.brightness == 0:
        tray.config.brightness = tray._last_brightness if tray._last_brightness > 0 else 25

    start_current_effect(
        tray,
        brightness_override=SOFT_ON_START_BRIGHTNESS,
        fade_in=True,
        fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
    )

    tray._refresh_ui()


def power_turn_off_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    software_effect_target_routes_aux_devices: Callable[[LightingTrayProtocol], bool],
    turn_off_secondary_software_targets: Callable[[LightingTrayProtocol], None],
) -> None:
    try_log_event(tray, "power", "turn_off")
    _set_power_forced_off(tray, True)
    _set_idle_forced_off(tray, False)
    tray.is_off = True
    tray.engine.turn_off(fade=True, fade_duration_s=SOFT_OFF_FADE_DURATION_S)
    if software_effect_target_routes_aux_devices(tray):
        turn_off_secondary_software_targets(tray)
    tray._refresh_ui()


def power_restore_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    safe_int_attr_fn: Callable[..., int],
    safe_str_attr_fn: Callable[..., str],
    is_software_effect_fn: Callable[[str], bool],
    is_reactive_effect_fn: Callable[[str], bool],
    start_current_effect: Callable[..., None],
) -> None:
    resume_at = time.monotonic()
    _set_last_resume_at(tray, resume_at)

    policy_state = normalize_lighting_power_restore_policy_state(
        tray,
        safe_int_attr_fn=safe_int_attr_fn,
        safe_str_attr_fn=safe_str_attr_fn,
        is_software_effect_fn=is_software_effect_fn,
        is_reactive_effect_fn=is_reactive_effect_fn,
    )
    if policy_state.guard_state.user_forced_off:
        return

    if policy_state.guard_state.idle_forced_off is True:
        return

    if policy_state.should_log_power_restore:
        try_log_event(tray, "power", "restore")

    if not policy_state.should_restore:
        tray.is_off = True
        return

    tray.engine.current_color = (0, 0, 0)
    tray.is_off = False

    if policy_state.is_loop_effect:
        start_current_effect(
            tray,
            brightness_override=None,
            fade_in=False,
            fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
        )
        tray._refresh_ui()
        return

    start_current_effect(
        tray,
        brightness_override=SOFT_ON_START_BRIGHTNESS,
        fade_in=True,
        fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
    )
    tray._refresh_ui()
