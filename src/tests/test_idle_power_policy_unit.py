from __future__ import annotations

import pytest

from src.tray.pollers.idle_power_policy import compute_idle_action


def test_compute_idle_action_returns_none_when_user_forced_off() -> None:
    action = compute_idle_action(
        dimmed=False,
        screen_off=False,
        is_off=True,
        idle_forced_off=False,
        dim_temp_active=True,
        idle_timeout_s=60.0,
        power_management_enabled=True,
        screen_dim_sync_enabled=True,
        screen_dim_sync_mode="temp",
        screen_dim_temp_brightness=5,
        brightness=20,
        user_forced_off=True,
        power_forced_off=False,
    )
    assert action is None


def test_compute_idle_action_returns_none_when_power_forced_off() -> None:
    action = compute_idle_action(
        dimmed=False,
        screen_off=False,
        is_off=True,
        idle_forced_off=False,
        dim_temp_active=True,
        idle_timeout_s=60.0,
        power_management_enabled=True,
        screen_dim_sync_enabled=True,
        screen_dim_sync_mode="temp",
        screen_dim_temp_brightness=5,
        brightness=20,
        user_forced_off=False,
        power_forced_off=True,
    )
    assert action is None


def test_compute_idle_action_temp_dim_mode_dimmed_triggers_dim_to_temp() -> None:
    action = compute_idle_action(
        dimmed=True,
        screen_off=False,
        is_off=False,
        idle_forced_off=False,
        dim_temp_active=False,
        idle_timeout_s=60.0,
        power_management_enabled=True,
        screen_dim_sync_enabled=True,
        screen_dim_sync_mode="temp",
        screen_dim_temp_brightness=5,
        brightness=25,
        user_forced_off=False,
        power_forced_off=False,
    )
    assert action == "dim_to_temp"


def test_compute_idle_action_temp_dim_mode_screen_off_triggers_turn_off() -> None:
    action = compute_idle_action(
        dimmed=True,
        screen_off=True,
        is_off=False,
        idle_forced_off=False,
        dim_temp_active=False,
        idle_timeout_s=60.0,
        power_management_enabled=True,
        screen_dim_sync_enabled=True,
        screen_dim_sync_mode="temp",
        screen_dim_temp_brightness=5,
        brightness=25,
        user_forced_off=False,
        power_forced_off=False,
    )
    assert action == "turn_off"


def test_compute_idle_action_temp_dim_mode_dimmed_does_not_repeat_when_dim_temp_active() -> None:
    action = compute_idle_action(
        dimmed=True,
        screen_off=False,
        is_off=False,
        idle_forced_off=False,
        dim_temp_active=True,
        idle_timeout_s=60.0,
        power_management_enabled=True,
        screen_dim_sync_enabled=True,
        screen_dim_sync_mode="temp",
        screen_dim_temp_brightness=5,
        brightness=25,
        user_forced_off=False,
        power_forced_off=False,
    )
    assert action is None


def test_compute_idle_action_restore_brightness_when_undimmed_and_dim_temp_active() -> None:
    action = compute_idle_action(
        dimmed=False,
        screen_off=False,
        is_off=False,
        idle_forced_off=False,
        dim_temp_active=True,
        idle_timeout_s=60.0,
        power_management_enabled=True,
        screen_dim_sync_enabled=True,
        screen_dim_sync_mode="temp",
        screen_dim_temp_brightness=5,
        brightness=25,
        user_forced_off=False,
        power_forced_off=False,
    )
    assert action == "restore_brightness"


@pytest.mark.parametrize("forced_flag", ["user", "power"])
def test_compute_idle_action_does_not_restore_brightness_if_forced_off(
    forced_flag: str,
) -> None:
    action = compute_idle_action(
        dimmed=False,
        screen_off=False,
        is_off=False,
        idle_forced_off=False,
        dim_temp_active=True,
        idle_timeout_s=60.0,
        power_management_enabled=True,
        screen_dim_sync_enabled=True,
        screen_dim_sync_mode="temp",
        screen_dim_temp_brightness=5,
        brightness=25,
        user_forced_off=(forced_flag == "user"),
        power_forced_off=(forced_flag == "power"),
    )
    assert action is None
