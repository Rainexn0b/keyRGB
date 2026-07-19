from __future__ import annotations

from src.tray.pollers.hardware._decisions import (
    BrightnessPersistDecision,
    OffStatePersistDecision,
    classify_brightness_change_persist,
    classify_off_state_change_persist,
    coerce_poll_int,
    hardware_poll_interval_s,
    normalize_brightness_to_config_scale,
    power_source_recovery_window_active,
    should_attempt_power_source_blank_recovery,
    should_attempt_stable_zero_brightness_recovery,
)

__all__ = [
    "BrightnessPersistDecision",
    "OffStatePersistDecision",
    "classify_brightness_change_persist",
    "classify_off_state_change_persist",
    "coerce_poll_int",
    "hardware_poll_interval_s",
    "normalize_brightness_to_config_scale",
    "power_source_recovery_window_active",
    "should_attempt_power_source_blank_recovery",
    "should_attempt_stable_zero_brightness_recovery",
]
