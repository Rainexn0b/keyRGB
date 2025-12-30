from __future__ import annotations

import threading
import time


def _apply_polled_hardware_state(
    tray,
    *,
    current_brightness: int,
    current_off: bool,
    last_brightness,
    last_off_state,
):
    if current_brightness > 0:
        tray._last_brightness = current_brightness

    if current_brightness == 0:
        current_off = True

    if last_brightness is not None and current_brightness != last_brightness:
        if tray._power_forced_off and current_brightness == 0:
            return current_brightness, current_off

        # Never persist brightness=0 from hardware polling. Some backends can
        # transiently report 0 during mode transitions; persisting it resets the
        # user's configured brightness to 0 (and writes it to disk).
        if current_brightness == 0:
            tray.is_off = True
        else:
            tray.config.brightness = current_brightness
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
                    current_brightness=int(current_brightness),
                    current_off=bool(current_off),
                    last_brightness=last_brightness,
                    last_off_state=last_off_state,
                )

            except Exception as exc:
                # Device disconnects can happen at any time.
                errno = getattr(exc, "errno", None)
                if errno == 19 or "No such device" in str(exc):
                    try:
                        tray.engine.mark_device_unavailable()
                    except (OSError, RuntimeError, ValueError):
                        # Best-effort; continue polling.
                        continue

                now = time.monotonic()
                if now - last_error_at > 30:
                    last_error_at = now
                    try:
                        tray._log_exception("Hardware polling error: %s", exc)
                    except (OSError, RuntimeError, ValueError):
                        continue

            time.sleep(2)

    threading.Thread(target=poll_hardware, daemon=True).start()
