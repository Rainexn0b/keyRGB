from __future__ import annotations

from collections.abc import Callable
import threading
import time
from typing import TypeVar

from src.core.utils.exceptions import is_device_disconnected
from src.tray.protocols import IdlePowerTrayProtocol


_BRIGHTNESS_COERCION_ERRORS = (TypeError, ValueError, OverflowError)
_HARDWARE_POLL_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_HARDWARE_POLL_RECOVERY_EXCEPTIONS = (OSError, RuntimeError, ValueError)
_T = TypeVar("_T")


def _coerce_poll_int(value: object, *, default: int) -> int:
    try:
        return int(value)  # type: ignore[call-overload]
    except _BRIGHTNESS_COERCION_ERRORS:
        return int(default)


def _run_recoverable_hardware_poll_boundary(
    action: Callable[[], _T],
    *,
    on_recoverable: Callable[[Exception], None],
) -> _T | None:
    try:
        return action()
    except _HARDWARE_POLL_RUNTIME_EXCEPTIONS as exc:  # @quality-exception exception-transparency: hardware polling crosses runtime backend I/O and best-effort tray callback seams; recoverable runtime failures must stay non-fatal while unexpected defects still propagate
        on_recoverable(exc)
        return None


def _log_polled_hardware_event(tray_vars: dict[str, object], action: str, **fields: object) -> None:
    log_event = tray_vars.get("_log_event")
    if not callable(log_event):
        return

    _run_recoverable_hardware_poll_boundary(
        lambda: log_event("hardware", action, **fields),
        on_recoverable=lambda _exc: None,
    )


def _normalize_brightness_to_config_scale(brightness: int, *, expected: int | None = None) -> int:
    """Clamp brightness into KeyRGB's expected 0..50 range.

    Note: We intentionally do NOT attempt to infer or convert other brightness
    scales (like 0..10 or 0..100) here. That heuristic caused unwanted
    brightness changes.
    """

    try:
        b = int(brightness)
    except _BRIGHTNESS_COERCION_ERRORS:
        return 0

    return max(0, min(50, b))


def _refresh_ui_without_icon_animation(tray: IdlePowerTrayProtocol) -> None:
    try:
        tray._refresh_ui(animate_icon=False)
    except TypeError:
        tray._refresh_ui()


def _apply_polled_hardware_state(
    tray: IdlePowerTrayProtocol,
    *,
    raw_brightness: int | None = None,
    current_brightness: int,
    current_off: bool,
    last_brightness,
    last_off_state,
):
    tray_vars = vars(tray)

    # If we're temporarily forcing brightness due to screen dim sync, do not
    # persist that brightness back into config.json (it would become a user
    # setting). Still allow off/on transitions to be detected.
    dim_temp_active = bool(tray_vars.get("_dim_temp_active", False))
    dim_temp_target = tray_vars.get("_dim_temp_target_brightness")

    if raw_brightness is None:
        raw_brightness = current_brightness

    current_brightness = _normalize_brightness_to_config_scale(current_brightness)

    if current_brightness == 0:
        current_off = True

    if last_brightness is not None and current_brightness != last_brightness:
        _log_polled_hardware_event(
            tray_vars,
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

        if bool(tray_vars.get("_power_forced_off", False)) and current_brightness == 0:
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
                    not bool(tray_vars.get("_user_forced_off", False))
                    and not bool(tray_vars.get("_power_forced_off", False))
                    and not bool(tray_vars.get("_idle_forced_off", False))
                ):
                    tray.is_off = False

        _refresh_ui_without_icon_animation(tray)
        return current_brightness, current_off

    if last_off_state is not None and current_off != last_off_state:
        _log_polled_hardware_event(
            tray_vars,
            "off_state_change",
            old=bool(last_off_state),
            new=bool(current_off),
        )

        if bool(tray_vars.get("_power_forced_off", False)) and current_off:
            return current_brightness, current_off

        if current_off:
            tray.is_off = True
        else:
            # Avoid overriding explicit forced-off states.
            if (
                not bool(tray_vars.get("_user_forced_off", False))
                and not bool(tray_vars.get("_power_forced_off", False))
                and not bool(tray_vars.get("_idle_forced_off", False))
            ):
                tray.is_off = False
        _refresh_ui_without_icon_animation(tray)
        return current_brightness, current_off

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


def _mark_device_unavailable_best_effort(tray: IdlePowerTrayProtocol) -> None:
    try:
        tray.engine.mark_device_unavailable()
    except _HARDWARE_POLL_RECOVERY_EXCEPTIONS:
        return


def _log_hardware_polling_error_best_effort(tray: IdlePowerTrayProtocol, exc: Exception) -> None:
    try:
        tray._log_exception("Hardware polling error: %s", exc)
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

            time.sleep(2)

    threading.Thread(target=poll_hardware, daemon=True).start()
