"""Idle/display sync and time-of-day scheduler config accessors."""

from __future__ import annotations

from typing import Any

from ._lighting import _props as _config_props


class SchedulerConfigAccessors:
    """Idle dim / screen-sync and day-night scheduler accessors for ``Config``."""

    _settings: dict[str, Any]

    def _save(self) -> None: ...

    # ---- screen dim sync / idle display

    screen_dim_sync_enabled = _config_props.bool_prop("screen_dim_sync_enabled", default=True)
    # Respect the ITE controller's own ~10-minute keyboard-input sleep timeout
    # as a valid off state (deck stays dark, wakes on new input) instead of
    # force re-lighting it via the hidden stable-zero recovery.
    controller_sleep_respect = _config_props.bool_prop("controller_sleep_respect", default=False)
    screen_dim_sync_mode = _config_props.enum_prop("screen_dim_sync_mode", default="off", allowed=("off", "temp"))
    # Temp brightness is intended to be non-zero; allow 1..50.
    screen_dim_temp_brightness = _config_props.int_prop(
        "screen_dim_temp_brightness",
        default=5,
        min_v=1,
        max_v=50,
    )
    idle_dim_debounce_enter_polls = _config_props.int_prop(
        "idle_dim_debounce_enter_polls", default=6, min_v=1, max_v=60
    )
    idle_dim_debounce_exit_polls = _config_props.int_prop("idle_dim_debounce_exit_polls", default=10, min_v=1, max_v=60)
    # Fade duration (seconds) for idle/power dim, turn-off, and restore ramps.
    idle_fade_duration_s = _config_props.float_prop("idle_fade_duration_s", default=0.6, min_v=0.1, max_v=3.0)

    # ---- time-of-day brightness scheduler

    time_scheduler_enabled = _config_props.bool_prop("time_scheduler_enabled", default=False)
    day_start_time = _config_props.str_prop("day_start_time", default="08:00")
    night_start_time = _config_props.str_prop("night_start_time", default="20:00")
    day_base_brightness = _config_props.int_prop("day_base_brightness", default=40, min_v=0, max_v=50)
    day_reactive_brightness = _config_props.int_prop("day_reactive_brightness", default=50, min_v=0, max_v=50)
    night_base_brightness = _config_props.int_prop("night_base_brightness", default=20, min_v=0, max_v=50)
    night_reactive_brightness = _config_props.int_prop("night_reactive_brightness", default=50, min_v=0, max_v=50)
