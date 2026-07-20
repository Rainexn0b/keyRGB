"""Hardware-poll blank-recovery executors and shared polling helpers.

Extracted from ``hardware_polling.py`` (WS1 / A3 slice 1) to drop the parent
module below the REFACTOR LOC band without changing behavior. The parent
module re-imports these names so existing monkeypatch seams and tests
importing ``from src.tray.pollers.hardware_polling import _recover_*`` keep
working unchanged.

Grouping rationale: the recovery group needs the same logging, refresh, and
tray-callback-resolution helpers as the main polling loop. Moving both
together keeps the import direction one-way (``hardware_polling`` →
``_recovery``) and avoids a circular import.
"""

from __future__ import annotations

from collections.abc import Callable
import time
from typing import TypeVar

from src.tray.idle_power_state import (
    any_forced_off,
    is_dim_temp_active,
)
from src.tray.pollers.hardware._decisions import (
    DEFAULT_HARDWARE_POLL_INTERVAL_S,
    FAST_HARDWARE_POLL_INTERVAL_S,
    POWER_SOURCE_RECOVERY_COOLDOWN_S,
    POWER_SOURCE_RECOVERY_WINDOW_S,
    STABLE_ZERO_BRIGHTNESS_RECOVERY_COOLDOWN_S,
    hardware_poll_interval_s as _pure_hardware_poll_interval_s,
    power_source_recovery_window_active as _pure_power_source_recovery_window_active,
    should_attempt_power_source_blank_recovery,
    should_attempt_stable_zero_brightness_recovery,
)
from src.tray.protocols import (
    IdlePowerTrayProtocol,
    clear_idle_power_state_field,
    read_idle_power_state_float_field,
    set_idle_power_state_field,
)


_T = TypeVar("_T")

_BRIGHTNESS_COERCION_ERRORS = (TypeError, ValueError, OverflowError)
_HARDWARE_POLL_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_HARDWARE_POLL_RECOVERY_EXCEPTIONS = (OSError, RuntimeError, ValueError)


# ---------------------------------------------------------------------------
# Shared impure helpers (used by both the polling loop and the recovery group)
# ---------------------------------------------------------------------------


def _resolve_tray_callback(tray: object, name: str):
    instance_callback = vars(tray).get(name)
    if callable(instance_callback):
        return instance_callback

    class_callback = getattr(type(tray), name, None)
    if not callable(class_callback):
        return None

    return lambda *args, **kwargs: class_callback(tray, *args, **kwargs)


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


def _log_hardware_polling_error_best_effort(tray: IdlePowerTrayProtocol, exc: Exception) -> None:
    try:
        tray._log_exception("Hardware polling error: %s", exc)
    except _HARDWARE_POLL_RECOVERY_EXCEPTIONS:
        return


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


# ---------------------------------------------------------------------------
# State queries (used by interval/recovery eligibility)
# ---------------------------------------------------------------------------


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
        window_s=POWER_SOURCE_RECOVERY_WINDOW_S,
    )


def _hardware_poll_interval_s(tray: IdlePowerTrayProtocol, *, now: float) -> float:
    return _pure_hardware_poll_interval_s(
        now=now,
        last_power_source_transition_at=_power_source_transition_at(tray),
        window_s=POWER_SOURCE_RECOVERY_WINDOW_S,
        fast_s=FAST_HARDWARE_POLL_INTERVAL_S,
        default_s=DEFAULT_HARDWARE_POLL_INTERVAL_S,
    )


def _configured_brightness_intent(tray: IdlePowerTrayProtocol) -> int:
    try:
        return int(getattr(getattr(tray, "config", None), "brightness", 0))
    except _BRIGHTNESS_COERCION_ERRORS:
        return 0


# ---------------------------------------------------------------------------
# Recovery group
# ---------------------------------------------------------------------------


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
    return should_attempt_power_source_blank_recovery(
        now=when,
        last_power_source_transition_at=_power_source_transition_at(tray),
        last_recovery_at=float(last_recovery_at),
        any_forced_off=any_forced_off(tray),
        configured_brightness_intent=_configured_brightness_intent(tray),
        window_s=POWER_SOURCE_RECOVERY_WINDOW_S,
        cooldown_s=POWER_SOURCE_RECOVERY_COOLDOWN_S,
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
    if not should_attempt_stable_zero_brightness_recovery(
        current_brightness=int(current_brightness),
        dim_temp_active=is_dim_temp_active(tray),
        any_forced_off=any_forced_off(tray),
        configured_brightness_intent=_configured_brightness_intent(tray),
        now=now,
        last_recovery_at=float(last_recovery_at),
        cooldown_s=STABLE_ZERO_BRIGHTNESS_RECOVERY_COOLDOWN_S,
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
