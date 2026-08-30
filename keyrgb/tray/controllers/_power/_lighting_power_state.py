from __future__ import annotations

import time
from collections.abc import Callable

from keyrgb.tray._power_restore_policy import normalize_lighting_power_restore_policy_state
from keyrgb.tray.idle_power_state import (
    read_idle_power_state_bool_field,
    read_last_brightness,
    set_idle_power_state_field,
)
from keyrgb.tray.protocols import LightingTrayProtocol

from ._transition_constants import (
    SOFT_ON_START_BRIGHTNESS,
    idle_fade_duration_s,
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


def _set_controller_sleep_off(tray: LightingTrayProtocol, value: bool) -> None:
    """Set controller_sleep_off state via idle power state bridge."""
    set_idle_power_state_field(
        tray,
        attr_name="_controller_sleep_off",
        state_name="controller_sleep_off",
        value=value,
    )


def _set_controller_sleep_resume_guard(tray: LightingTrayProtocol, value: bool) -> None:
    """Arm/clear the relight-intent guard that suppresses controller-sleep latching."""
    set_idle_power_state_field(
        tray,
        attr_name="_controller_sleep_resume_guard",
        state_name="controller_sleep_resume_guard",
        value=bool(value),
    )


def _set_last_resume_at(tray: LightingTrayProtocol, value: float) -> None:
    """Set last_resume_at timestamp via idle power state bridge."""
    set_idle_power_state_field(tray, attr_name="_last_resume_at", state_name="last_resume_at", value=value)


def _read_controller_sleep_off(tray: LightingTrayProtocol) -> bool:
    """Read whether the controller has native-slept the deck dark.

    This is the firmware-input-timeout sleep, distinct from an explicit off:
    the physical deck is already dark but the engine's cached brightness is
    untouched. A fade-off would flatten and re-enter user mode at that cached
    brightness and briefly relight the deck before fading it back to off.
    """

    return read_idle_power_state_bool_field(
        tray,
        attr_name="_controller_sleep_off",
        state_name="controller_sleep_off",
        default=False,
    )


def turn_off_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    software_effect_target_routes_aux_devices: Callable[[LightingTrayProtocol], bool],
    turn_off_secondary_software_targets: Callable[[LightingTrayProtocol], None],
    turn_off_secondary_profile_areas: Callable[[LightingTrayProtocol], None] | None = None,
) -> None:
    try_log_event(tray, "menu", "turn_off")
    _set_user_forced_off(tray, True)
    _set_idle_forced_off(tray, False)
    _set_controller_sleep_resume_guard(tray, False)
    tray.engine.turn_off()
    if software_effect_target_routes_aux_devices(tray):
        turn_off_secondary_software_targets(tray)
    if turn_off_secondary_profile_areas is not None:
        turn_off_secondary_profile_areas(tray)
    tray.is_off = True
    tray._refresh_ui()


def turn_on_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    start_current_effect: Callable[..., object],
) -> None:
    try_log_event(tray, "menu", "turn_on")
    # Same post-resume stamp as idle/power restore: a firmware transient zero
    # right after soft-on must not re-enter controller_sleep_off and stick the
    # deck dark until another manual toggle.
    _set_last_resume_at(tray, time.monotonic())
    _set_user_forced_off(tray, False)
    _set_idle_forced_off(tray, False)
    # A manual turn-on is an explicit relight intent: keep the deck from being
    # re-latched into native sleep by a firmware zero read until hardware proves
    # it is actually awake.
    _set_controller_sleep_resume_guard(tray, True)
    _set_controller_sleep_off(tray, False)
    tray.is_off = False

    if tray.config.brightness == 0:
        tray.config.brightness = read_last_brightness(tray, default=25)

    start_current_effect(
        tray,
        brightness_override=SOFT_ON_START_BRIGHTNESS,
        fade_in=True,
        fade_in_duration_s=idle_fade_duration_s(tray.config),
    )

    tray._refresh_ui()


def power_turn_off_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    software_effect_target_routes_aux_devices: Callable[[LightingTrayProtocol], bool],
    turn_off_secondary_software_targets: Callable[[LightingTrayProtocol], None],
    turn_off_secondary_profile_areas: Callable[[LightingTrayProtocol], None] | None = None,
) -> None:
    try_log_event(tray, "power", "turn_off")
    _set_power_forced_off(tray, True)
    _set_idle_forced_off(tray, False)
    _set_controller_sleep_resume_guard(tray, False)
    tray.is_off = True
    # If the controller already native-slept the deck dark
    # (controller_sleep_off), an explicit off keeps it dark without a
    # wake-capable flatten/fade write: the engine's cached brightness is still
    # the last user value, so a fade would re-enter user mode at that brightness
    # and visibly relight the deck before turning it off. An ordinary on-state
    # suspend still fades to off as configured.
    if _read_controller_sleep_off(tray):
        tray.engine.turn_off()
    else:
        tray.engine.turn_off(fade=True, fade_duration_s=idle_fade_duration_s(tray.config))
    if software_effect_target_routes_aux_devices(tray):
        turn_off_secondary_software_targets(tray)
    if turn_off_secondary_profile_areas is not None:
        turn_off_secondary_profile_areas(tray)
    tray._refresh_ui(refresh_menu=False)


def power_restore_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    safe_int_attr_fn: Callable[..., int],
    safe_str_attr_fn: Callable[..., str],
    is_software_effect_fn: Callable[[str], bool],
    is_reactive_effect_fn: Callable[[str], bool],
    start_current_effect: Callable[..., object],
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
        # An explicit user-off wants the deck dark; clear any stale guard so a
        # later genuine controller sleep can latch again.
        _set_controller_sleep_resume_guard(tray, False)
        return

    if policy_state.guard_state.idle_forced_off is True:
        _set_controller_sleep_resume_guard(tray, False)
        return

    if policy_state.should_log_power_restore:
        try_log_event(tray, "power", "restore")

    if not policy_state.should_restore:
        # The policy decided not to relight (e.g. board stays dark). No relight
        # intent, so clear any stale guard.
        _set_controller_sleep_off(tray, False)
        _set_controller_sleep_resume_guard(tray, False)
        tray.is_off = True
        return

    # Arm before clearing the prior native-sleep latch and before crossing the
    # effect/backend boundary. A concurrent hardware poll must not re-latch the
    # same zero observation in either gap.
    _set_controller_sleep_resume_guard(tray, True)
    _set_controller_sleep_off(tray, False)
    tray.engine.current_color = (0, 0, 0)
    tray.is_off = False

    # Lid/suspend is a cold start even for loop/reactive effects. Restarting
    # in place at full brightness skips the enable_user_mode@1 prime and shows
    # up as a snap-on plus a later 10→0→10 blank-heal flicker.
    start_current_effect(
        tray,
        brightness_override=SOFT_ON_START_BRIGHTNESS,
        fade_in=True,
        fade_in_duration_s=idle_fade_duration_s(tray.config),
    )
    tray._refresh_ui(refresh_menu=False)
