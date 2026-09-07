from __future__ import annotations

import sys
import threading
import time

from keyrgb.core.utils.exceptions import is_device_disconnected
from keyrgb.tray.controllers.runtime_coordination import (
    capture_transition_revision,
    run_tray_observation_if_current,
)
from keyrgb.tray.pollers.hardware import _controller_sleep, _decisions, _recovery, _runtime_support
from keyrgb.tray.protocols import IdlePowerTrayProtocol

from . import _lifecycle as polling_lifecycle

# Bind recovery helpers used by this module (and keep short local names).
_BRIGHTNESS_COERCION_ERRORS = _recovery._BRIGHTNESS_COERCION_ERRORS
_HARDWARE_POLL_RECOVERY_EXCEPTIONS = _recovery._HARDWARE_POLL_RECOVERY_EXCEPTIONS
_hardware_poll_interval_s = _recovery._hardware_poll_interval_s
_log_hardware_polling_error_best_effort = _recovery._log_hardware_polling_error_best_effort
_log_polled_hardware_event = _recovery._log_polled_hardware_event
_power_source_recovery_window_active = _recovery._power_source_recovery_window_active
_recover_invalid_high_brightness_best_effort = _recovery._recover_invalid_high_brightness_best_effort
_recover_recent_power_source_blank_best_effort = _recovery._recover_recent_power_source_blank_best_effort
_recover_stable_zero_brightness_best_effort = _recovery._recover_stable_zero_brightness_best_effort
_refresh_ui_without_icon_animation = _recovery._refresh_ui_without_icon_animation
_reset_stable_zero_recovery_attempt_count = _recovery.reset_stable_zero_recovery_attempt_count
_reset_invalid_high_brightness_recovery_attempt_count = _recovery.reset_invalid_high_brightness_recovery_attempt_count
_set_pending_zero_confirm_at = _recovery.set_pending_zero_confirm_at
_controller_sleep_off_active = _recovery.controller_sleep_off_active
_controller_sleep_respect_enabled = _recovery.controller_sleep_respect_enabled
_controller_sleep_resume_guard_active = _recovery.controller_sleep_resume_guard_active
_set_controller_sleep_resume_guard = _recovery.set_controller_sleep_resume_guard
_stop_engine_for_controller_sleep_best_effort = _controller_sleep.stop_engine_for_controller_sleep_best_effort
_clear_post_stop_controller_sleep_write_best_effort = _controller_sleep.clear_post_stop_write_best_effort
_restart_effect_after_controller_firmware_wake_best_effort = (
    _controller_sleep.restart_effect_after_firmware_wake_best_effort
)
_reactive_pulse_mix_or_zero = _runtime_support.reactive_pulse_mix_or_zero
_REACTIVE_PULSE_POLL_DEFER_RETRY_S = _decisions.REACTIVE_PULSE_POLL_DEFER_RETRY_S
_coerce_poll_int = _decisions.coerce_poll_int
_normalize_brightness_to_config_scale = _decisions.normalize_brightness_to_config_scale
_should_defer_poll_for_reactive_pulses = _decisions.should_defer_poll_for_reactive_pulses

_run_recoverable_hardware_poll_boundary = _recovery._run_recoverable_hardware_poll_boundary

# Compatibility facade for the pre-extraction recovery import and monkeypatch
# paths documented in v0.30.2.
_HARDWARE_POLL_RUNTIME_EXCEPTIONS = _recovery._HARDWARE_POLL_RUNTIME_EXCEPTIONS
_configured_brightness_intent = _recovery._configured_brightness_intent
_execute_blank_recovery = _recovery._execute_blank_recovery
_power_source_blank_recovery_eligible = _recovery._power_source_blank_recovery_eligible
_power_source_transition_at = _recovery._power_source_transition_at
_resolve_tray_callback = _recovery._resolve_tray_callback

# Compatibility facade for the pre-extraction polled-state import and
# monkeypatch paths documented in v0.30.2.


def _commit_polled_intent(*args, **kwargs):
    from keyrgb.tray.pollers.hardware._polled_state import commit_polled_intent

    return commit_polled_intent(sys.modules[__name__], *args, **kwargs)


def _apply_polled_hardware_state(*args, **kwargs):
    from keyrgb.tray.pollers.hardware._polled_state import apply_polled_hardware_state

    return apply_polled_hardware_state(sys.modules[__name__], *args, **kwargs)


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


def _handle_hardware_polling_exception(
    tray: IdlePowerTrayProtocol,
    exc: Exception,
    *,
    last_error_at: float,
) -> float:
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

    def poll_hardware() -> None:
        last_brightness: object | None = None
        last_off_state: object | None = None
        last_error_at = 0.0
        last_real_poll_at = time.monotonic()
        last_real_controller_sleep_off = _controller_sleep_off_active(tray)
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
            # While reactive pulses are mid-flight, synchronous USB reads would
            # stall the render thread. Defer on a short retry cadence, except
            # after input clears controller-sleep ownership and the resulting
            # wake still needs its first accepted hardware verification.
            current_controller_sleep_off = _controller_sleep_off_active(tray)
            if _should_defer_poll_for_reactive_pulses(
                reactive_pulse_mix=_reactive_pulse_mix_or_zero(tray),
                now=time.monotonic(),
                last_real_poll_at=last_real_poll_at,
                controller_wake_verification_pending=(
                    last_real_controller_sleep_off and not current_controller_sleep_off
                ),
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

            def _poll_once(
                lb: object | None = last_brightness,
                lo: object | None = last_off_state,
            ) -> tuple[int, bool] | None:
                return _runtime_support.poll_hardware_once(
                    tray,
                    last_brightness=lb,
                    last_off_state=lo,
                    apply_polled_state_fn=apply_current_observation,
                )

            polled_state = _run_recoverable_hardware_poll_boundary(
                _poll_once,
                on_recoverable=_recover_polling_error,
            )
            last_real_poll_at = time.monotonic()
            if polled_state is not None:
                last_brightness, last_off_state = polled_state
                last_real_controller_sleep_off = _controller_sleep_off_active(tray)

            if polling_lifecycle.wait_for_shutdown(
                tray,
                _hardware_poll_interval_s(tray, now=time.monotonic()),
                sleep_fn=time.sleep,
            ):
                return

    thread = threading.Thread(target=poll_hardware, daemon=True)
    thread.start()
    return thread
