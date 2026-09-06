from __future__ import annotations

from types import ModuleType

from keyrgb.tray.deck_pipeline import commit_sleep_wake_intent
from keyrgb.tray.deck_state import SleepWakeGuards, SleepWakeIntent, SleepWakeIntentKind
from keyrgb.tray.idle_power_state import (
    dim_temp_target_brightness,
    is_dim_temp_active,
    read_forced_off_flags,
    read_last_resume_at,
)
from keyrgb.tray.pollers.hardware._decisions import (
    CONFIG_BRIGHTNESS_MAX,
    coerce_poll_int,
    normalize_brightness_to_config_scale,
)
from keyrgb.tray.pollers.idle_power._constants import POST_RESUME_IDLE_ACTION_SUPPRESSION_S


def commit_polled_intent(
    hp: ModuleType,
    tray,
    intent: SleepWakeIntent,
    *,
    now: float,
    current_brightness: int,
    dim_temp_target: int | None,
    recently_restored: bool,
    respect: bool,
    stable_zero_confirmed: bool = False,
) -> bool:
    """Commit a hardware-poll intent through the live polling facade."""

    return commit_sleep_wake_intent(
        tray,
        intent,
        now=now,
        respect=respect,
        guards=SleepWakeGuards(
            recently_restored=bool(recently_restored),
            resume_guard=hp._controller_sleep_resume_guard_active(tray),
            stable_zero_confirmed=bool(stable_zero_confirmed),
            dim_temp_still_active=is_dim_temp_active(tray),
        ),
        current_brightness=int(current_brightness),
        dim_temp_target=dim_temp_target,
        recover_stable_zero=hp._recover_stable_zero_brightness_best_effort,
        recover_power_source=hp._recover_recent_power_source_blank_best_effort,
        recover_invalid_brightness=hp._recover_invalid_high_brightness_best_effort,
        stop_engine=hp._stop_engine_for_controller_sleep_best_effort,
        clear_post_stop=hp._clear_post_stop_controller_sleep_write_best_effort,
        restart_firmware_wake=hp._restart_effect_after_controller_firmware_wake_best_effort,
    )


