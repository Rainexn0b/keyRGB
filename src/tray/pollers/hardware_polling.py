from __future__ import annotations

from collections.abc import Callable
import os
import threading
import time
from typing import TypeVar

from src.core.utils.exceptions import is_device_disconnected
from src.tray.protocols import (
    IdlePowerTrayProtocol,
    clear_idle_power_state_field,
    read_idle_power_state_float_field,
    set_idle_power_state_field,
)


_BRIGHTNESS_COERCION_ERRORS = (TypeError, ValueError, OverflowError)
_HARDWARE_POLL_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_HARDWARE_POLL_RECOVERY_EXCEPTIONS = (OSError, RuntimeError, ValueError)
_POWER_SOURCE_RECOVERY_WINDOW_S = 6.0
_POWER_SOURCE_RECOVERY_COOLDOWN_S = 0.75
_STABLE_ZERO_BRIGHTNESS_RECOVERY_COOLDOWN_S = 5.0
_DEFAULT_HARDWARE_POLL_INTERVAL_S = 2.0
_FAST_HARDWARE_POLL_INTERVAL_S = 0.25
_T = TypeVar("_T")


def _env_flag_enabled(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _hardware_debug_logging_enabled() -> bool:
    return _env_flag_enabled("KEYRGB_DEBUG") or _env_flag_enabled("KEYRGB_DEBUG_BRIGHTNESS")


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


def _log_polled_hardware_event(tray: IdlePowerTrayProtocol, action: str, **fields: object) -> None:
    log_event = _resolve_tray_callback(tray, "_log_event")
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


def _resolve_tray_callback(tray: object, name: str):
    instance_callback = vars(tray).get(name)
    if callable(instance_callback):
        return instance_callback

    class_callback = getattr(type(tray), name, None)
    if not callable(class_callback):
        return None

    return lambda *args, **kwargs: class_callback(tray, *args, **kwargs)


def _power_source_recovery_window_active(tray: IdlePowerTrayProtocol, *, now: float) -> bool:
    changed_at = read_idle_power_state_float_field(
        tray,
        attr_name="_last_power_source_transition_at",
        state_name="last_power_source_transition_at",
        default=0.0,
    )
    if changed_at <= 0:
        return False

    return now - changed_at <= _POWER_SOURCE_RECOVERY_WINDOW_S


def _hardware_poll_interval_s(tray: IdlePowerTrayProtocol, *, now: float) -> float:
    if _power_source_recovery_window_active(tray, now=now):
        return _FAST_HARDWARE_POLL_INTERVAL_S
    return _DEFAULT_HARDWARE_POLL_INTERVAL_S


def _configured_brightness_intent(tray: IdlePowerTrayProtocol) -> int:
    try:
        return int(getattr(getattr(tray, "config", None), "brightness", 0))
    except _BRIGHTNESS_COERCION_ERRORS:
        return 0


def _recover_recent_power_source_blank_best_effort(
    tray: IdlePowerTrayProtocol,
    *,
    current_brightness: int,
) -> bool:
    tray_vars = vars(tray)
    now = time.monotonic()
    if not _power_source_recovery_window_active(tray, now=now):
        return False

    if bool(tray_vars.get("_user_forced_off", False)):
        return False
    if bool(tray_vars.get("_power_forced_off", False)):
        return False
    if bool(tray_vars.get("_idle_forced_off", False)):
        return False
    if _configured_brightness_intent(tray) <= 0:
        return False

    try:
        last_recovery_at = read_idle_power_state_float_field(
            tray,
            attr_name="_last_power_source_blank_recovery_at",
            state_name="last_power_source_blank_recovery_at",
            default=0.0,
        )
    except _BRIGHTNESS_COERCION_ERRORS:
        last_recovery_at = 0.0
    if now - last_recovery_at < _POWER_SOURCE_RECOVERY_COOLDOWN_S:
        return False

    apply_transition = _resolve_tray_callback(tray, "_apply_power_source_perkey_profile_transition")
    start_current_effect = _resolve_tray_callback(tray, "_start_current_effect")
    method = "none"

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
        if handled:
            method = "in_place_transition"
        if not handled and callable(start_current_effect):
            start_current_effect()
            handled = True
            method = "effect_restart"
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
        attr_name="_last_power_source_blank_recovery_at",
        state_name="last_power_source_blank_recovery_at",
        value=float(now),
    )
    tray.is_off = False
    _log_polled_hardware_event(
        tray,
        "power_source_blank_recover",
        brightness=int(current_brightness),
        method=str(method),
    )
    _refresh_ui_without_icon_animation(tray)
    return True


