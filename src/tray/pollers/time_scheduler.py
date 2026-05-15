from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from src.tray.controllers._lighting_controller_helpers import (
    _log_tray_exception,
    get_effect_name,
    is_reactive_effect,
    is_software_effect,
    sync_reactive_effect_brightness_state,
    try_log_event,
)
from src.tray.controllers.lighting_controller import start_current_effect


if TYPE_CHECKING:
    from src.tray.protocols import LightingTrayProtocol


logger = logging.getLogger(__name__)

_BRIGHTNESS_COERCION_EXCEPTIONS = (TypeError, ValueError, OverflowError)
_SCHEDULER_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _apply_time_scheduler_brightness(
    tray: LightingTrayProtocol,
    base_brightness: int | None,
    reactive_brightness: int | None,
) -> None:
    try:
        base_brightness_int = None if base_brightness is None else int(base_brightness)
        reactive_brightness_int = None if reactive_brightness is None else int(reactive_brightness)
    except _BRIGHTNESS_COERCION_EXCEPTIONS:
        return

    if base_brightness_int is None and reactive_brightness_int is None:
        return

    if base_brightness_int is not None and base_brightness_int < 0:
        return
    if reactive_brightness_int is not None and reactive_brightness_int < 0:
        return

    if tray._user_forced_off:
        return

    if tray._power_forced_off or tray._idle_forced_off:
        return

    try:
        if base_brightness_int is not None and base_brightness_int > 0:
            tray._last_brightness = base_brightness_int

        try_log_event(
            tray,
            "time_scheduler",
            "apply_brightness",
            base=base_brightness_int,
            reactive=reactive_brightness_int,
        )

        effect = get_effect_name(tray)
        is_sw_effect = is_software_effect(effect)
        is_reactive = is_reactive_effect(effect)

        prev_cfg_brightness = getattr(tray.config, "brightness", 0)
        fade_down = bool(base_brightness_int is not None and base_brightness_int < prev_cfg_brightness)
        fade_s = 0.12 if base_brightness_int is not None and base_brightness_int <= 0 else 0.25

        if is_reactive:
            if base_brightness_int is not None:
                tray.config.perkey_brightness = base_brightness_int
                tray.config.brightness = base_brightness_int
            if reactive_brightness_int is not None:
                tray.config.reactive_brightness = reactive_brightness_int
            sync_reactive_effect_brightness_state(
                tray,
                source="time-scheduler",
                base_brightness=base_brightness_int,
                reactive_brightness=reactive_brightness_int,
                fade=fade_down,
                fade_duration_s=fade_s,
            )
            tray._refresh_ui()
            return

        if reactive_brightness_int is not None:
            tray.config.reactive_brightness = reactive_brightness_int
        if base_brightness_int is None:
            return

        tray.config.brightness = base_brightness_int
        tray.engine.set_brightness(
            tray.config.brightness,
            apply_to_hardware=not is_sw_effect,
            fade=fade_down,
            fade_duration_s=fade_s,
        )
        if not bool(getattr(tray, "is_off", False)) and not is_sw_effect:
            start_current_effect(tray)
        tray._refresh_ui()
    except _SCHEDULER_RUNTIME_EXCEPTIONS as exc:  # @quality-exception exception-transparency: time-scheduler brightness application crosses config setters, backend runtime calls, and UI callbacks; must remain non-fatal
        _log_tray_exception(tray, "Failed to apply time-scheduler brightness: %s", exc)
        return


def _parse_time(time_str: str) -> tuple[int, int] | None:
    try:
        parts = str(time_str).strip().split(":")
        if len(parts) != 2:
            return None
        hour = int(parts[0])
        minute = int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        return (hour, minute)
    except (TypeError, ValueError):
        return None


def _is_night(now: datetime, day_start: tuple[int, int], night_start: tuple[int, int]) -> bool:
    """Return True if `now` is in the night period.

    Night is defined as the period from night_start to day_start.
    If day_start == night_start, the whole day is treated as day.
    """
    current_minutes = now.hour * 60 + now.minute
    day_start_minutes = day_start[0] * 60 + day_start[1]
    night_start_minutes = night_start[0] * 60 + night_start[1]

    if night_start_minutes == day_start_minutes:
        return False

    if night_start_minutes < day_start_minutes:
        # Night is a contiguous block during the day (e.g. 02:00 to 14:00)
        return night_start_minutes <= current_minutes < day_start_minutes
    else:
        # Night wraps around midnight (e.g. 22:00 to 08:00)
        return current_minutes >= night_start_minutes or current_minutes < day_start_minutes


