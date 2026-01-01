from __future__ import annotations

from src.tray.pollers.idle_power_polling import _compute_idle_action


def test_dimmed_turns_off() -> None:
    assert (
        _compute_idle_action(
            dimmed=True,
            screen_off=False,
            idle_timeout_s=60.0,
            is_off=False,
            idle_forced_off=False,
            dim_temp_active=False,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
        )
        == "turn_off"
    )


def test_dimmed_temp_mode_dims() -> None:
    assert (
        _compute_idle_action(
            dimmed=True,
            screen_off=False,
            idle_timeout_s=60.0,
            is_off=False,
            idle_forced_off=False,
            dim_temp_active=False,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="temp",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
        )
        == "dim_to_temp"
    )


def test_dimmed_temp_mode_turns_off_when_screen_off() -> None:
    assert (
        _compute_idle_action(
            dimmed=True,
            screen_off=True,
            idle_timeout_s=60.0,
            is_off=False,
            idle_forced_off=False,
            dim_temp_active=False,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="temp",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
        )
        == "turn_off"
    )


def test_temp_mode_turns_off_when_screen_off_even_if_dimmed_false() -> None:
    assert (
        _compute_idle_action(
            dimmed=False,
            screen_off=True,
            idle_timeout_s=60.0,
            is_off=False,
            idle_forced_off=False,
            dim_temp_active=False,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="temp",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
        )
        == "turn_off"
    )


def test_dim_sync_does_not_act_when_disabled_or_zero_brightness() -> None:
    assert (
        _compute_idle_action(
            dimmed=True,
            screen_off=False,
            idle_timeout_s=60.0,
            is_off=False,
            idle_forced_off=False,
            dim_temp_active=False,
            power_management_enabled=False,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
        )
        is None
    )

    assert (
        _compute_idle_action(
            dimmed=True,
            screen_off=False,
            idle_timeout_s=60.0,
            is_off=False,
            idle_forced_off=False,
            dim_temp_active=False,
            power_management_enabled=True,
            screen_dim_sync_enabled=False,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
        )
        is None
    )

    assert (
        _compute_idle_action(
            dimmed=True,
            screen_off=False,
            idle_timeout_s=60.0,
            is_off=False,
            idle_forced_off=False,
            dim_temp_active=False,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
            brightness=0,
            user_forced_off=False,
            power_forced_off=False,
        )
        is None
    )


def test_restore_when_not_dimmed_and_off() -> None:
    assert (
        _compute_idle_action(
            dimmed=False,
            screen_off=False,
            idle_timeout_s=60.0,
            is_off=True,
            idle_forced_off=False,
            dim_temp_active=False,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
        )
        == "restore"
    )


def test_restore_brightness_when_undimmed_after_temp() -> None:
    assert (
        _compute_idle_action(
            dimmed=False,
            screen_off=False,
            idle_timeout_s=60.0,
            is_off=False,
            idle_forced_off=False,
            dim_temp_active=True,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="temp",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
        )
        == "restore_brightness"
    )


def test_restore_when_dim_unknown_and_off() -> None:
    assert (
        _compute_idle_action(
            dimmed=None,
            screen_off=False,
            idle_timeout_s=60.0,
            is_off=True,
            idle_forced_off=False,
            dim_temp_active=False,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
        )
        == "restore"
    )


def test_idle_unknown_does_not_restore_if_idle_forced_off() -> None:
    assert (
        _compute_idle_action(
            dimmed=None,
            screen_off=False,
            idle_timeout_s=60.0,
            is_off=True,
            idle_forced_off=True,
            dim_temp_active=False,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
        )
        is None
    )


def test_idle_never_fights_user_or_power_forced_off() -> None:
    assert (
        _compute_idle_action(
            dimmed=False,
            screen_off=False,
            idle_timeout_s=60.0,
            is_off=True,
            idle_forced_off=False,
            dim_temp_active=False,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=True,
            power_forced_off=False,
        )
        is None
    )

    assert (
        _compute_idle_action(
            dimmed=False,
            screen_off=False,
            idle_timeout_s=60.0,
            is_off=True,
            idle_forced_off=False,
            dim_temp_active=False,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=True,
        )
        is None
    )
