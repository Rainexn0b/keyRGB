from __future__ import annotations

import threading
import time


def _normalize_brightness_to_config_scale(brightness: int, *, expected: int | None = None) -> int:
    """Clamp brightness into KeyRGB's expected 0..50 range.

    Note: We intentionally do NOT attempt to infer or convert other brightness
    scales (like 0..10 or 0..100) here. That heuristic caused unwanted
    brightness changes.
    """

    try:
        b = int(brightness)
    except Exception:
        return 0

    return max(0, min(50, b))


def _apply_polled_hardware_state(
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
    dim_temp_active = bool(getattr(tray, "_dim_temp_active", False))
    dim_temp_target = getattr(tray, "_dim_temp_target_brightness", None)

    if raw_brightness is None:
        raw_brightness = current_brightness

    current_brightness = _normalize_brightness_to_config_scale(current_brightness)

    if current_brightness == 0:
        current_off = True

    if last_brightness is not None and current_brightness != last_brightness:
        log_event = getattr(tray, "_log_event", None)
        if callable(log_event):
            try:
                log_event(
                    "hardware",
                    "brightness_change",
                    raw=int(raw_brightness),
                    old=int(last_brightness),
                    new=int(current_brightness),
                    dim_temp_active=bool(dim_temp_active),
                    dim_temp_target=dim_temp_target,
                )
            except Exception:
                pass

        if dim_temp_active and dim_temp_target is not None:
            try:
                if int(current_brightness) == int(dim_temp_target):
                    # Update the tracked last_brightness so we don't repeatedly
                    # enter this branch; but do not write to config.
                    return int(current_brightness), bool(current_off)
            except Exception:
                pass

        if tray._power_forced_off and current_brightness == 0:
            return current_brightness, current_off

        # Never persist brightness=0 from hardware polling. Some backends can
        # transiently report 0 during mode transitions; persisting it resets the
        # user's configured brightness to 0 (and writes it to disk).
        if current_brightness == 0:
            tray.is_off = True
        else:
            # Do not persist hardware-polled brightness into config.json.
            # Some backends report a different scale (e.g. 0..10), which would
            # overwrite the user's tray selection and leave no brightness radio
            # item selected after restart.
            if last_brightness == 0:
                if (
                    not bool(getattr(tray, "_user_forced_off", False))
                    and not bool(getattr(tray, "_power_forced_off", False))
                    and not bool(getattr(tray, "_idle_forced_off", False))
                ):
                    tray.is_off = False

        tray._refresh_ui()
        return current_brightness, current_off

    if last_off_state is not None and current_off != last_off_state:
        log_event = getattr(tray, "_log_event", None)
        if callable(log_event):
            try:
                log_event(
                    "hardware",
                    "off_state_change",
                    old=bool(last_off_state),
                    new=bool(current_off),
                )
            except Exception:
                pass

        if tray._power_forced_off and current_off:
            return current_brightness, current_off

        if current_off:
            tray.is_off = True
        else:
            # Avoid overriding explicit forced-off states.
            if (
                not bool(getattr(tray, "_user_forced_off", False))
                and not bool(getattr(tray, "_power_forced_off", False))
                and not bool(getattr(tray, "_idle_forced_off", False))
            ):
                tray.is_off = False
        tray._refresh_ui()
        return current_brightness, current_off

    return current_brightness, current_off


def _handle_hardware_polling_exception(tray, exc: Exception, *, last_error_at: float) -> float:
    # Device disconnects can happen at any time.
    errno = getattr(exc, "errno", None)
    if errno == 19 or "No such device" in str(exc):
        try:
            tray.engine.mark_device_unavailable()
        except (OSError, RuntimeError, ValueError):
            # Best-effort; continue polling.
            pass
        return float(last_error_at)

    now = time.monotonic()
    if now - float(last_error_at) > 30:
        last_error_at = now
        try:
            tray._log_exception("Hardware polling error: %s", exc)
        except (OSError, RuntimeError, ValueError):
            pass
    return float(last_error_at)


def start_hardware_polling(tray) -> None:
    """Poll keyboard hardware state to detect physical button changes."""

    def poll_hardware():
        last_brightness = None
        last_off_state = None
        last_error_at = 0.0

        while True:
            try:
                with tray.engine.kb_lock:
                    current_brightness = tray.engine.kb.get_brightness()
                    current_off = tray.engine.kb.is_off()

                last_brightness, last_off_state = _apply_polled_hardware_state(
                    tray,
                    raw_brightness=int(current_brightness),
                    current_brightness=int(current_brightness),
                    current_off=bool(current_off),
                    last_brightness=last_brightness,
                    last_off_state=last_off_state,
                )

            except Exception as exc:
                last_error_at = _handle_hardware_polling_exception(
                    tray,
                    exc,
                    last_error_at=last_error_at,
                )

            time.sleep(2)

    threading.Thread(target=poll_hardware, daemon=True).start()
