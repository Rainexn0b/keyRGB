from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.core.config.defaults import DEFAULTS


_BRIGHTNESS_COERCION_EXCEPTIONS = (TypeError, ValueError, OverflowError)
_DEFAULT_TIME_SCHEDULER_ENABLED = bool(DEFAULTS["time_scheduler_enabled"])
_DEFAULT_POWER_MANAGEMENT_ENABLED = bool(DEFAULTS["power_management_enabled"])
_DEFAULT_DAY_START = str(DEFAULTS["day_start_time"])
_DEFAULT_NIGHT_START = str(DEFAULTS["night_start_time"])
_DEFAULT_DAY_BASE_BRIGHTNESS = int(DEFAULTS["day_base_brightness"])
_DEFAULT_DAY_REACTIVE_BRIGHTNESS = int(DEFAULTS["day_reactive_brightness"])
_DEFAULT_NIGHT_BASE_BRIGHTNESS = int(DEFAULTS["night_base_brightness"])
_DEFAULT_NIGHT_REACTIVE_BRIGHTNESS = int(DEFAULTS["night_reactive_brightness"])


@dataclass(frozen=True)
class SchedulerBrightnessState:
    enabled: bool
    times_valid: bool
    in_night: bool
    active_base_brightness: int | None
    active_reactive_brightness: int | None
    defer_base_to_power_policy: bool
    ac_brightness_override: int | None
    battery_brightness_override: int | None

    @property
    def applied_base_brightness(self) -> int | None:
        if self.defer_base_to_power_policy:
            return None
        return self.active_base_brightness


def coerce_brightness_value(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(0, min(50, value))
    if isinstance(value, float):
        try:
            return max(0, min(50, int(value)))
        except _BRIGHTNESS_COERCION_EXCEPTIONS:
            return None
    if not isinstance(value, str):
        return None
    try:
        return max(0, min(50, int(value)))
    except _BRIGHTNESS_COERCION_EXCEPTIONS:
        try:
            return max(0, min(50, int(float(value))))
        except _BRIGHTNESS_COERCION_EXCEPTIONS:
            return None


def parse_scheduler_time(value: object) -> tuple[int, int] | None:
    try:
        parts = str(value or "").strip().split(":")
        if len(parts) != 2:
            return None
        hour = int(parts[0])
        minute = int(parts[1])
    except _BRIGHTNESS_COERCION_EXCEPTIONS:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def is_scheduler_night(now: datetime, day_start: tuple[int, int], night_start: tuple[int, int]) -> bool:
    current_minutes = now.hour * 60 + now.minute
    day_start_minutes = day_start[0] * 60 + day_start[1]
    night_start_minutes = night_start[0] * 60 + night_start[1]

    if night_start_minutes == day_start_minutes:
        return False
    if night_start_minutes < day_start_minutes:
        return night_start_minutes <= current_minutes < day_start_minutes
    return current_minutes >= night_start_minutes or current_minutes < day_start_minutes


def _read_brightness_attr(config: object, attr_name: str, *, default: int) -> int:
    value = coerce_brightness_value(getattr(config, attr_name, default))
    if value is None:
        return int(default)
    return int(value)


def _read_optional_brightness_attr(config: object, attr_name: str) -> int | None:
    return coerce_brightness_value(getattr(config, attr_name, None))


def resolve_power_source_brightness_overrides(config: object) -> tuple[int | None, int | None]:
    return (
        _read_optional_brightness_attr(config, "ac_lighting_brightness"),
        _read_optional_brightness_attr(config, "battery_lighting_brightness"),
    )


def compose_power_source_brightness_overrides(
    *,
    ac_brightness_override: int | None,
    battery_brightness_override: int | None,
    scheduler_base_brightness: int | None,
    scheduler_in_night: bool = False,
) -> tuple[int | None, int | None]:
    if scheduler_base_brightness is None:
        return ac_brightness_override, battery_brightness_override

    if bool(scheduler_in_night):
        effective_ac = (
            int(scheduler_base_brightness)
            if ac_brightness_override is None
            else min(int(ac_brightness_override), int(scheduler_base_brightness))
        )
        effective_battery = (
            int(scheduler_base_brightness)
            if battery_brightness_override is None
            else min(int(battery_brightness_override), int(scheduler_base_brightness))
        )
        return effective_ac, effective_battery

    effective_ac = int(scheduler_base_brightness) if ac_brightness_override is None else int(ac_brightness_override)
    effective_battery = (
        int(scheduler_base_brightness) if battery_brightness_override is None else int(battery_brightness_override)
    )
    return effective_ac, effective_battery


def resolve_scheduler_brightness_state(
    config: object,
    *,
    now: datetime,
    power_management_enabled: bool | None = None,
) -> SchedulerBrightnessState:
    enabled = bool(getattr(config, "time_scheduler_enabled", _DEFAULT_TIME_SCHEDULER_ENABLED))
    ac_brightness_override, battery_brightness_override = resolve_power_source_brightness_overrides(config)

    if not enabled:
        return SchedulerBrightnessState(
            enabled=False,
            times_valid=False,
            in_night=False,
            active_base_brightness=None,
            active_reactive_brightness=None,
            defer_base_to_power_policy=False,
            ac_brightness_override=ac_brightness_override,
            battery_brightness_override=battery_brightness_override,
        )

    day_start = parse_scheduler_time(getattr(config, "day_start_time", _DEFAULT_DAY_START))
    night_start = parse_scheduler_time(getattr(config, "night_start_time", _DEFAULT_NIGHT_START))
    if day_start is None or night_start is None:
        return SchedulerBrightnessState(
            enabled=True,
            times_valid=False,
            in_night=False,
            active_base_brightness=None,
            active_reactive_brightness=None,
            defer_base_to_power_policy=False,
            ac_brightness_override=ac_brightness_override,
            battery_brightness_override=battery_brightness_override,
        )

    in_night = is_scheduler_night(now, day_start, night_start)
    active_base_brightness = _read_brightness_attr(
        config,
        "night_base_brightness" if in_night else "day_base_brightness",
        default=_DEFAULT_NIGHT_BASE_BRIGHTNESS if in_night else _DEFAULT_DAY_BASE_BRIGHTNESS,
    )
    active_reactive_brightness = _read_brightness_attr(
        config,
        "night_reactive_brightness" if in_night else "day_reactive_brightness",
        default=_DEFAULT_NIGHT_REACTIVE_BRIGHTNESS if in_night else _DEFAULT_DAY_REACTIVE_BRIGHTNESS,
    )
    effective_power_management_enabled = (
        _DEFAULT_POWER_MANAGEMENT_ENABLED if power_management_enabled is None else bool(power_management_enabled)
    )
    defer_base_to_power_policy = effective_power_management_enabled and (
        ac_brightness_override is not None or battery_brightness_override is not None
    )

    return SchedulerBrightnessState(
        enabled=True,
        times_valid=True,
        in_night=in_night,
        active_base_brightness=active_base_brightness,
        active_reactive_brightness=active_reactive_brightness,
        defer_base_to_power_policy=defer_base_to_power_policy,
        ac_brightness_override=ac_brightness_override,
        battery_brightness_override=battery_brightness_override,
    )