def _recover_stable_zero_brightness_best_effort(
    tray: IdlePowerTrayProtocol,
    *,
    current_brightness: int,
) -> bool:
    tray_vars = vars(tray)
    if int(current_brightness) != 0:
        return False
    if bool(tray_vars.get("_dim_temp_active", False)):
        return False
    if bool(tray_vars.get("_user_forced_off", False)):
        return False
    if bool(tray_vars.get("_power_forced_off", False)):
        return False
    if bool(tray_vars.get("_idle_forced_off", False)):
        return False
    if _configured_brightness_intent(tray) <= 0:
        return False

    now = time.monotonic()
    last_recovery_at = read_idle_power_state_float_field(
        tray,
        attr_name="_last_hardware_blank_recovery_at",
        state_name="last_hardware_blank_recovery_at",
        default=0.0,
    )
    if now - last_recovery_at < _STABLE_ZERO_BRIGHTNESS_RECOVERY_COOLDOWN_S:
        return False

    apply_transition = _resolve_tray_callback(tray, "_apply_power_source_perkey_profile_transition")
    start_current_effect = _resolve_tray_callback(tray, "_start_current_effect")
    method = "none"

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
        if handled:
            method = "in_place_transition"
        if not handled and callable(start_current_effect):
            start_current_effect()
            handled = True
            method = "effect_restart"
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
        attr_name="_last_hardware_blank_recovery_at",
        state_name="last_hardware_blank_recovery_at",
        value=float(now),
    )
    tray.is_off = False
    _log_polled_hardware_event(
        tray,
        "stable_zero_brightness_recover",
        brightness=int(current_brightness),
        method=str(method),
    )
    _refresh_ui_without_icon_animation(tray)
    return True


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
    if current_brightness == 0 and (
        bool(current_off)
        or bool(tray_vars.get("_power_forced_off", False))
        or bool(tray_vars.get("_user_forced_off", False))
        or bool(tray_vars.get("_idle_forced_off", False))
    ):
        current_off = True

    if last_brightness is not None and current_brightness != last_brightness:
        debug_fields: dict[str, object] = {}
        if _hardware_debug_logging_enabled():
            debug_fields = {
                "config_brightness": int(_configured_brightness_intent(tray)),
                "idle_forced_off": bool(tray_vars.get("_idle_forced_off", False)),
                "power_forced_off": bool(tray_vars.get("_power_forced_off", False)),
                "power_source_recovery_window": bool(
                    _power_source_recovery_window_active(tray, now=time.monotonic())
                ),
                "user_forced_off": bool(tray_vars.get("_user_forced_off", False)),
                "zero_without_off": bool(zero_brightness_without_off_state),
            }
        _log_polled_hardware_event(
            tray,
            "brightness_change",
            raw=_coerce_poll_int(raw_brightness, default=current_brightness),
            old=_coerce_poll_int(last_brightness, default=current_brightness),
            new=int(current_brightness),
            dim_temp_active=bool(dim_temp_active),
            dim_temp_target=dim_temp_target,
            **debug_fields,
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
                if (
                    not bool(tray_vars.get("_user_forced_off", False))
                    and not bool(tray_vars.get("_power_forced_off", False))
                    and not bool(tray_vars.get("_idle_forced_off", False))
                ):
                    tray.is_off = False

        _refresh_ui_without_icon_animation(tray)
        return current_brightness, current_off

    if last_off_state is not None and current_off != last_off_state:
        debug_fields: dict[str, object] = {}
        if _hardware_debug_logging_enabled():
            debug_fields = {
                "config_brightness": int(_configured_brightness_intent(tray)),
                "idle_forced_off": bool(tray_vars.get("_idle_forced_off", False)),
                "power_forced_off": bool(tray_vars.get("_power_forced_off", False)),
                "power_source_recovery_window": bool(
                    _power_source_recovery_window_active(tray, now=time.monotonic())
                ),
                "user_forced_off": bool(tray_vars.get("_user_forced_off", False)),
                "zero_without_off": bool(current_brightness == 0 and not bool(current_off)),
            }
        _log_polled_hardware_event(
            tray,
            "off_state_change",
            old=bool(last_off_state),
            new=bool(current_off),
            **debug_fields,
        )

        if bool(tray_vars.get("_power_forced_off", False)) and current_off:
            return current_brightness, current_off

        if current_off:
            if _recover_recent_power_source_blank_best_effort(tray, current_brightness=current_brightness):
                return current_brightness, False
            if _power_source_recovery_window_active(tray, now=time.monotonic()):
                return current_brightness, False
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
