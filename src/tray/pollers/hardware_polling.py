from __future__ import annotations

from collections.abc import Callable
import threading
import time
from typing import TypeVar

from src.core.utils.exceptions import is_device_disconnected
from src.tray.idle_power_state import (
    any_forced_off,
    dim_temp_target_brightness,
    is_dim_temp_active,
    read_forced_off_flags,
)
from src.tray.pollers.hardware._decisions import (
    DEFAULT_HARDWARE_POLL_INTERVAL_S as _DEFAULT_HARDWARE_POLL_INTERVAL_S,
    FAST_HARDWARE_POLL_INTERVAL_S as _FAST_HARDWARE_POLL_INTERVAL_S,
    POWER_SOURCE_RECOVERY_COOLDOWN_S as _POWER_SOURCE_RECOVERY_COOLDOWN_S,
    POWER_SOURCE_RECOVERY_WINDOW_S as _POWER_SOURCE_RECOVERY_WINDOW_S,
    STABLE_ZERO_BRIGHTNESS_RECOVERY_COOLDOWN_S as _STABLE_ZERO_BRIGHTNESS_RECOVERY_COOLDOWN_S,
    coerce_poll_int as _coerce_poll_int,
    hardware_poll_interval_s as _pure_hardware_poll_interval_s,
    normalize_brightness_to_config_scale as _normalize_brightness_to_config_scale,
    power_source_recovery_window_active as _pure_power_source_recovery_window_active,
    should_attempt_power_source_blank_recovery as _should_attempt_power_source_blank_recovery,
    should_attempt_stable_zero_brightness_recovery as _should_attempt_stable_zero_brightness_recovery,
)
from src.tray.protocols import (
    IdlePowerTrayProtocol,
    clear_idle_power_state_field,
    read_idle_power_state_float_field,
    set_idle_power_state_field,
)


_BRIGHTNESS_COERCION_ERRORS = (TypeError, ValueError, OverflowError)
_HARDWARE_POLL_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_HARDWARE_POLL_RECOVERY_EXCEPTIONS = (OSError, RuntimeError, ValueError)
_T = TypeVar("_T")


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


def _log_polled_hardware_event(tray: IdlePowerTrayProtocol, action: str, **fields: object) -> None:
    log_event = _resolve_tray_callback(tray, "_log_event")
    if not callable(log_event):
        return

    _run_recoverable_hardware_poll_boundary(
        lambda: log_event("hardware", action, **fields),
        on_recoverable=lambda _exc: None,
    )


def _refresh_ui_without_icon_animation(tray: IdlePowerTrayProtocol) -> None:
    try:
        tray._refresh_ui(animate_icon=False)
    except TypeError:
        tray._refresh_ui()


def _resolve_tray_callback(tray: object, name: str):
    instance_callback = vars(tray).get(name)
    if callable(instance_callback):
        return instance_callback

    class_callback = getattr(type(tray), name, None)
    if not callable(class_callback):
        return None

    return lambda *args, **kwargs: class_callback(tray, *args, **kwargs)


def _power_source_transition_at(tray: IdlePowerTrayProtocol) -> float:
    return read_idle_power_state_float_field(
        tray,
        attr_name="_last_power_source_transition_at",
        state_name="last_power_source_transition_at",
        default=0.0,
    )


def _power_source_recovery_window_active(tray: IdlePowerTrayProtocol, *, now: float) -> bool:
    return _pure_power_source_recovery_window_active(
        now=now,
        last_power_source_transition_at=_power_source_transition_at(tray),
        window_s=_POWER_SOURCE_RECOVERY_WINDOW_S,
    )


def _hardware_poll_interval_s(tray: IdlePowerTrayProtocol, *, now: float) -> float:
    return _pure_hardware_poll_interval_s(
        now=now,
        last_power_source_transition_at=_power_source_transition_at(tray),
        window_s=_POWER_SOURCE_RECOVERY_WINDOW_S,
        fast_s=_FAST_HARDWARE_POLL_INTERVAL_S,
        default_s=_DEFAULT_HARDWARE_POLL_INTERVAL_S,
    )


def _configured_brightness_intent(tray: IdlePowerTrayProtocol) -> int:
    try:
        return int(getattr(getattr(tray, "config", None), "brightness", 0))
    except _BRIGHTNESS_COERCION_ERRORS:
        return 0


