from __future__ import annotations

import time

from src.core.power_policies.battery_saver_policy import BatterySaverPolicy


def test_battery_saver_dims_on_unplug_and_restores_on_ac() -> None:
    policy = BatterySaverPolicy(enabled=True, target_brightness=25, debounce_seconds=0.0)

    now = 100.0
    assert policy.update(on_ac=True, current_brightness=100, is_off=False, now=now) is None

    now += 1.0
    assert policy.update(on_ac=False, current_brightness=100, is_off=False, now=now) == 25

    # While on battery, user changes brightness manually.
    now += 1.0
    assert policy.update(on_ac=False, current_brightness=40, is_off=False, now=now) is None

    # Back on AC: restore original AC brightness.
    now += 1.0
    assert policy.update(on_ac=True, current_brightness=40, is_off=False, now=now) == 100


def test_battery_saver_noop_when_disabled() -> None:
    policy = BatterySaverPolicy(enabled=False, target_brightness=25, debounce_seconds=0.0)

    now = 0.0
    assert policy.update(on_ac=True, current_brightness=100, is_off=False, now=now) is None

    now += 1.0
    assert policy.update(on_ac=False, current_brightness=100, is_off=False, now=now) is None


def test_battery_saver_does_not_dim_when_keyboard_off_or_brightness_zero() -> None:
    policy = BatterySaverPolicy(enabled=True, target_brightness=25, debounce_seconds=0.0)

    now = 0.0
    assert policy.update(on_ac=True, current_brightness=0, is_off=False, now=now) is None

    now += 1.0
    assert policy.update(on_ac=False, current_brightness=0, is_off=False, now=now) is None

    # If the user explicitly turned the keyboard off, don't fight it.
    now += 1.0
    assert policy.update(on_ac=True, current_brightness=100, is_off=True, now=now) is None


def test_battery_saver_debounces_flapping() -> None:
    policy = BatterySaverPolicy(enabled=True, target_brightness=25, debounce_seconds=5.0)

    now = 0.0
    assert policy.update(on_ac=True, current_brightness=100, is_off=False, now=now) is None

    # First transition (after debounce window) dims.
    now += 6.0
    assert policy.update(on_ac=False, current_brightness=100, is_off=False, now=now) == 25

    # Rapid flip back should be ignored.
    now += 1.0
    assert policy.update(on_ac=True, current_brightness=25, is_off=False, now=now) is None

    # After debounce window, restore happens.
    now += 6.0
    assert policy.update(on_ac=True, current_brightness=25, is_off=False, now=now) == 100