def _read_scheduler_config(tray: LightingTrayProtocol) -> dict:
    """Read time-scheduler config values safely."""
    cfg = tray.config
    return {
        "enabled": bool(getattr(cfg, "time_scheduler_enabled", False)),
        "day_start": str(getattr(cfg, "day_start_time", "08:00")),
        "night_start": str(getattr(cfg, "night_start_time", "22:00")),
        "day_base": max(0, min(50, int(getattr(cfg, "day_base_brightness", 25)))),
        "day_reactive": max(0, min(50, int(getattr(cfg, "day_reactive_brightness", 25)))),
        "night_base": max(0, min(50, int(getattr(cfg, "night_base_brightness", 10)))),
        "night_reactive": max(0, min(50, int(getattr(cfg, "night_reactive_brightness", 10)))),
        "power_management_enabled": bool(getattr(cfg, "power_management_enabled", True)),
    }


def _run_scheduler_iteration(tray: LightingTrayProtocol) -> None:
    cfg = _read_scheduler_config(tray)

    if not cfg["enabled"]:
        return

    day_start = _parse_time(cfg["day_start"])
    night_start = _parse_time(cfg["night_start"])

    if day_start is None or night_start is None:
        logger.warning("Invalid time-scheduler times: day=%s night=%s", cfg["day_start"], cfg["night_start"])
        return

    now = datetime.now()
    in_night = _is_night(now, day_start, night_start)

    if in_night:
        base_brightness = cfg["night_base"]
        reactive_brightness = cfg["night_reactive"]
        _apply_time_scheduler_brightness(tray, base_brightness, reactive_brightness)
    else:
        if cfg["power_management_enabled"]:
            _apply_time_scheduler_brightness(tray, None, cfg["day_reactive"])
        else:
            _apply_time_scheduler_brightness(tray, cfg["day_base"], cfg["day_reactive"])


def _scheduler_loop(
    tray: LightingTrayProtocol,
    *,
    sleep_fn: Callable[[float], None],
    now_fn: Callable[[], datetime],
) -> None:
    """Main scheduler polling loop.

    Checks every 60 seconds whether the time-scheduler should apply
    brightness overrides.
    """
    last_applied_key: str | None = None

    while True:
        try:
            cfg = _read_scheduler_config(tray)

            if cfg["enabled"]:
                day_start = _parse_time(cfg["day_start"])
                night_start = _parse_time(cfg["night_start"])

                if day_start is not None and night_start is not None:
                    now = now_fn()
                    in_night = _is_night(now, day_start, night_start)

                    # Build an apply key so we only apply when the period or config changes
                    apply_key = f"{in_night}:{cfg['night_base']}:{cfg['night_reactive']}:{cfg['day_base']}:{cfg['day_reactive']}:{cfg['power_management_enabled']}"

                    if apply_key != last_applied_key:
                        if in_night:
                            _apply_time_scheduler_brightness(tray, cfg["night_base"], cfg["night_reactive"])
                            try_log_event(tray, "time_scheduler", "night_applied")
                        else:
                            if cfg["power_management_enabled"]:
                                _apply_time_scheduler_brightness(tray, None, cfg["day_reactive"])
                                try_log_event(
                                    tray,
                                    "time_scheduler",
                                    "day_reactive_applied_base_deferred_to_power_policy",
                                )
                            else:
                                _apply_time_scheduler_brightness(tray, cfg["day_base"], cfg["day_reactive"])
                                try_log_event(tray, "time_scheduler", "day_applied")
                        last_applied_key = apply_key
        except _SCHEDULER_RUNTIME_EXCEPTIONS as exc:
            logger.error("Time-scheduler iteration error: %s", exc, exc_info=True)

        sleep_fn(60.0)


def start_time_scheduler_polling(tray: LightingTrayProtocol) -> None:
    """Start the time-of-day brightness scheduler in a daemon thread."""

    def run_scheduler() -> None:
        _scheduler_loop(tray, sleep_fn=time.sleep, now_fn=datetime.now)

    threading.Thread(target=run_scheduler, daemon=True).start()
