"""Convenience predicates over idle/power tray state.

Extracted from ``idle_power_state.py`` (WS1 / A2 slice 1). Public import path
remains ``src.tray.idle_power_state`` via re-exports.
"""

from __future__ import annotations

from src.tray._idle_power_fields import (
    _coerce_idle_power_optional_int,
    _read_idle_power_state_field_converged,
    read_idle_power_state_bool_field,
    read_idle_power_state_float_field,
    read_idle_power_state_optional_int_field,
    set_idle_power_state_field,
)


def reset_dim_state_on_tray(tray: object) -> None:
    """Reset dim-temporary state on both the tray and typed owner.

    Convenience helper that clears ``dim_temp_active`` and
    ``dim_temp_target_brightness`` in a single call, keeping the legacy
    tray attributes and the ``TrayIdlePowerState`` owner in sync.
    """
    set_idle_power_state_field(tray, attr_name="_dim_temp_active", state_name="dim_temp_active", value=False)
    set_idle_power_state_field(
        tray, attr_name="_dim_temp_target_brightness", state_name="dim_temp_target_brightness", value=None
    )


def read_forced_off_flags(tray: object) -> tuple[bool, bool, bool]:
    """Return ``(user_forced_off, power_forced_off, idle_forced_off)``.

    Reads through the legacy-attr / owner compatibility bridge so callers do
    not need to touch private tray attributes directly.
    """

    user = read_idle_power_state_bool_field(
        tray, attr_name="_user_forced_off", state_name="user_forced_off", default=False
    )
    power = read_idle_power_state_bool_field(
        tray, attr_name="_power_forced_off", state_name="power_forced_off", default=False
    )
    idle = read_idle_power_state_bool_field(
        tray, attr_name="_idle_forced_off", state_name="idle_forced_off", default=False
    )
    return user, power, idle


def any_forced_off(tray: object) -> bool:
    """True when user, power, or idle policy is holding the keyboard off."""

    user, power, idle = read_forced_off_flags(tray)
    return bool(user or power or idle)


def is_user_forced_off(tray: object) -> bool:
    return read_forced_off_flags(tray)[0]


def is_system_forced_off(tray: object) -> bool:
    """True when power or idle policy (not the user) is holding the keyboard off."""

    _user, power, idle = read_forced_off_flags(tray)
    return bool(power or idle)


def is_dim_temp_active(tray: object) -> bool:
    return read_idle_power_state_bool_field(
        tray, attr_name="_dim_temp_active", state_name="dim_temp_active", default=False
    )


def dim_temp_target_brightness(tray: object) -> int | None:
    return read_idle_power_state_optional_int_field(
        tray,
        attr_name="_dim_temp_target_brightness",
        state_name="dim_temp_target_brightness",
        default=None,
    )


def read_last_resume_at(tray: object) -> float:
    return read_idle_power_state_float_field(
        tray, attr_name="_last_resume_at", state_name="last_resume_at", default=0.0
    )


def read_last_brightness(tray: object, *, default: int = 25) -> int:
    """Return the last non-zero brightness cache used for restore paths."""

    value = _read_idle_power_state_field_converged(
        tray,
        attr_name="_last_brightness",
        state_name="last_brightness",
        default=int(default),
        coerce=_coerce_idle_power_optional_int,
    )
    if value is None:
        return int(default)
    if isinstance(value, (int, float, str, bytes, bytearray)):
        try:
            brightness = int(value)
        except (TypeError, ValueError, OverflowError):
            return int(default)
    else:
        return int(default)
    return brightness if brightness > 0 else int(default)


def set_last_brightness(tray: object, value: int) -> None:
    """Cache last brightness on legacy tray attr and typed owner."""

    try:
        brightness = int(value)
    except (TypeError, ValueError, OverflowError):
        return
    if brightness <= 0:
        return
    set_idle_power_state_field(
        tray,
        attr_name="_last_brightness",
        state_name="last_brightness",
        value=brightness,
    )