def apply_polled_hardware_state(
    hp: ModuleType,
    tray,
    *,
    raw_brightness: int | None = None,
    current_brightness: int,
    current_off: bool,
    last_brightness,
    last_off_state,
):
    # If we're temporarily forcing brightness due to screen dim sync, do not
    # persist that brightness back into config.json (it would become a user
    # setting). Still allow off/on transitions to be detected.
    dim_temp_active = is_dim_temp_active(tray)
    dim_temp_target = dim_temp_target_brightness(tray)
    user_forced_off, power_forced_off, idle_forced_off = read_forced_off_flags(tray)
    forced_off = bool(user_forced_off or power_forced_off or idle_forced_off)

    if raw_brightness is None:
        raw_brightness = current_brightness

    current_brightness = normalize_brightness_to_config_scale(current_brightness)
    raw_brightness_value = coerce_poll_int(raw_brightness, default=current_brightness)
    if raw_brightness_value <= CONFIG_BRIGHTNESS_MAX:
        hp._reset_invalid_high_brightness_recovery_attempt_count(tray)
    now = hp.time.monotonic()
    last_resume_at = float(read_last_resume_at(tray) or 0.0)
    recently_restored = last_resume_at > 0.0 and (now - last_resume_at) < POST_RESUME_IDLE_ACTION_SUPPRESSION_S
    respect = hp._controller_sleep_respect_enabled(tray)
    wake_dim_target = int(dim_temp_target) if dim_temp_active and dim_temp_target is not None else None

    # Controller native sleep honored as an off state: polls keep reading 0
    # while the deck is deliberately dark; stay quiet until input, a power
    # restore, or a manual turn-on clears the flag. A non-zero read means the
    # firmware woke itself; adopt and resume normal handling.
    if hp._controller_sleep_off_active(tray):
        if current_brightness > 0 and not current_off and not forced_off:
            if hp._commit_polled_intent(
                tray,
                SleepWakeIntent(SleepWakeIntentKind.FIRMWARE_WAKE),
                now=now,
                current_brightness=current_brightness,
                dim_temp_target=wake_dim_target,
                recently_restored=recently_restored,
                respect=respect,
            ):
                return current_brightness, False
            return current_brightness, True
        else:
            # Forced-off policy wins over a stale/non-zero poll sampled during
            # the fade to off.
            return current_brightness, True

    # A non-zero read means the transient-0 window has cleared. Reset the
    # stable-zero recovery circuit breaker and any pending confirmation.
    if current_brightness > 0:
        hp._reset_stable_zero_recovery_attempt_count(tray)
        hp._set_pending_zero_confirm_at(tray, 0.0)
        if not current_off and hp._controller_sleep_resume_guard_active(tray):
            hp._set_controller_sleep_resume_guard(tray, False)

    # Temp-dim is a brightness policy, not an off-state.
    if dim_temp_active and dim_temp_target is not None:
        if current_brightness == 0:
            return current_brightness, False
        if bool(current_off):
            return current_brightness, False

    zero_brightness_without_off_state = current_brightness == 0 and not bool(current_off)
    if current_brightness == 0 and (bool(current_off) or forced_off):
        current_off = True

    # Inspect raw values above the configured range even when normalization
    # leaves the tracked brightness unchanged, so render healing is dispatched.
    if (
        raw_brightness_value > CONFIG_BRIGHTNESS_MAX
        and not current_off
        and not forced_off
        and hp._configured_brightness_intent(tray) > 0
        and hp._commit_polled_intent(
            tray,
            SleepWakeIntent(SleepWakeIntentKind.AUTO_HEAL),
            now=now,
            current_brightness=raw_brightness_value,
            dim_temp_target=wake_dim_target,
            recently_restored=recently_restored,
            respect=respect,
        )
    ):
        return current_brightness, False

    if last_brightness is not None and current_brightness != last_brightness:
        hp._log_polled_hardware_event(
            tray,
            "brightness_change",
            raw=raw_brightness_value,
            old=coerce_poll_int(last_brightness, default=current_brightness),
            new=int(current_brightness),
            dim_temp_active=bool(dim_temp_active),
            dim_temp_target=dim_temp_target,
        )

        if dim_temp_active and dim_temp_target is not None:
            try:
                if int(current_brightness) == int(dim_temp_target):
                    return int(current_brightness), bool(current_off)
            except hp._BRIGHTNESS_COERCION_ERRORS:
                pass

        if power_forced_off and current_brightness == 0:
            return current_brightness, current_off

        # Never persist brightness=0 from hardware polling.
        if current_brightness == 0:
            if zero_brightness_without_off_state and not forced_off:
                hp._set_pending_zero_confirm_at(tray, now)
            if (
                not forced_off
                and hp._configured_brightness_intent(tray) > 0
                and hp._commit_polled_intent(
                    tray,
                    SleepWakeIntent(SleepWakeIntentKind.AUTO_HEAL),
                    now=now,
                    current_brightness=current_brightness,
                    dim_temp_target=wake_dim_target,
                    recently_restored=recently_restored,
                    respect=respect,
                    stable_zero_confirmed=False,
                )
            ):
                return current_brightness, False
            if zero_brightness_without_off_state:
                return current_brightness, False
            tray.is_off = True
        elif last_brightness == 0 and not forced_off:
            tray.is_off = False

        hp._refresh_ui_without_icon_animation(tray)
        return current_brightness, current_off

    if last_off_state is not None and current_off != last_off_state:
        hp._log_polled_hardware_event(
            tray,
            "off_state_change",
            old=bool(last_off_state),
            new=bool(current_off),
        )

        if power_forced_off and current_off:
            return current_brightness, current_off

        if (
            current_brightness == 0
            and not current_off
            and recently_restored
            and not forced_off
            and hp._configured_brightness_intent(tray) > 0
            and hp._commit_polled_intent(
                tray,
                SleepWakeIntent(SleepWakeIntentKind.AUTO_HEAL),
                now=now,
                current_brightness=current_brightness,
                dim_temp_target=wake_dim_target,
                recently_restored=True,
                respect=respect,
            )
        ):
            return current_brightness, False

        if current_off:
            if not forced_off and hp._commit_polled_intent(
                tray,
                SleepWakeIntent(SleepWakeIntentKind.AUTO_HEAL),
                now=now,
                current_brightness=current_brightness,
                dim_temp_target=wake_dim_target,
                recently_restored=recently_restored,
                respect=respect,
            ):
                return current_brightness, False
            if hp._power_source_recovery_window_active(tray, now=hp.time.monotonic()):
                return current_brightness, False
            tray.is_off = True
        elif not forced_off:
            tray.is_off = False
        hp._refresh_ui_without_icon_animation(tray)
        return current_brightness, current_off

    if last_brightness == 0 and hp._controller_sleep.classify_polled_state(
        tray,
        current_brightness=current_brightness,
        current_off=current_off,
    ):
        hp._set_pending_zero_confirm_at(tray, 0.0)
        can_own_sleep = (
            respect
            and not forced_off
            and hp._configured_brightness_intent(tray) > 0
            and not recently_restored
            and not hp._controller_sleep_resume_guard_active(tray)
        )
        if can_own_sleep and hp._commit_polled_intent(
            tray,
            SleepWakeIntent(SleepWakeIntentKind.CONTROLLER_SLEEP),
            now=now,
            current_brightness=current_brightness,
            dim_temp_target=wake_dim_target,
            recently_restored=False,
            respect=True,
            stable_zero_confirmed=True,
        ):
            return current_brightness, True
        if hp._commit_polled_intent(
            tray,
            SleepWakeIntent(SleepWakeIntentKind.AUTO_HEAL),
            now=now,
            current_brightness=current_brightness,
            dim_temp_target=wake_dim_target,
            recently_restored=recently_restored,
            respect=respect,
            stable_zero_confirmed=True,
        ):
            return current_brightness, False

    return current_brightness, current_off
