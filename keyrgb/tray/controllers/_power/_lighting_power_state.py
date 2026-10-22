from __future__ import annotations

import time
from collections.abc import Callable

from keyrgb.core.lighting_result import LightingResult
from keyrgb.tray._power_restore_policy import normalize_lighting_power_restore_policy_state
from keyrgb.tray.idle_power_state import (
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


def turn_off_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    software_effect_target_routes_aux_devices: Callable[[LightingTrayProtocol], bool],
    turn_off_secondary_software_targets: Callable[[LightingTrayProtocol], None],
    turn_off_secondary_profile_areas: Callable[[LightingTrayProtocol], None] | None = None,
) -> LightingResult:
    # Late import to avoid cycles: deck_pipeline is the commit owner.
    from keyrgb.tray.deck_pipeline import commit_lighting_power_intent
    from keyrgb.tray.deck_state import SleepWakeIntentKind

    def _leaf() -> None:
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

    return commit_lighting_power_intent(tray, SleepWakeIntentKind.MANUAL_OFF, _leaf)


def turn_on_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    start_current_effect: Callable[..., object],
) -> LightingResult:
    from keyrgb.tray.deck_pipeline import commit_lighting_power_intent
    from keyrgb.tray.deck_state import SleepWakeIntentKind

    fade_duration_s = idle_fade_duration_s(tray.config)

    def _leaf() -> bool:
        try_log_event(tray, "menu", "turn_on")
        # Same post-resume stamp as idle/power restore: a firmware transient zero
        # right after soft-on must not re-enter controller_sleep_off and stick the
        # deck dark until another manual toggle.
        _set_last_resume_at(tray, time.monotonic())
        _set_user_forced_off(tray, False)
        _set_idle_forced_off(tray, False)
        # Manual On supersedes a stranded suspend/lid-off owner too. Leaving
        # this latch set lights the deck but keeps source/profile polling paused.
        _set_power_forced_off(tray, False)
        # A manual turn-on is an explicit relight intent: keep the deck from being
        # re-latched into native sleep by a firmware zero read until hardware proves
        # it is actually awake.
        _set_controller_sleep_resume_guard(tray, True)
        _set_controller_sleep_off(tray, False)
        tray.is_off = False

        if tray.config.brightness == 0:
            tray.config.brightness = read_last_brightness(tray, default=25)

        started = start_current_effect(
            tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in=True,
            fade_in_duration_s=fade_duration_s,
        )

        tray._refresh_ui()
        return started is not False

    return commit_lighting_power_intent(
        tray,
        SleepWakeIntentKind.MANUAL_ON,
        _leaf,
        fade_in_duration_s=fade_duration_s,
    )


def power_turn_off_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    software_effect_target_routes_aux_devices: Callable[[LightingTrayProtocol], bool],
    turn_off_secondary_software_targets: Callable[[LightingTrayProtocol], None],
    turn_off_secondary_profile_areas: Callable[[LightingTrayProtocol], None] | None = None,
) -> LightingResult:
    from keyrgb.tray.deck_pipeline import commit_lighting_power_intent
    from keyrgb.tray.deck_state import SleepWakeIntentKind

    def _leaf() -> None:
        try_log_event(tray, "power", "turn_off")
        _set_power_forced_off(tray, True)
        _set_idle_forced_off(tray, False)
        _set_controller_sleep_resume_guard(tray, False)
        tray.is_off = True
        # PrepareForSleep has a finite shutdown budget. Commit off immediately;
        # also avoids flattening a natively sleeping deck back into user mode.
        tray.engine.turn_off()
        if software_effect_target_routes_aux_devices(tray):
            turn_off_secondary_software_targets(tray)
        if turn_off_secondary_profile_areas is not None:
            turn_off_secondary_profile_areas(tray)
        tray._refresh_ui(refresh_menu=False)

    return commit_lighting_power_intent(tray, SleepWakeIntentKind.POWER_OFF, _leaf)


def power_restore_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    safe_int_attr_fn: Callable[..., int],
    safe_str_attr_fn: Callable[..., str],
    is_software_effect_fn: Callable[[str], bool],
    is_reactive_effect_fn: Callable[[str], bool],
    start_current_effect: Callable[..., object],
) -> LightingResult:
    from keyrgb.tray.deck_pipeline import commit_lighting_power_intent
    from keyrgb.tray.deck_state import SleepWakeIntentKind

    fade_duration_s = idle_fade_duration_s(tray.config)

    def _leaf() -> bool | None:
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
            return None

        if policy_state.guard_state.idle_forced_off is True:
            _set_controller_sleep_resume_guard(tray, False)
            return None

        if policy_state.should_log_power_restore:
            try_log_event(tray, "power", "restore")

        if not policy_state.should_restore:
            # The policy decided not to relight (e.g. board stays dark). No relight
            # intent, so clear any stale guard.
            _set_controller_sleep_off(tray, False)
            _set_controller_sleep_resume_guard(tray, False)
            tray.is_off = True
            return None

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
        started = start_current_effect(
            tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in=True,
            fade_in_duration_s=fade_duration_s,
        )
        tray._refresh_ui(refresh_menu=False)
        return started is not False

    return commit_lighting_power_intent(
        tray,
        SleepWakeIntentKind.POWER_RESUME,
        _leaf,
        fade_in_duration_s=fade_duration_s,
    )
