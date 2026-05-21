from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from src.core.brightness_layers import compose_power_source_brightness_overrides
from src.core.brightness_layers import resolve_scheduler_brightness_state


def test_resolve_scheduler_brightness_state_applies_day_window_without_power_source_override() -> None:
    config = MagicMock()
    config.time_scheduler_enabled = True
    config.day_start_time = "08:00"
    config.night_start_time = "20:00"
    config.day_base_brightness = 30
    config.day_reactive_brightness = 45
    config.night_base_brightness = 10
    config.night_reactive_brightness = 20
    config.ac_lighting_brightness = None
    config.battery_lighting_brightness = None

    state = resolve_scheduler_brightness_state(
        config,
        now=datetime(2024, 1, 1, 12, 0),
        power_management_enabled=True,
    )

    assert state.enabled is True
    assert state.times_valid is True
    assert state.in_night is False
    assert state.active_base_brightness == 30
    assert state.active_reactive_brightness == 45
    assert state.defer_base_to_power_policy is False
    assert state.applied_base_brightness == 30


def test_resolve_scheduler_brightness_state_defers_base_when_power_source_override_exists() -> None:
    config = MagicMock()
    config.time_scheduler_enabled = True
    config.day_start_time = "08:00"
    config.night_start_time = "20:00"
    config.day_base_brightness = 30
    config.day_reactive_brightness = 45
    config.night_base_brightness = 10
    config.night_reactive_brightness = 20
    config.ac_lighting_brightness = 40
    config.battery_lighting_brightness = 15

    state = resolve_scheduler_brightness_state(
        config,
        now=datetime(2024, 1, 1, 12, 0),
        power_management_enabled=True,
    )

    assert state.enabled is True
    assert state.times_valid is True
    assert state.in_night is False
    assert state.active_base_brightness == 30
    assert state.active_reactive_brightness == 45
    assert state.defer_base_to_power_policy is True
    assert state.applied_base_brightness is None
    assert state.ac_brightness_override == 40
    assert state.battery_brightness_override == 15


def test_resolve_scheduler_brightness_state_ignores_unconfigured_mock_overrides() -> None:
    config = MagicMock()
    config.time_scheduler_enabled = True
    config.day_start_time = "08:00"
    config.night_start_time = "20:00"
    config.day_base_brightness = 30
    config.day_reactive_brightness = 45
    config.night_base_brightness = 10
    config.night_reactive_brightness = 20
    del config.ac_lighting_brightness
    del config.battery_lighting_brightness

    state = resolve_scheduler_brightness_state(
        config,
        now=datetime(2024, 1, 1, 12, 0),
        power_management_enabled=True,
    )

    assert state.defer_base_to_power_policy is False
    assert state.ac_brightness_override is None
    assert state.battery_brightness_override is None
    assert state.applied_base_brightness == 30


def test_compose_power_source_brightness_overrides_uses_power_source_values_during_day() -> None:
    ac_override, battery_override = compose_power_source_brightness_overrides(
        ac_brightness_override=40,
        battery_brightness_override=15,
        scheduler_base_brightness=25,
        scheduler_in_night=False,
    )

    assert ac_override == 40
    assert battery_override == 15


def test_compose_power_source_brightness_overrides_uses_scheduler_as_day_fallback() -> None:
    ac_override, battery_override = compose_power_source_brightness_overrides(
        ac_brightness_override=None,
        battery_brightness_override=15,
        scheduler_base_brightness=25,
        scheduler_in_night=False,
    )

    assert ac_override == 25
    assert battery_override == 15


def test_compose_power_source_brightness_overrides_caps_values_at_night() -> None:
    ac_override, battery_override = compose_power_source_brightness_overrides(
        ac_brightness_override=40,
        battery_brightness_override=15,
        scheduler_base_brightness=25,
        scheduler_in_night=True,
    )

    assert ac_override == 25
    assert battery_override == 15


def test_compose_power_source_brightness_overrides_uses_scheduler_as_night_fallback() -> None:
    ac_override, battery_override = compose_power_source_brightness_overrides(
        ac_brightness_override=None,
        battery_brightness_override=None,
        scheduler_base_brightness=25,
        scheduler_in_night=True,
    )

    assert ac_override == 25
    assert battery_override == 25
