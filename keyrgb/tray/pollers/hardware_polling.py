from __future__ import annotations

import threading
import time

from keyrgb.core.utils.exceptions import is_device_disconnected
from keyrgb.tray.controllers.runtime_coordination import (
    capture_transition_revision,
    run_tray_observation_if_current,
)
from keyrgb.tray.idle_power_state import (
    dim_temp_target_brightness,
    is_dim_temp_active,
    read_forced_off_flags,
    read_last_resume_at,
)
from keyrgb.tray.pollers.hardware import _controller_sleep, _recovery, _runtime_support
from keyrgb.tray.pollers.hardware._decisions import (
    REACTIVE_PULSE_POLL_DEFER_RETRY_S as _REACTIVE_PULSE_POLL_DEFER_RETRY_S,
    coerce_poll_int as _coerce_poll_int,
    normalize_brightness_to_config_scale as _normalize_brightness_to_config_scale,
    should_defer_poll_for_reactive_pulses as _should_defer_poll_for_reactive_pulses,
)
from keyrgb.tray.pollers.idle_power._constants import POST_RESUME_IDLE_ACTION_SUPPRESSION_S
from keyrgb.tray.protocols import IdlePowerTrayProtocol

from . import _lifecycle as polling_lifecycle

# Bind recovery helpers used by this module (and keep short local names).
_BRIGHTNESS_COERCION_ERRORS = _recovery._BRIGHTNESS_COERCION_ERRORS
_HARDWARE_POLL_RECOVERY_EXCEPTIONS = _recovery._HARDWARE_POLL_RECOVERY_EXCEPTIONS
_hardware_poll_interval_s = _recovery._hardware_poll_interval_s
_log_hardware_polling_error_best_effort = _recovery._log_hardware_polling_error_best_effort
_log_polled_hardware_event = _recovery._log_polled_hardware_event
_power_source_recovery_window_active = _recovery._power_source_recovery_window_active
_recover_recent_power_source_blank_best_effort = _recovery._recover_recent_power_source_blank_best_effort
_recover_stable_zero_brightness_best_effort = _recovery._recover_stable_zero_brightness_best_effort
_refresh_ui_without_icon_animation = _recovery._refresh_ui_without_icon_animation
_reset_stable_zero_recovery_attempt_count = _recovery.reset_stable_zero_recovery_attempt_count
_set_pending_zero_confirm_at = _recovery.set_pending_zero_confirm_at
_controller_sleep_off_active = _recovery.controller_sleep_off_active
_controller_sleep_respect_enabled = _recovery.controller_sleep_respect_enabled
_set_controller_sleep_off = _recovery.set_controller_sleep_off
_controller_sleep_resume_guard_active = _recovery.controller_sleep_resume_guard_active
_set_controller_sleep_resume_guard = _recovery.set_controller_sleep_resume_guard
_stop_engine_for_controller_sleep_best_effort = _controller_sleep.stop_engine_for_controller_sleep_best_effort
_clear_post_stop_controller_sleep_write_best_effort = _controller_sleep.clear_post_stop_write_best_effort
_restart_effect_after_controller_firmware_wake_best_effort = (
    _controller_sleep.restart_effect_after_firmware_wake_best_effort
)
_reactive_pulse_mix_or_zero = _runtime_support.reactive_pulse_mix_or_zero


_run_recoverable_hardware_poll_boundary = _recovery._run_recoverable_hardware_poll_boundary

# Compatibility facade for the pre-extraction recovery import and monkeypatch
# paths documented in v0.30.2.
_HARDWARE_POLL_RUNTIME_EXCEPTIONS = _recovery._HARDWARE_POLL_RUNTIME_EXCEPTIONS
_configured_brightness_intent = _recovery._configured_brightness_intent
_execute_blank_recovery = _recovery._execute_blank_recovery
_power_source_blank_recovery_eligible = _recovery._power_source_blank_recovery_eligible
_power_source_transition_at = _recovery._power_source_transition_at
_resolve_tray_callback = _recovery._resolve_tray_callback

# ---------------------------------------------------------------------------
# Polled-state application (brightness / off transitions)
# ---------------------------------------------------------------------------


