"""Pure time-scheduler helpers for settings load/apply."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class _SchedulerValuesProtocol(Protocol):
    time_scheduler_enabled: bool
    day_start_time: object
    night_start_time: object
    night_reactive_brightness: int
    day_reactive_brightness: int


def parse_scheduler_time(value: object) -> tuple[int, int] | None:
    try:
        parts = str(value or "").strip().split(":")
        if len(parts) != 2:
            return None
        hour = int(parts[0])
        minute = int(parts[1])
    except (TypeError, ValueError, OverflowError):
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


def active_scheduler_reactive_brightness(
    values: _SchedulerValuesProtocol,
    *,
    now: datetime,
    clamp_brightness,
) -> int | None:
    if not bool(values.time_scheduler_enabled):
        return None

    day_start = parse_scheduler_time(values.day_start_time)
    night_start = parse_scheduler_time(values.night_start_time)
    if day_start is None or night_start is None:
        return None

    if is_scheduler_night(now, day_start, night_start):
        return clamp_brightness(values.night_reactive_brightness)
    return clamp_brightness(values.day_reactive_brightness)
