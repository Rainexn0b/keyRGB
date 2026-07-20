from __future__ import annotations

import threading
import time

from src.core.utils.exceptions import is_device_disconnected
from src.tray.idle_power_state import (
    dim_temp_target_brightness,
    is_dim_temp_active,
    read_forced_off_flags,
)
from src.tray.pollers.hardware._decisions import (
    coerce_poll_int as _coerce_poll_int,
    normalize_brightness_to_config_scale as _normalize_brightness_to_config_scale,
)
from src.tray.pollers.hardware import _recovery as _recovery
from src.tray.protocols import IdlePowerTrayProtocol

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
_run_recoverable_hardware_poll_boundary = _recovery._run_recoverable_hardware_poll_boundary

# Test/monkeypatch compatibility: private recovery helpers were historically
# imported from this module. Prefer ``src.tray.pollers.hardware._recovery``.
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
                return current_brightness, False
            tray.is_off = True
        else:
            # Do not persist hardware-polled brightness into config.json.
            # Some backends report a different scale (e.g. 0..10), which would
            # overwrite the user's tray selection and leave no brightness radio
            # item selected after restart.
            if last_brightness == 0:
                if not (user_forced_off or power_forced_off or idle_forced_off):
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

    if (
        current_brightness == 0
        and last_brightness == 0
        and not bool(current_off)
        and _recover_stable_zero_brightness_best_effort(tray, current_brightness=current_brightness)
    ):
        return current_brightness, False

    return current_brightness, current_off


def _poll_hardware_once(
    tray: IdlePowerTrayProtocol,
    *,
    last_brightness,
    last_off_state,
) -> tuple[int, bool]:
    with tray.engine.kb_lock:
        current_brightness = tray.engine.kb.get_brightness()
        current_off = tray.engine.kb.is_off()

    return _apply_polled_hardware_state(
        tray,
        raw_brightness=int(current_brightness),
        current_brightness=int(current_brightness),
        current_off=bool(current_off),
        last_brightness=last_brightness,
        last_off_state=last_off_state,
    )


# ---------------------------------------------------------------------------
# Device-disconnect handling and polling-loop entrypoint
# ---------------------------------------------------------------------------


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


def start_hardware_polling(tray: IdlePowerTrayProtocol) -> None:
    """Poll keyboard hardware state to detect physical button changes."""

    def poll_hardware():
        last_brightness = None
        last_off_state = None
        last_error_at = 0.0

        def _recover_polling_error(exc: Exception) -> None:
            nonlocal last_error_at
            last_error_at = _handle_hardware_polling_exception(
                tray,
                exc,
                last_error_at=last_error_at,
            )

        while True:
            polled_state = _run_recoverable_hardware_poll_boundary(
                lambda: _poll_hardware_once(
                    tray,
                    last_brightness=last_brightness,
                    last_off_state=last_off_state,
                ),
                on_recoverable=_recover_polling_error,
            )
            if polled_state is not None:
                last_brightness, last_off_state = polled_state

            time.sleep(_hardware_poll_interval_s(tray, now=time.monotonic()))

    threading.Thread(target=poll_hardware, daemon=True).start()