def _apply_polled_hardware_state(
    tray: IdlePowerTrayProtocol,
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

    if raw_brightness is None:
        raw_brightness = current_brightness

    current_brightness = _normalize_brightness_to_config_scale(current_brightness)

    # Controller native sleep honored as an off state: polls keep reading 0
    # while the deck is deliberately dark; stay quiet until input, a power
    # restore, or a manual turn-on clears the flag.  A non-zero read means the
    # firmware woke itself (e.g. its first-keypress ramp) — adopt and resume
    # normal handling. A corrective explicit turn-off can retain a non-zero
    # brightness register while reporting is_off=True; that is still dark and
    # must not clear the honored-sleep flag.
    if _controller_sleep_off_active(tray):
        if current_brightness > 0 and not current_off and not (user_forced_off or power_forced_off or idle_forced_off):
            # The firmware's own first-keypress wake won the race with the
            # idle-power evdev loop. Claim the transition before restarting so
            # that loop will not run a second off->soft-on restore.
            _set_controller_sleep_off(tray, False)
            tray.is_off = False
            # A proven-awake read also clears any relight-intent guard so a later
            # genuine native sleep can latch again.
            if _controller_sleep_resume_guard_active(tray):
                _set_controller_sleep_resume_guard(tray, False)
            # A temporary screen-dim brightness is a brightness policy, not an
            # off owner: the firmware wake happened while that policy still owns
            # the deck, so restore at the dim target rather than relighting to
            # the full configured brightness and bypassing the temporary target.
            # The idle/evdev path restores full brightness once the screen wakes.
            wake_brightness_override = None
            if dim_temp_active and dim_temp_target is not None:
                wake_brightness_override = int(dim_temp_target)
            restored = _restart_effect_after_controller_firmware_wake_best_effort(
                tray,
                now=time.monotonic(),
                brightness_override=wake_brightness_override,
            )
            _log_polled_hardware_event(
                tray,
                "controller_sleep_firmware_wake",
                effect_restored=bool(restored),
            )
        else:
            # Forced-off policy wins over a stale/non-zero poll sampled during
            # the fade to off. In particular, a suspend transition can begin
            # while controller_sleep_off is still latched; treating an
            # in-flight fade sample as firmware wake would restart the effect
            # and relight the deck immediately before suspend.
            return current_brightness, True

    # A non-zero hardware read means the ITE transient-0 window has cleared
    # (see device.py:get_brightness docstring).  Reset the stable-zero
    # recovery circuit-breaker counter so the next genuine stuck-zero gets a
    # fresh quota of recovery attempts.
    if current_brightness > 0:
        _reset_stable_zero_recovery_attempt_count(tray)
        _set_pending_zero_confirm_at(tray, 0.0)
        # A non-zero read with the device reported as not-off proves the
        # firmware actually woke and the deck is lit. Clear the relight-intent
        # guard so a later genuine controller sleep can latch again.
        if not current_off and _controller_sleep_resume_guard_active(tray):
            _set_controller_sleep_resume_guard(tray, False)

    # Temp-dim is a "screen dimmed" brightness policy, not an off-state. Some
    # backends can briefly report 0 / off while dim-sync brightness is being
    # restored; ignore that transient so we do not bounce through a full
    # off -> on restore path.
    if dim_temp_active and dim_temp_target is not None:
        if current_brightness == 0:
            return current_brightness, False
        if bool(current_off):
            return current_brightness, False

    zero_brightness_without_off_state = current_brightness == 0 and not bool(current_off)
    if current_brightness == 0 and (bool(current_off) or user_forced_off or power_forced_off or idle_forced_off):
        current_off = True

    now = time.monotonic()
    last_resume_at = float(read_last_resume_at(tray) or 0.0)
    recently_restored = last_resume_at > 0.0 and (now - last_resume_at) < POST_RESUME_IDLE_ACTION_SUPPRESSION_S

    if last_brightness is not None and current_brightness != last_brightness:
        _log_polled_hardware_event(
            tray,
            "brightness_change",
            raw=_coerce_poll_int(raw_brightness, default=current_brightness),
            old=_coerce_poll_int(last_brightness, default=current_brightness),
            new=int(current_brightness),
            dim_temp_active=bool(dim_temp_active),
            dim_temp_target=dim_temp_target,
        )

        if dim_temp_active and dim_temp_target is not None:
            try:
                if int(current_brightness) == int(dim_temp_target):
                    # Update the tracked last_brightness so we don't repeatedly
                    # enter this branch; but do not write to config.
                    return int(current_brightness), bool(current_off)
            except _BRIGHTNESS_COERCION_ERRORS:
                pass

        if power_forced_off and current_brightness == 0:
            return current_brightness, current_off

        # Never persist brightness=0 from hardware polling. Some backends can
        # transiently report 0 during mode transitions; persisting it resets the
        # user's configured brightness to 0 (and writes it to disk).
        if current_brightness == 0:
            if _recover_recent_power_source_blank_best_effort(tray, current_brightness=current_brightness):
                return current_brightness, False
            if zero_brightness_without_off_state:
                # Fresh zero transition (likely ITE controller sleep): arm a
                # fast confirmation poll so the stable-zero recovery fires in
                # ~0.25 s instead of after a full 2 s poll cycle.  Skip when a
                # forced-off state intentionally wants the deck dark.
                if not (user_forced_off or power_forced_off or idle_forced_off):
                    _set_pending_zero_confirm_at(tray, now)
                # A zero right after restore is a transient glitch, not a
                # stable sleep.  Recover on the first read instead of waiting
                # for the confirmation poll — the 2 s cadence would otherwise
                # leave the deck dark for seconds.
                if (
                    recently_restored
                    and not (user_forced_off or power_forced_off or idle_forced_off)
                    and _configured_brightness_intent(tray) > 0
                    and _recover_stable_zero_brightness_best_effort(tray, current_brightness=current_brightness)
                ):
                    return current_brightness, False
                return current_brightness, False
            tray.is_off = True
        else:
            # Do not persist hardware-polled brightness into config.json.
            # Some backends report a different scale (e.g. 0..10), which would
            # overwrite the user's tray selection and leave no brightness radio
            # item selected after restart.
            if last_brightness == 0 and not (user_forced_off or power_forced_off or idle_forced_off):
                tray.is_off = False

        _refresh_ui_without_icon_animation(tray)
        return current_brightness, current_off

    if last_off_state is not None and current_off != last_off_state:
        _log_polled_hardware_event(
            tray,
            "off_state_change",
            old=bool(last_off_state),
            new=bool(current_off),
        )

        if power_forced_off and current_off:
            return current_brightness, current_off

        if current_off:
            if _recover_recent_power_source_blank_best_effort(tray, current_brightness=current_brightness):
                return current_brightness, False
            if _power_source_recovery_window_active(tray, now=time.monotonic()):
                return current_brightness, False
            tray.is_off = True
        else:
            # Avoid overriding explicit forced-off states.
            if not (user_forced_off or power_forced_off or idle_forced_off):
                tray.is_off = False
        _refresh_ui_without_icon_animation(tray)
        return current_brightness, current_off

    if last_brightness == 0 and _controller_sleep.classify_polled_state(
        tray,
        current_brightness=current_brightness,
        current_off=current_off,
    ):
        # The confirmation poll ran (fast or normal cadence); stop fast-polling
        # and let the recovery circuit breaker's cooldown govern any retries.
        _set_pending_zero_confirm_at(tray, 0.0)
        if (
            _controller_sleep_respect_enabled(tray)
            and not (user_forced_off or power_forced_off or idle_forced_off)
            and _configured_brightness_intent(tray) > 0
            and not recently_restored
            and not _controller_sleep_resume_guard_active(tray)
        ):
            # Opt-in: honor the controller's native keyboard-input sleep as a
            # valid off state instead of force re-lighting it. This contract
            # applies even when a software/reactive effect was mid-render:
            # recovering there defeats the explicit "let the controller sleep"
            # setting and produces the visible off→on flicker it is meant to
            # avoid.
            # The idle runtime restores on validated keyboard activity; a
            # firmware wake observed here is the fallback when hardware wins
            # that race. Power restore and menu turn-on use their normal paths.
            #
            # Skip this stick-dark path for a short window after idle/power
            # restore: a post-restore firmware transient zero must not undo the
            # restore and leave the deck stuck until a manual tray toggle.
            # The relight-intent guard extends that protection past the fixed
            # timestamp window: the firmware may remain in native sleep (and
            # keep reporting zero) long after resume, so we must not re-latch
            # until a poll proves the deck is actually awake.
            _set_controller_sleep_off(tray, True, now=now)
            tray.is_off = True
            # Stop any residual effect thread and mark mode-off for the next
            # soft-on prime (enable_user_mode reassert).
            if _stop_engine_for_controller_sleep_best_effort(tray):
                _clear_post_stop_controller_sleep_write_best_effort(tray)
            _log_polled_hardware_event(tray, "controller_sleep_off")
            _refresh_ui_without_icon_animation(tray)
            return current_brightness, True
        # When the relight guard prevented controller-sleep latching above,
        # retain the normal stable-zero recovery attempt.  Static effects do
        # not have a render loop continuously reasserting brightness, so merely
        # keeping the logical state on would not necessarily wake the deck.
        if _recover_stable_zero_brightness_best_effort(tray, current_brightness=current_brightness):
            return current_brightness, False

    return current_brightness, current_off


# ---------------------------------------------------------------------------
# Device-disconnect handling and polling-loop entrypoint
# ---------------------------------------------------------------------------


def _apply_hardware_observation_if_current(
    tray: IdlePowerTrayProtocol,
    revision: int | None,
    *args,
    **kwargs,
) -> tuple[int, bool] | None:
    outcome = run_tray_observation_if_current(
        tray,
        revision,
        lambda: _apply_polled_hardware_state(*args, **kwargs),
    )
    return outcome.value if outcome.accepted else None


def _mark_device_unavailable_best_effort(tray: IdlePowerTrayProtocol) -> None:
    try:
        tray.engine.mark_device_unavailable()
    except _HARDWARE_POLL_RECOVERY_EXCEPTIONS:
        return


def _handle_hardware_polling_exception(tray: IdlePowerTrayProtocol, exc: Exception, *, last_error_at: float) -> float:
    # Device disconnects can happen at any time.
    if is_device_disconnected(exc):
        _mark_device_unavailable_best_effort(tray)
        return float(last_error_at)

    now = time.monotonic()
    if now - float(last_error_at) > 30:
        last_error_at = now
        _log_hardware_polling_error_best_effort(tray, exc)
    return float(last_error_at)


def start_hardware_polling(tray: IdlePowerTrayProtocol) -> threading.Thread:
    """Poll keyboard hardware state to detect physical button changes."""

    def poll_hardware():
        last_brightness = None
        last_off_state = None
        last_error_at = 0.0
        last_real_poll_at = time.monotonic()
        poll_revision: int | None = None

        def _recover_polling_error(exc: Exception) -> None:
            nonlocal last_error_at
            outcome = run_tray_observation_if_current(
                tray,
                poll_revision,
                lambda: _handle_hardware_polling_exception(
                    tray,
                    exc,
                    last_error_at=last_error_at,
                ),
            )
            if outcome.accepted and outcome.value is not None:
                last_error_at = outcome.value

        while not polling_lifecycle.shutdown_requested(tray):
            # While reactive pulses are mid-flight, the poll's synchronous USB
            # reads would stall the render thread (visible ripple hitch). Defer
            # on a short retry cadence, bounded by a staleness cap so hardware
            # state detection cannot starve during continuous typing.
            if _should_defer_poll_for_reactive_pulses(
                reactive_pulse_mix=_reactive_pulse_mix_or_zero(tray),
                now=time.monotonic(),
                last_real_poll_at=last_real_poll_at,
            ):
                if polling_lifecycle.wait_for_shutdown(
                    tray,
                    _REACTIVE_PULSE_POLL_DEFER_RETRY_S,
                    sleep_fn=time.sleep,
                ):
                    return
                continue

            poll_revision = capture_transition_revision(tray)

            def apply_current_observation(*args, revision=poll_revision, **kwargs):
                return _apply_hardware_observation_if_current(
                    tray,
                    revision,
                    *args,
                    **kwargs,
                )

            polled_state = _run_recoverable_hardware_poll_boundary(
                lambda lb=last_brightness, lo=last_off_state: _runtime_support.poll_hardware_once(
                    tray,
                    last_brightness=lb,
                    last_off_state=lo,
                    apply_polled_state_fn=apply_current_observation,
                ),
                on_recoverable=_recover_polling_error,
            )
            last_real_poll_at = time.monotonic()
            if polled_state is not None:
                last_brightness, last_off_state = polled_state

            if polling_lifecycle.wait_for_shutdown(
                tray,
                _hardware_poll_interval_s(tray, now=time.monotonic()),
                sleep_fn=time.sleep,
            ):
                return

    thread = threading.Thread(target=poll_hardware, daemon=True)
    thread.start()
    return thread