def _power_source_blank_recovery_eligible(tray: IdlePowerTrayProtocol, *, now: float | None = None) -> bool:
    when = time.monotonic() if now is None else float(now)
    try:
        last_recovery_at = read_idle_power_state_float_field(
            tray,
            attr_name="_last_power_source_blank_recovery_at",
            state_name="last_power_source_blank_recovery_at",
            default=0.0,
        )
    except _BRIGHTNESS_COERCION_ERRORS:
        last_recovery_at = 0.0
    return _should_attempt_power_source_blank_recovery(
        now=when,
        last_power_source_transition_at=_power_source_transition_at(tray),
        last_recovery_at=float(last_recovery_at),
        any_forced_off=any_forced_off(tray),
        configured_brightness_intent=_configured_brightness_intent(tray),
        window_s=_POWER_SOURCE_RECOVERY_WINDOW_S,
        cooldown_s=_POWER_SOURCE_RECOVERY_COOLDOWN_S,
    )


def _execute_blank_recovery(
    tray: IdlePowerTrayProtocol,
    *,
    current_brightness: int,
    now: float,
    recovery_stamp_attr: str,
    recovery_stamp_state: str,
    log_action: str,
) -> bool:
    apply_transition = _resolve_tray_callback(tray, "_apply_power_source_perkey_profile_transition")
    start_current_effect = _resolve_tray_callback(tray, "_start_current_effect")

    try:
        set_idle_power_state_field(
            tray,
            attr_name="_hidden_perkey_restore_brightness_hint",
            state_name="hidden_perkey_restore_brightness_hint",
            value=int(current_brightness),
        )
        set_idle_power_state_field(
            tray,
            attr_name="_hidden_perkey_restore_device_off_hint",
            state_name="hidden_perkey_restore_device_off_hint",
            value=False,
        )
        handled = bool(apply_transition()) if callable(apply_transition) else False
        if not handled and callable(start_current_effect):
            start_current_effect()
            handled = True
    except _HARDWARE_POLL_RUNTIME_EXCEPTIONS as exc:
        _log_hardware_polling_error_best_effort(tray, exc)
        return False
    finally:
        clear_idle_power_state_field(
            tray,
            attr_name="_hidden_perkey_restore_brightness_hint",
            state_name="hidden_perkey_restore_brightness_hint",
            value=None,
        )
        clear_idle_power_state_field(
            tray,
            attr_name="_hidden_perkey_restore_device_off_hint",
            state_name="hidden_perkey_restore_device_off_hint",
            value=None,
        )

    if not handled:
        return False

    set_idle_power_state_field(
        tray,
        attr_name=recovery_stamp_attr,
        state_name=recovery_stamp_state,
        value=float(now),
    )
    tray.is_off = False
    _log_polled_hardware_event(
        tray,
        log_action,
        brightness=int(current_brightness),
    )
    _refresh_ui_without_icon_animation(tray)
    return True


def _recover_recent_power_source_blank_best_effort(
    tray: IdlePowerTrayProtocol,
    *,
    current_brightness: int,
) -> bool:
    now = time.monotonic()
    if not _power_source_blank_recovery_eligible(tray, now=now):
        return False
    return _execute_blank_recovery(
        tray,
        current_brightness=current_brightness,
        now=now,
        recovery_stamp_attr="_last_power_source_blank_recovery_at",
        recovery_stamp_state="last_power_source_blank_recovery_at",
        log_action="power_source_blank_recover",
    )


def _recover_stable_zero_brightness_best_effort(
    tray: IdlePowerTrayProtocol,
    *,
    current_brightness: int,
) -> bool:
    now = time.monotonic()
    last_recovery_at = read_idle_power_state_float_field(
        tray,
        attr_name="_last_hardware_blank_recovery_at",
        state_name="last_hardware_blank_recovery_at",
        default=0.0,
    )
    if not _should_attempt_stable_zero_brightness_recovery(
        current_brightness=int(current_brightness),
        dim_temp_active=is_dim_temp_active(tray),
        any_forced_off=any_forced_off(tray),
        configured_brightness_intent=_configured_brightness_intent(tray),
        now=now,
        last_recovery_at=float(last_recovery_at),
        cooldown_s=_STABLE_ZERO_BRIGHTNESS_RECOVERY_COOLDOWN_S,
    ):
        return False
    return _execute_blank_recovery(
        tray,
        current_brightness=current_brightness,
        now=now,
        recovery_stamp_attr="_last_hardware_blank_recovery_at",
        recovery_stamp_state="last_hardware_blank_recovery_at",
        log_action="stable_zero_brightness_recover",
    )


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

            time.sleep(_hardware_poll_interval_s(tray, now=time.monotonic()))

    threading.Thread(target=poll_hardware, daemon=True).start()
